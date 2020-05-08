# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os

from exabgp.vendoring import six
import traceback

# ================================================================ Registration
#

from exabgp.util import ordinal

from exabgp.reactor.network.outgoing import Outgoing

# from exabgp.reactor.network.error import NotifyError

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message import Message
from exabgp.bgp.message import NOP
from exabgp.bgp.message import _NOP
from exabgp.bgp.message import Open
from exabgp.bgp.message.open import Version
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message import Update
from exabgp.bgp.message import EOR
from exabgp.bgp.message import KeepAlive
from exabgp.bgp.message import Notification
from exabgp.bgp.message import Notify
from exabgp.bgp.message import Operational

from exabgp.bgp.message.direction import IN
from exabgp.bgp.message.update.attribute import Attribute

from exabgp.protocol.ip import IP
from exabgp.reactor.api.processes import ProcessError

from exabgp.logger import Logger
from exabgp.logger import FakeLogger

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

_UPDATE = Update([], b'')
_OPERATIONAL = Operational(0x00)


class Protocol(object):
    decode = True

    def __init__(self, peer):
        try:
            self.logger = Logger()
        except RuntimeError:
            self.logger = FakeLogger()
        self.peer = peer
        self.neighbor = peer.neighbor
        self.negotiated = Negotiated(self.neighbor)
        self.connection = None

        if self.neighbor.connect:
            self.port = self.neighbor.connect
        elif os.environ.get('exabgp.tcp.port', '').isdigit():
            self.port = int(os.environ.get('exabgp.tcp.port'))
        elif os.environ.get('exabgp_tcp_port', '').isdigit():
            self.port = int(os.environ.get('exabgp_tcp_port'))
        else:
            self.port = 179

        from exabgp.configuration.environment import environment

        self.log_routes = peer.neighbor.adj_rib_in or environment.settings().log.routes

    def fd(self):
        if self.connection is None:
            return -1
        return self.connection.fd()

    # XXX: we use self.peer.neighbor.peer_address when we could use self.neighbor.peer_address

    def me(self, message):
        return "%s/%s %s" % (self.peer.neighbor.peer_address, self.peer.neighbor.peer_as, message)

    def accept(self, incoming):
        self.connection = incoming

        if self.peer.neighbor.api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        # very important - as we use this function on __init__
        return self

    def connect(self):
        # allows to test the protocol code using modified StringIO with a extra 'pending' function
        if self.connection:
            return

        local = self.neighbor.md5_ip.top() if not self.neighbor.auto_discovery else None
        peer = self.neighbor.peer_address.top()
        afi = self.neighbor.peer_address.afi
        md5 = self.neighbor.md5_password
        md5_base64 = self.neighbor.md5_base64
        ttl_out = self.neighbor.ttl_out
        self.connection = Outgoing(afi, peer, local, self.port, md5, md5_base64, ttl_out)

        for connected in self.connection.establish():
            yield False

        if self.peer.neighbor.api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        if not local:
            self.neighbor.local_address = IP.create(self.connection.local)
            if self.neighbor.router_id is None and self.neighbor.local_address.afi == AFI.ipv4:
                self.neighbor.router_id = self.neighbor.local_address

        yield True

    def close(self, reason='protocol closed, reason unspecified'):
        if self.connection:
            self.logger.debug(reason, self.connection.session())

            # must be first otherwise we could have a loop caused by the raise in the below
            self.connection.close()
            self.connection = None

            self.peer.stats['down'] = self.peer.stats.get('down', 0) + 1
            try:
                if self.peer.neighbor.api['neighbor-changes']:
                    self.peer.reactor.processes.down(self.peer.neighbor, reason)
            except ProcessError:
                self.logger.debug('could not send notification of neighbor close to API', self.connection.session())

    def _to_api(self, direction, message, raw):
        packets = self.neighbor.api['%s-packets' % direction]
        parsed = self.neighbor.api['%s-parsed' % direction]
        consolidate = self.neighbor.api['%s-consolidate' % direction]
        negotiated = self.negotiated if self.neighbor.api['negotiated'] else None

        if consolidate:
            if packets:
                self.peer.reactor.processes.message(
                    message.ID, self.peer.neighbor, direction, message, negotiated, raw[:19], raw[19:]
                )
            else:
                self.peer.reactor.processes.message(
                    message.ID, self.peer.neighbor, direction, message, negotiated, b'', b''
                )
        else:
            if packets:
                self.peer.reactor.processes.packets(
                    self.peer.neighbor, direction, int(message.ID), negotiated, raw[:19], raw[19:]
                )
            if parsed:
                self.peer.reactor.processes.message(
                    message.ID, self.peer.neighbor, direction, message, negotiated, b'', b''
                )

    def write(self, message, negotiated=None):
        raw = message.message(negotiated)

        code = 'send-%s' % Message.CODE.short(message.ID)
        self.peer.stats[code] = self.peer.stats.get(code, 0) + 1
        if self.neighbor.api.get(code, False):
            self._to_api('send', message, raw)

        for boolean in self.connection.writer(raw):
            yield boolean

    def send(self, raw):
        code = 'send-%s' % Message.CODE.short(ordinal(raw[18]))
        self.peer.stats[code] = self.peer.stats.get(code, 0) + 1
        if self.neighbor.api.get(code, False):
            message = Update.unpack_message(raw[19:], self.negotiated)
            self._to_api('send', message, raw)

        for boolean in self.connection.writer(raw):
            yield boolean

    # Read from network .......................................................

    def read_message(self):
        # This will always be defined by the loop but scope leaking upset scrutinizer/pylint
        msg_id = None

        packets = self.neighbor.api['receive-packets']
        consolidate = self.neighbor.api['receive-consolidate']
        parsed = self.neighbor.api['receive-parsed']

        body, header = b'', b''  # just because pylint/pylama are getting more clever

        for length, msg_id, header, body, notify in self.connection.reader():
            # internal issue
            if notify:
                code = 'receive-%s' % Message.CODE.NOTIFICATION.SHORT
                if self.neighbor.api.get(code, False):
                    if consolidate:
                        self.peer.reactor.processes.notification(
                            self.peer.neighbor, 'receive', notify.code, notify.subcode, str(notify), None, header, body
                        )
                    elif parsed:
                        self.peer.reactor.processes.notification(
                            self.peer.neighbor, 'receive', notify.code, notify.subcode, str(notify), None, b'', b''
                        )
                    elif packets:
                        self.peer.reactor.processes.packets(self.peer.neighbor, 'receive', msg_id, None, header, body)
                # XXX: is notify not already Notify class ?
                raise Notify(notify.code, notify.subcode, str(notify))

            if not length:
                yield _NOP
                continue

            self.logger.debug('<< message of type %s' % Message.CODE.name(msg_id), self.connection.session())

            code = 'receive-%s' % Message.CODE.short(msg_id)
            self.peer.stats[code] = self.peer.stats.get(code, 0) + 1
            for_api = self.neighbor.api.get(code, False)

            if for_api and packets and not consolidate:
                negotiated = self.negotiated if self.neighbor.api.get('negotiated', False) else None
                self.peer.reactor.processes.packets(self.peer.neighbor, 'receive', msg_id, negotiated, header, body)

            if msg_id == Message.CODE.UPDATE:
                if not self.neighbor.adj_rib_in and not (for_api or self.log_routes) and not (parsed or consolidate):
                    yield _UPDATE
                    return

            try:
                message = Message.unpack(msg_id, body, self.negotiated)
            except (KeyboardInterrupt, SystemExit, Notify):
                raise
            except Exception as exc:
                self.logger.debug('could not decode message "%d"' % msg_id, self.connection.session())
                self.logger.debug('%s' % str(exc), self.connection.session())
                self.logger.debug(traceback.format_exc(), self.connection.session())
                raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id)
                # raise Notify(5,0,'unknown message received')

            if message.TYPE == Update.TYPE:
                if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in message.attributes:
                    for nlri in message.nlris:
                        nlri.action = IN.WITHDRAWN

            if for_api:
                negotiated = self.negotiated if self.neighbor.api.get('negotiated', False) else None
                if consolidate:
                    self.peer.reactor.processes.message(
                        msg_id, self.neighbor, 'receive', message, negotiated, header, body
                    )
                elif parsed:
                    self.peer.reactor.processes.message(msg_id, self.neighbor, 'receive', message, negotiated, b'', b'')

            if message.TYPE == Notification.TYPE:
                raise message

            if message.TYPE == Update.TYPE and Attribute.CODE.INTERNAL_DISCARD in message.attributes:
                yield _NOP
            else:
                yield message

    def validate_open(self):
        error = self.negotiated.validate(self.neighbor)
        if error is not None:
            raise Notify(*error)

        if self.neighbor.api['negotiated']:
            self.peer.reactor.processes.negotiated(self.peer.neighbor, self.negotiated)

        if self.negotiated.mismatch:
            self.logger.warning(
                '--------------------------------------------------------------------', self.connection.session()
            )
            self.logger.warning('the connection can not carry the following family/families', self.connection.session())
            for reason, (afi, safi) in self.negotiated.mismatch:
                self.logger.warning(
                    ' - %s is not configured for %s/%s' % (reason, afi, safi), self.connection.session()
                )
            self.logger.warning(
                'therefore no routes of this kind can be announced on the connection', self.connection.session()
            )
            self.logger.warning(
                '--------------------------------------------------------------------', self.connection.session()
            )

    def read_open(self, ip):
        for received_open in self.read_message():
            if received_open.TYPE == NOP.TYPE:
                yield received_open
            else:
                break

        if received_open.TYPE != Open.TYPE:
            raise Notify(5, 1, 'The first packet received is not an open message (%s)' % received_open)

        self.logger.debug('<< %s' % received_open, self.connection.session())
        yield received_open

    def read_keepalive(self):
        for message in self.read_message():
            if message.TYPE == NOP.TYPE:
                yield message
            else:
                break

        if message.TYPE != KeepAlive.TYPE:
            raise Notify(5, 2)

        yield message

    #
    # Sending message to peer
    #

    def new_open(self):
        if self.neighbor.local_as:
            local_as = self.neighbor.local_as
        elif self.negotiated.received_open:
            local_as = self.negotiated.received_open.asn
        else:
            raise RuntimeError('no ASN available for the OPEN message')

        sent_open = Open(
            Version(4),
            local_as,
            self.neighbor.hold_time,
            self.neighbor.router_id,
            Capabilities().new(self.neighbor, self.peer._restarted),
        )

        # we do not buffer open message in purpose
        for _ in self.write(sent_open):
            yield _NOP

        self.logger.debug('>> %s' % sent_open, self.connection.session())
        yield sent_open

    def new_keepalive(self, comment=''):
        keepalive = KeepAlive()

        for _ in self.write(keepalive):
            yield _NOP

        self.logger.debug('>> KEEPALIVE%s' % (' (%s)' % comment if comment else ''), self.connection.session())

        yield keepalive

    def new_notification(self, notification):
        for _ in self.write(notification):
            yield _NOP
        self.logger.debug(
            '>> NOTIFICATION (%d,%d,"%s")'
            % (notification.code, notification.subcode, notification.data.decode('utf-8')),
            self.connection.session(),
        )
        yield notification

    def new_update(self, include_withdraw):
        updates = self.neighbor.rib.outgoing.updates(self.neighbor.group_updates)
        number = 0
        for update in updates:
            for message in update.messages(self.negotiated, include_withdraw):
                number += 1
                for boolean in self.send(message):
                    # boolean is a transient network error we already announced
                    yield _NOP
        if number:
            self.logger.debug('>> %d UPDATE(s)' % number, self.connection.session())
        yield _UPDATE

    def new_eor(self, afi, safi):
        eor = EOR(afi, safi)
        for _ in self.write(eor):
            yield _NOP
        self.logger.debug('>> EOR %s %s' % (afi, safi), self.connection.session())
        yield eor

    def new_eors(self, afi=AFI.undefined, safi=SAFI.undefined):
        # Send EOR to let our peer know he can perform a RIB update
        if self.negotiated.families:
            families = (
                self.negotiated.families if (afi, safi) == (AFI.undefined, SAFI.undefined) else [(afi, safi),]
            )
            for eor_afi, eor_safi in families:
                for _ in self.new_eor(eor_afi, eor_safi):
                    yield _
        else:
            # If we are not sending an EOR, send a keepalive as soon as when finished
            # So the other routers knows that we have no (more) routes to send ...
            # (is that behaviour documented somewhere ??)
            for eor in self.new_keepalive('EOR'):
                yield _NOP
            yield _UPDATE

    def new_operational(self, operational, negotiated):
        for _ in self.write(operational, negotiated):
            yield _NOP
        self.logger.debug('>> OPERATIONAL %s' % str(operational), self.connection.session())
        yield operational

    def new_refresh(self, refresh):
        for _ in self.write(refresh, None):
            yield _NOP
        self.logger.debug('>> REFRESH %s' % str(refresh), self.connection.session())
        yield refresh
