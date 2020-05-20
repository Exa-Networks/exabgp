# encoding: utf-8
"""
peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import time
from collections import defaultdict

# import traceback
from exabgp.vendoring import six
from exabgp.util import ordinal
from exabgp.bgp.timer import ReceiveTimer
from exabgp.bgp.message import Message
from exabgp.bgp.fsm import FSM
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import REFRESH
from exabgp.bgp.message import NOP
from exabgp.bgp.message import Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message import Notification
from exabgp.bgp.message import Notify
from exabgp.reactor.protocol import Protocol
from exabgp.reactor.delay import Delay
from exabgp.reactor.keepalive import KA
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.api.processes import ProcessError

from exabgp.rib.change import Change

from exabgp.configuration.environment import environment
from exabgp.logger import Logger
from exabgp.logger import FakeLogger
from exabgp.logger import LazyFormat

from exabgp.util.trace import trace

from exabgp.util.panic import NO_PANIC
from exabgp.util.panic import FOOTER


class ACTION(object):
    CLOSE = 0x01  # finished, no need to restart the peer
    LATER = 0x02  # re-run at the next reactor round
    NOW = 0x03  # re-run immediatlely
    ALL = [CLOSE, LATER, NOW]


class SEND(object):
    DONE = 0x01
    NORMAL = 0x02
    REFRESH = 0x04
    ALL = [DONE, NORMAL, REFRESH]


# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True


class Interrupted(Exception):
    pass


class Stop(Exception):
    pass


# ======================================================================== Peer
# Present a File like interface to socket.socket


class Peer(object):
    def __init__(self, neighbor, reactor):
        try:
            self.logger = Logger()
            # We only to try to connect via TCP once
            self.once = environment.settings().tcp.once
            self.bind = True if environment.settings().tcp.bind else False
        except RuntimeError:
            self.logger = FakeLogger()
            self.once = False
            self.bind = True

        now = time.time()

        self.reactor = reactor
        self.neighbor = neighbor
        # The next restart neighbor definition
        self._neighbor = None

        self.proto = None
        self.fsm = FSM(self, FSM.IDLE)
        self.stats = {
            'fsm': self.fsm,
            'creation': now,
            'reset': now,
            'complete': 0,
        }
        self.generator = None

        # The peer should restart after a stop
        self._restart = True
        # The peer was restarted (to know what kind of open to send for graceful restart)
        self._restarted = FORCE_GRACEFUL

        # We want to remove routes which are not in the configuration anymore after a signal to reload
        self._reconfigure = True
        # We want to send all the known routes
        self._resend_routes = SEND.DONE

        # We have been asked to teardown the session with this code
        self._teardown = None

        self._delay = Delay()
        self.recv_timer = None

    def id(self):
        return 'peer-%s' % self.neighbor.uid

    def _reset(self, message='', error=''):
        self.fsm.change(FSM.IDLE)
        self.stats = {
            'fsm': self.fsm,
            'creation': self.stats['creation'],
            'reset': time.time(),
            'complete': 0,
        }
        if self.proto:
            try:
                message = u"peer reset, message [{0}] error[{1}]".format(message, error)
            except UnicodeDecodeError as msg_err:
                message = u"peer reset, message [{0}] error[{1}]".format(message, msg_err)
            self.proto.close(message)
        self._delay.increase()

        self.proto = None

        if not self._restart or self.neighbor.generated:
            self.generator = False
            return

        self.generator = None
        self._teardown = None
        self.neighbor.rib.reset()

        # If we are restarting, and the neighbor definition is different, update the neighbor
        if self._neighbor:
            self.neighbor = self._neighbor
            self._neighbor = None

    def _stop(self, message):
        self.generator = None
        if self.proto:
            self.proto.close('stop, message [%s]' % message)
            self.proto = None

    # logging

    def me(self, message):
        return "peer %s ASN %-7s %s" % (self.neighbor.peer_address, self.neighbor.peer_as, message)

    # control

    def stop(self):
        self._teardown = 3
        self._restart = False
        self._restarted = False
        self._delay.reset()
        self.fsm.change(FSM.IDLE)
        self.stats = {
            'fsm': self.fsm,
            'creation': self.stats['creation'],
            'reset': time.time(),
        }
        self.neighbor.rib.uncache()

    def remove(self):
        self._stop("removed")
        self.stop()

    def shutdown(self):
        self._stop("shutting down")
        self.stop()

    def resend(self):
        self._resend_routes = SEND.NORMAL
        self._delay.reset()

    def reestablish(self, restart_neighbor=None):
        # we want to tear down the session and re-establish it
        self._teardown = 3
        self._restart = True
        self._restarted = True
        self._resend_routes = SEND.NORMAL
        self._neighbor = restart_neighbor
        self._delay.reset()

    def reconfigure(self, restart_neighbor=None):
        # we want to update the route which were in the configuration file
        self._reconfigure = True
        self._neighbor = restart_neighbor
        self._resend_routes = SEND.NORMAL
        self._neighbor = restart_neighbor

    def teardown(self, code, restart=True):
        self._restart = restart
        self._teardown = code
        self._delay.reset()

    def socket(self):
        if self.proto:
            return self.proto.fd()
        return -1

    def handle_connection(self, connection):
        self.logger.debug("state machine for the peer is %s" % self.fsm.name(), self.id())

        # if the other side fails, we go back to idle
        if self.fsm == FSM.ESTABLISHED:
            self.logger.debug('we already have a peer in state established for %s' % connection.name(), self.id())
            return connection.notification(6, 7, 'could not accept the connection, already established')

        # 6.8 The convention is to compare the BGP Identifiers of the peers
        # involved in the collision and to retain only the connection initiated
        # by the BGP speaker with the higher-valued BGP Identifier.
        # FSM.IDLE , FSM.ACTIVE , FSM.CONNECT , FSM.OPENSENT , FSM.OPENCONFIRM , FSM.ESTABLISHED

        if self.fsm == FSM.OPENCONFIRM:
            # We cheat: we are not really reading the OPEN, we use the data we have instead
            # it does not matter as the open message will be the same anyway
            local_id = self.neighbor.router_id.pack()
            remote_id = self.proto.negotiated.received_open.router_id.pack()

            if remote_id < local_id:
                self.logger.debug(
                    'closing incoming connection as we have an outgoing connection with higher router-id for %s'
                    % connection.name(),
                    self.id(),
                )
                return connection.notification(
                    6,
                    7,
                    'could not accept the connection, as another connection is already in open-confirm and will go through',
                )

        # accept the connection
        if self.proto:
            self.logger.debug(
                'closing outgoing connection as we have another incoming on with higher router-id for %s'
                % connection.name(),
                self.id(),
            )
            self.proto.close('closing outgoing connection as we have another incoming on with higher router-id')

        self.proto = Protocol(self).accept(connection)
        self.generator = None
        # Let's make sure we do some work with this connection
        self._delay.reset()
        return None

    def established(self):
        return self.fsm == FSM.ESTABLISHED

    def negotiated_families(self):
        if self.proto:
            families = ["%s/%s" % (x[0], x[1]) for x in self.proto.negotiated.families]
        else:
            families = ["%s/%s" % (x[0], x[1]) for x in self.neighbor.families()]

        if len(families) > 1:
            return "[ %s ]" % " ".join(families)
        elif len(families) == 1:
            return families[0]

        return ''

    def _connect(self):
        proto = Protocol(self)
        connected = False
        try:
            for connected in proto.connect():
                if connected:
                    break
                if self._teardown:
                    raise Stop()
                # we want to come back as soon as possible
                yield ACTION.LATER
            self.proto = proto
        except Stop:
            # Connection failed
            if not connected and self.proto:
                self.proto.close('connection to %s:%d failed' % (self.neighbor.peer_address, self.neighbor.connect))

            # A connection arrived before we could establish !
            if not connected or self.proto:
                yield ACTION.NOW
                raise Interrupted()

    def _send_open(self):
        message = Message.CODE.NOP
        for message in self.proto.new_open():
            if ordinal(message.TYPE) == Message.CODE.NOP:
                yield ACTION.NOW
        yield message

    def _read_open(self):
        wait = environment.settings().bgp.openwait
        opentimer = ReceiveTimer(
            self.proto.connection.session, wait, 1, 1, 'waited for open too long, we do not like stuck in active'
        )
        # Only yield if we have not the open, otherwise the reactor can run the other connection
        # which would be bad as we need to do the collission check without going to the other peer
        for message in self.proto.read_open(self.neighbor.peer_address.top()):
            opentimer.check_ka(message)
            # XXX: FIXME: change the whole code to use the ord and not the chr version
            # Only yield if we have not the open, otherwise the reactor can run the other connection
            # which would be bad as we need to do the collission check
            if ordinal(message.TYPE) == Message.CODE.NOP:
                # If a peer does not reply to OPEN message, or not enough bytes
                # yielding ACTION.NOW can cause ExaBGP to busy spin trying to
                # read from peer. See GH #723 .
                yield ACTION.LATER
        yield message

    def _send_ka(self):
        for message in self.proto.new_keepalive('OPENCONFIRM'):
            yield ACTION.NOW

    def _read_ka(self):
        # Start keeping keepalive timer
        for message in self.proto.read_keepalive():
            self.recv_timer.check_ka_timer(message)
            yield ACTION.NOW

    def _establish(self):
        # try to establish the outgoing connection
        self.fsm.change(FSM.ACTIVE)

        if not self.proto:
            for action in self._connect():
                if action in ACTION.ALL:
                    yield action
        self.fsm.change(FSM.CONNECT)

        # normal sending of OPEN first ...
        if self.neighbor.local_as:
            for sent_open in self._send_open():
                if sent_open in ACTION.ALL:
                    yield sent_open
            self.proto.negotiated.sent(sent_open)
            self.fsm.change(FSM.OPENSENT)

        # read the peer's open
        for received_open in self._read_open():
            if received_open in ACTION.ALL:
                yield received_open
        self.proto.negotiated.received(received_open)

        self.proto.connection.msg_size = self.proto.negotiated.msg_size

        # if we mirror the ASN, we need to read first and send second
        if not self.neighbor.local_as:
            for sent_open in self._send_open():
                if sent_open in ACTION.ALL:
                    yield sent_open
            self.proto.negotiated.sent(sent_open)
            self.fsm.change(FSM.OPENSENT)

        self.proto.validate_open()
        self.fsm.change(FSM.OPENCONFIRM)

        self.recv_timer = ReceiveTimer(self.proto.connection.session, self.proto.negotiated.holdtime, 4, 0)
        for action in self._send_ka():
            yield action
        for action in self._read_ka():
            yield action
        self.fsm.change(FSM.ESTABLISHED)
        self.stats['complete'] = time.time()

        # let the caller know that we were sucesfull
        yield ACTION.NOW

    def _main(self):
        """yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"""
        if self._teardown:
            raise Notify(6, 3)

        self.neighbor.rib.incoming.clear()

        include_withdraw = False

        # Announce to the process BGP is up
        self.logger.notice('connected to %s with %s' % (self.id(), self.proto.connection.name()), 'reactor')
        self.stats['up'] = self.stats.get('up', 0) + 1
        if self.neighbor.api['neighbor-changes']:
            try:
                self.reactor.processes.up(self.neighbor)
            except ProcessError:
                # Can not find any better error code than 6,0 !
                # XXX: We can not restart the program so this will come back again and again - FIX
                # XXX: In the main loop we do exit on this kind of error
                raise Notify(6, 0, 'ExaBGP Internal error, sorry.')

        send_eor = not self.neighbor.manual_eor
        new_routes = None
        self._resend_routes = SEND.NORMAL
        send_families = []

        # Every last asm message should be re-announced on restart
        for family in self.neighbor.asm:
            if family in self.neighbor.families():
                self.neighbor.messages.appendleft(self.neighbor.asm[family])

        operational = None
        refresh = None
        command_eor = None
        number = 0
        refresh_enhanced = True if self.proto.negotiated.refresh == REFRESH.ENHANCED else False

        send_ka = KA(self.proto.connection.session, self.proto)

        while not self._teardown:
            for message in self.proto.read_message():
                self.recv_timer.check_ka(message)

                if send_ka() is not False:
                    # we need and will send a keepalive
                    while send_ka() is None:
                        yield ACTION.NOW

                # Received update
                if message.TYPE == Update.TYPE:
                    number += 1
                    self.logger.debug('<< UPDATE #%d' % number, self.id())

                    for nlri in message.nlris:
                        self.neighbor.rib.incoming.update_cache(Change(nlri, message.attributes))
                        self.logger.debug(LazyFormat('   UPDATE #%d nlri ' % number, nlri, str), self.id())

                elif message.TYPE == RouteRefresh.TYPE:
                    if message.reserved == RouteRefresh.request:
                        self._resend_routes = SEND.REFRESH
                        send_families.append((message.afi, message.safi))

                # SEND OPERATIONAL
                if self.neighbor.operational:
                    if not operational:
                        new_operational = self.neighbor.messages.popleft() if self.neighbor.messages else None
                        if new_operational:
                            operational = self.proto.new_operational(new_operational, self.proto.negotiated)

                    if operational:
                        try:
                            six.next(operational)
                        except StopIteration:
                            operational = None
                # make sure that if some operational message are received via the API
                # that we do not eat memory for nothing
                elif self.neighbor.messages:
                    self.neighbor.messages.popleft()

                # SEND REFRESH
                if self.neighbor.route_refresh:
                    if not refresh:
                        new_refresh = self.neighbor.refresh.popleft() if self.neighbor.refresh else None
                        if new_refresh:
                            refresh = self.proto.new_refresh(new_refresh)

                    if refresh:
                        try:
                            six.next(refresh)
                        except StopIteration:
                            refresh = None

                # Take the routes already sent to that peer and resend them
                if self._reconfigure:
                    self._reconfigure = False

                    # we are here following a configuration change
                    if self._neighbor:
                        # see what changed in the configuration
                        self.neighbor.rib.outgoing.replace(self._neighbor.backup_changes, self._neighbor.changes)
                        # do not keep the previous routes in memory as they are not useful anymore
                        self._neighbor.backup_changes = []

                # Take the routes already sent to that peer and resend them
                if self._resend_routes != SEND.DONE:
                    enhanced = True if refresh_enhanced and self._resend_routes == SEND.REFRESH else False
                    self._resend_routes = SEND.DONE
                    self.neighbor.rib.outgoing.resend(send_families, enhanced)
                    send_families = []

                # Need to send update
                if not new_routes and self.neighbor.rib.outgoing.pending():
                    # XXX: in proto really. hum to think about ?
                    new_routes = self.proto.new_update(include_withdraw)

                if new_routes:
                    count = 1 if self.neighbor.rate_limit > 0 else 25
                    try:
                        for _ in range(count):
                            # This can raise a NetworkError
                            six.next(new_routes)
                    except StopIteration:
                        new_routes = None
                        include_withdraw = True

                elif send_eor:
                    send_eor = False
                    for _ in self.proto.new_eors():
                        yield ACTION.NOW
                    self.logger.debug('>> EOR(s)', self.id())

                # SEND MANUAL KEEPALIVE (only if we have no more routes to send)
                elif not command_eor and self.neighbor.eor:
                    new_eor = self.neighbor.eor.popleft()
                    command_eor = self.proto.new_eors(new_eor.afi, new_eor.safi)

                if command_eor:
                    try:
                        six.next(command_eor)
                    except StopIteration:
                        command_eor = None

                if new_routes or message.TYPE != NOP.TYPE:
                    yield ACTION.NOW
                elif self.neighbor.messages or operational:
                    yield ACTION.NOW
                elif self.neighbor.eor or command_eor:
                    yield ACTION.NOW
                else:
                    yield ACTION.LATER

                # read_message will loop until new message arrives with NOP
                if self._teardown:
                    break

        # If graceful restart, silent shutdown
        if self.neighbor.graceful_restart and self.proto.negotiated.sent_open.capabilities.announced(
            Capability.CODE.GRACEFUL_RESTART
        ):
            self.logger.error('closing the session without notification', self.id())
            self.proto.close('graceful restarted negotiated, closing without sending any notification')
            raise NetworkError('closing')

        # notify our peer of the shutdown
        raise Notify(6, self._teardown)

    def _run(self):
        """yield True if we want the reactor to give us back the hand with the same peer loop, None if we do not have any more work to do"""
        try:
            for action in self._establish():
                yield action

            for action in self._main():
                yield action

        # CONNECTION FAILURE
        except NetworkError as network:
            # we tried to connect once, it failed and it was not a manual request, we stop
            if self.once and not self._teardown:
                self.logger.debug('only one attempt to connect is allowed, stopping the peer', self.id())
                self.stop()

            self._reset('closing connection', network)
            return

        # NOTIFY THE PEER OF AN ERROR
        except Notify as notify:
            if self.proto:
                try:
                    generator = self.proto.new_notification(notify)
                    try:
                        while True:
                            six.next(generator)
                            yield ACTION.NOW
                    except StopIteration:
                        pass
                except (NetworkError, ProcessError):
                    self.logger.error('Notification not sent', self.id())
                self._reset('notification sent (%d,%d)' % (notify.code, notify.subcode), notify)
            else:
                self._reset()
            return

        # THE PEER NOTIFIED US OF AN ERROR
        except Notification as notification:
            # we tried to connect once, it failed and it was not a manual request, we stop
            if self.once and not self._teardown:
                self.logger.debug('only one attempt to connect is allowed, stopping the peer', self.id())
                self.stop()

            self._reset('notification received (%d,%d)' % (notification.code, notification.subcode), notification)
            return

        # RECEIVED a Message TYPE we did not expect
        except Message as message:
            self._reset('unexpected message received', message)
            return

        # PROBLEM WRITING TO OUR FORKED PROCESSES
        except ProcessError as process:
            self._reset('process problem', process)
            return

        # ....
        except Interrupted as interruption:
            self._reset('connection received before we could fully establish one')
            return

        # UNHANDLED PROBLEMS
        except Exception as exc:
            # Those messages can not be filtered in purpose
            self.logger.debug('\n'.join([NO_PANIC, '', '', str(type(exc)), str(exc), trace(), FOOTER]), 'reactor')
            self._reset()
            return

    # loop

    def run(self):
        if self.reactor.processes.broken(self.neighbor):
            # XXX: we should perhaps try to restart the process ??
            self.logger.error('ExaBGP lost the helper process for this peer - stopping', 'process')
            if self.reactor.processes.terminate_on_error:
                self.reactor.api_shutdown()
            else:
                self.stop()
            return True

        if self.generator:
            try:
                # This generator only stops when it raises
                # otherwise return one of the ACTION
                return six.next(self.generator)
            except StopIteration:
                # Trying to run a closed loop, no point continuing
                self.generator = None
                if self._restart:
                    return ACTION.LATER
                return ACTION.CLOSE

        elif self.generator is None:
            if self.fsm in [FSM.OPENCONFIRM, FSM.ESTABLISHED]:
                self.logger.debug('stopping, other connection is established', self.id())
                self.generator = False
                return ACTION.LATER
            if self._delay.backoff():
                return ACTION.LATER
            if self._restart:
                self.logger.debug('initialising connection to %s' % self.id(), 'reactor')
                self.generator = self._run()
                return ACTION.LATER  # make sure we go through a clean loop
            return ACTION.CLOSE

    def cli_data(self):
        def tri(value):
            if value is None:
                return None
            return True if value else False

        peer = defaultdict(lambda: None)

        have_peer = self.proto is not None
        have_open = self.proto and self.proto.negotiated.received_open

        if have_peer:
            peer.update(
                {'multi-session': self.proto.negotiated.multisession, 'operational': self.proto.negotiated.operational,}
            )

        if have_open:
            capa = self.proto.negotiated.received_open.capabilities
            peer.update(
                {
                    'router-id': self.proto.negotiated.sent_open.router_id,
                    'peer-id': self.proto.negotiated.received_open.router_id,
                    'hold-time': self.proto.negotiated.received_open.hold_time,
                    'asn4': self.proto.negotiated.asn4,
                    'route-refresh': capa.announced(Capability.CODE.ROUTE_REFRESH),
                    'multi-session': capa.announced(Capability.CODE.MULTISESSION)
                    or capa.announced(Capability.CODE.MULTISESSION_CISCO),
                    'add-path': capa.announced(Capability.CODE.ADD_PATH),
                    'extended-message': capa.announced(Capability.CODE.EXTENDED_MESSAGE),
                    'graceful-restart': capa.announced(Capability.CODE.GRACEFUL_RESTART),
                }
            )

        capabilities = {
            'asn4': (tri(self.neighbor.asn4), tri(peer['asn4'])),
            'route-refresh': (tri(self.neighbor.route_refresh), tri(peer['route-refresh'])),
            'multi-session': (tri(self.neighbor.multisession), tri(peer['multi-session'])),
            'operational': (tri(self.neighbor.operational), tri(peer['operational'])),
            'add-path': (tri(self.neighbor.add_path), tri(peer['add-path'])),
            'extended-message': (tri(self.neighbor.extended_message), tri(peer['extended-message'])),
            'graceful-restart': (tri(self.neighbor.graceful_restart), tri(peer['graceful-restart'])),
        }

        families = {}
        for family in self.neighbor.families():
            if have_open:
                common = True if family in self.proto.negotiated.families else False
                addpath = self.proto.negotiated.addpath.send(*family) and self.proto.negotiated.addpath.receive(*family)
            else:
                common = None
                addpath = None if family in self.neighbor.addpaths() else False
            families[family] = (True, common, addpath)

        messages = {}
        total_sent = 0
        total_rcvd = 0
        for message in ('open', 'notification', 'keepalive', 'update', 'refresh'):
            sent = self.stats.get('send-%s' % message, 0)
            rcvd = self.stats.get('receive-%s' % message, 0)
            total_sent += sent
            total_rcvd += rcvd
            messages[message] = (sent, rcvd)
        messages['total'] = (total_sent, total_rcvd)

        return {
            'down': int(self.stats['reset'] - self.stats['creation']),
            'duration': int(time.time() - self.stats['complete']) if self.stats['complete'] else 0,
            'local-address': str(self.neighbor.local_address),
            'peer-address': str(self.neighbor.peer_address),
            'local-as': int(self.neighbor.local_as),
            'peer-as': int(self.neighbor.peer_as),
            'local-id': str(self.neighbor.router_id),
            'peer-id': None if peer['peer-id'] is None else str(peer['router-id']),
            'local-hold': int(self.neighbor.hold_time),
            'peer-hold': None if peer['hold-time'] is None else int(peer['hold-time']),
            'state': self.fsm.name(),
            'capabilities': capabilities,
            'families': families,
            'messages': messages,
        }
