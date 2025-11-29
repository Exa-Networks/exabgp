"""peer.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio  # noqa: F401 - Used by async methods (_send_open_async, _read_open_async, _send_ka_async, _read_ka_async)
import time
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Generator, Iterator, cast

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.loop import Reactor
    from exabgp.reactor.network.incoming import Incoming

# import traceback
from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import _NOP, _AWAKE, _DONE, Message, Notification, Notify, Open, Update
from exabgp.bgp.message.open.capability import REFRESH, Capability
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.timer import ReceiveTimer
from exabgp.debug.report import format_exception
from exabgp.environment import getenv
from exabgp.logger import lazyformat, lazymsg, log
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.delay import Delay
from exabgp.util.enumeration import TriState
from exabgp.reactor.keepalive import KA
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.protocol import Protocol
from exabgp.rib.change import Change


# As we can not know if this is our first start or not, this flag is used to
# always make the program act like it was recovering from a failure
# If set to FALSE, no EOR and OPEN Flags set for Restart will be set in the
# OPEN Graceful Restart Capability
FORCE_GRACEFUL = True


class Interrupted(Exception):
    pass


class Stop(Exception):
    pass


# ======================================================================== Counter


class Stats(dict):
    __format: dict[str, Any] = {
        'complete': lambda t: 'time {}'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(t)))
    }

    def __init__(self, *args: tuple[Any, ...]) -> None:
        dict.__init__(self, args)
        self.__changed: set[str] = set()

    def __setitem__(self, key: str, val: Any) -> None:
        dict.__setitem__(self, key, val)
        self.__changed.add(key)

    def changed_statistics(self) -> Iterator[str]:
        for name in self.__changed:
            formater = self.__format.get(name, lambda v: f'counter {v}')
            yield f'statistics for {name} {formater(self[name])}'
        self.__changed = set()


# ======================================================================== Peer
# Present a File like interface to socket.socket


class Peer:
    def __init__(self, neighbor: 'Neighbor', reactor: 'Reactor') -> None:
        # Maximum connection attempts (0 = unlimited)
        self.max_connection_attempts: int = getenv().tcp.attempts
        self.connection_attempts: int = 0
        self.bind: bool = True if getenv().tcp.bind else False

        now: float = time.time()

        self.reactor: 'Reactor' = reactor
        self.neighbor: 'Neighbor' = neighbor
        # The next restart neighbor definition
        self._neighbor: 'Neighbor' | None = None

        self.proto: Protocol | None = None
        self.fsm: FSM = FSM(self, FSM.IDLE)
        self.stats: Stats = Stats()
        self.stats.update(
            {
                'fsm': self.fsm,
                'creation': now,  # when the peer was created
                'reset': now,  # time of last reset
                'complete': 0,  # when did the peer got established
                'up': 0,
                'down': 0,
                'receive-open': 0,
                'send-open': 0,
                'receive-notification': 0,
                'send-notification': 0,
                'receive-update': 0,
                'send-update': 0,
                'receive-refresh': 0,
                'send-refresh': 0,
                'receive-keepalive': 0,
                'send-keepalive': 0,
            },
        )

        # None = needs initialization, False = closed/don't restart, Generator = running
        self.generator: Generator[Message, None, None] | bool | None = None
        self._async_task: asyncio.Task | None = None  # For async mode

        # The peer should restart after a stop
        self._restart: bool = True
        # The peer was restarted (to know what kind of open to send for graceful restart)
        self._restarted: bool = FORCE_GRACEFUL

        # We have been asked to teardown the session with this code
        self._teardown: int | None = None

        self._delay: Delay = Delay()
        self.recv_timer: ReceiveTimer | None = None

    def id(self) -> str:
        return 'peer-{}'.format(self.neighbor.uid)

    def _close(self, message: str = '', error: str | Exception = '') -> None:
        if self.fsm not in (FSM.IDLE, FSM.ACTIVE):
            try:
                if self.neighbor.api and self.neighbor.api['neighbor-changes']:
                    self.reactor.processes.down(self.neighbor, message)
            except ProcessError:
                log.debug(
                    lazymsg('peer.close.api.failed reason=process_error'),
                    self.id(),
                )
        self.fsm.change(FSM.IDLE)

        self.stats.update(
            {
                'fsm': self.fsm,
                'reset': time.time(),
                'complete': 0,
                'receive-open': 0,
                'send-open': 0,
                'receive-notification': 0,
                'send-notification': 0,
                'receive-update': 0,
                'send-update': 0,
                'receive-refresh': 0,
                'send-refresh': 0,
                'receive-keepalive': 0,
                'send-keepalive': 0,
            },
        )

        if self.proto:
            try:
                message = f'peer reset, message [{message}] error[{error}]'
            except UnicodeDecodeError as msg_err:
                message = f'peer reset, message [{message}] error[{msg_err}]'
            self.proto.close(message)
        self._delay.increase()

        self.proto = None

    def _reset(self, message: str = '', error: str | Exception = '') -> None:
        self._close(message, error)

        if not self._restart or self.neighbor.generated:
            self.generator = False
            return

        self.generator = None
        self._teardown = None
        self.neighbor.reset_rib()

        # If we are restarting, and the neighbor definition is different, update the neighbor
        if self._neighbor:
            self.neighbor = self._neighbor
            self._neighbor = None

    def _stop(self, message: str) -> None:
        self.generator = None
        if self.proto:
            self._close(f'stop, message [{message}]')

    # logging

    def me(self, message: str) -> str:
        return f'peer {self.neighbor.session.peer_address} ASN {self.neighbor.session.peer_as:<7} {message}'

    # control

    def can_reconnect(self) -> bool:
        """Check if peer can attempt another connection"""
        if self.max_connection_attempts == 0:  # unlimited
            return True
        return self.connection_attempts < self.max_connection_attempts

    def stop(self) -> None:
        self._teardown = 3
        self._restart = False
        self._restarted = False
        self._delay.reset()
        self.fsm.change(FSM.IDLE)
        self.stats.update(
            {
                'fsm': self.fsm,
                'reset': time.time(),
                'complete': 0,
                'receive-open': 0,
                'send-open': 0,
                'receive-notification': 0,
                'send-notification': 0,
                'receive-update': 0,
                'send-update': 0,
                'receive-refresh': 0,
                'send-refresh': 0,
                'receive-keepalive': 0,
                'send-keepalive': 0,
            },
        )
        if self.neighbor.rib:
            self.neighbor.rib.uncache()

    def remove(self) -> None:
        self._stop('removed')
        self.stop()

    def shutdown(self) -> None:
        self._stop('shutting down')
        self.stop()

    def resend(self, enhanced: bool, family: tuple[AFI, SAFI] | None = None) -> None:
        if self.neighbor.rib:
            self.neighbor.rib.outgoing.resend(enhanced, family)
        self._delay.reset()

    def reestablish(self, restart_neighbor: 'Neighbor' | None = None) -> None:
        # we want to tear down the session and re-establish it
        self._teardown = 3
        self._restart = True
        self._restarted = True
        self._neighbor = restart_neighbor
        self._delay.reset()

    def reconfigure(self, restart_neighbor: 'Neighbor' | None = None) -> None:
        # we want to update the route which were in the configuration file
        self._neighbor = restart_neighbor
        # Update self.neighbor immediately so API processes see the new configuration
        # during RELOAD (SIGUSR1), not just during connection reset
        if restart_neighbor:
            self.neighbor = restart_neighbor

    def teardown(self, code: int, restart: bool = True) -> None:
        self._restart = restart
        self._teardown = code
        self._delay.reset()

    def socket(self) -> int:
        if self.proto:
            return self.proto.fd()
        return -1

    def handle_connection(self, connection: 'Incoming') -> Iterator[bool] | None:
        log.debug(lazymsg('peer.fsm.state state={s}', s=self.fsm.name()), self.id())

        # if the other side fails, we go back to idle
        if self.fsm == FSM.ESTABLISHED:
            log.debug(
                lazymsg('peer.connection.rejected connection={c} reason=already_established', c=connection.name()),
                self.id(),
            )
            return connection.notification(6, 7, b'could not accept the connection, already established')

        # 6.8 The convention is to compare the BGP Identifiers of the peers
        # involved in the collision and to retain only the connection initiated
        # by the BGP speaker with the higher-valued BGP Identifier.
        # FSM.IDLE , FSM.ACTIVE , FSM.CONNECT , FSM.OPENSENT , FSM.OPENCONFIRM , FSM.ESTABLISHED

        if self.fsm == FSM.OPENCONFIRM:
            # We cheat: we are not really reading the OPEN, we use the data we have instead
            # it does not matter as the open message will be the same anyway
            assert self.proto is not None  # Must exist in OPENCONFIRM state
            assert self.proto.negotiated.received_open is not None  # Must exist in OPENCONFIRM
            assert self.neighbor.session.router_id is not None  # Must exist at this point
            local_id = self.neighbor.session.router_id.pack_ip()
            remote_id = self.proto.negotiated.received_open.router_id.pack_ip()

            if remote_id < local_id:
                log.debug(
                    lazymsg(
                        'peer.connection.rejected connection={c} reason=higher_router_id_outgoing', c=connection.name()
                    ),
                    self.id(),
                )
                return connection.notification(
                    6,
                    7,
                    b'could not accept the connection, as another connection is already in open-confirm and will go through',
                )

        # accept the connection
        if self.proto:
            log.debug(
                lazymsg('peer.connection.closing connection={c} reason=higher_router_id_incoming', c=connection.name()),
                self.id(),
            )
            self._close('closing outgoing connection as we have another incoming on with higher router-id')

        self.proto = Protocol(self).accept(connection)
        self.generator = None
        # Let's make sure we do some work with this connection
        self._delay.reset()
        return None

    def established(self) -> bool:
        return self.fsm == FSM.ESTABLISHED

    def negotiated_families(self) -> str:
        if self.proto:
            families = [f'{x[0]}/{x[1]}' for x in self.proto.negotiated.families]
        else:
            families = [f'{x[0]}/{x[1]}' for x in self.neighbor.families()]

        if len(families) > 1:
            joined = ' '.join(families)
            return f'[ {joined} ]'
        if len(families) == 1:
            return families[0]

        return ''

    def _connect(self) -> Generator[Message, None, None]:
        # Increment connection attempt counter
        self.connection_attempts += 1

        proto = Protocol(self)
        connected = False
        try:
            for connected in proto.connect():
                if connected:
                    break
                if self._teardown:
                    raise Stop
                # we want to come back as soon as possible
                yield _NOP
            self.proto = proto
        except Stop:
            # Connection failed
            if not connected and self.proto:
                self._close(
                    f'connection to {self.neighbor.session.peer_address}:{self.neighbor.session.connect} failed'
                )

            # A connection arrived before we could establish !
            if not connected or self.proto:
                yield _AWAKE
                raise Interrupted('connection failed') from None

    async def _connect_async(self) -> None:
        """Async version of _connect() - establishes connection using asyncio

        Raises:
            Interrupted: If connection fails or is interrupted

        Uses Protocol.connect_async() which properly integrates with asyncio
        instead of generator-based polling.
        """
        # Increment connection attempt counter
        self.connection_attempts += 1

        proto = Protocol(self)
        try:
            # Use async connect instead of generator
            connected = await proto.connect_async()

            if not connected:
                if self.proto:
                    self._close(
                        f'connection to {self.neighbor.session.peer_address}:{self.neighbor.session.connect} failed'
                    )
                raise Interrupted('connection failed')

            self.proto = proto

        except Stop:
            # Connection failed
            if self.proto:
                self._close(
                    f'connection to {self.neighbor.session.peer_address}:{self.neighbor.session.connect} failed'
                )
            raise Interrupted('connection failed') from None

    def _send_open(self) -> Generator[Message, None, None]:
        assert self.proto is not None
        for message in self.proto.new_open():
            yield message

    async def _send_open_async(self) -> Open:
        """Async version of _send_open() - sends OPEN message using async I/O"""
        assert self.proto is not None
        return await self.proto.new_open_async()

    def _read_open(self) -> Generator[Message, None, None]:
        assert self.proto is not None
        assert self.proto.connection is not None
        wait = getenv().bgp.openwait
        opentimer = ReceiveTimer(
            self.proto.connection.session,
            HoldTime(wait),
            1,
            1,
            'waited for open too long, we do not like stuck in active',
        )
        # Only yield if we have not the open, otherwise the reactor can run the other connection
        # which would be bad as we need to do the collission check without going to the other peer
        assert self.neighbor.session.peer_address is not None
        for message in self.proto.read_open(self.neighbor.session.peer_address.top()):
            opentimer.check_ka(message)
            yield message

    async def _read_open_async(self) -> Open:
        """Async version of _read_open() - reads OPEN message using async I/O"""
        assert self.proto is not None
        assert self.neighbor.session.peer_address is not None
        wait = getenv().bgp.openwait
        try:
            # Use asyncio timeout instead of ReceiveTimer
            message = await asyncio.wait_for(
                self.proto.read_open_async(self.neighbor.session.peer_address.top()), timeout=wait
            )
            return message
        except asyncio.TimeoutError:
            raise Notify(5, 1, 'waited for open too long, we do not like stuck in active') from None

    def _send_ka(self) -> Generator[Message, None, None]:
        assert self.proto is not None
        for message in self.proto.new_keepalive('OPENCONFIRM'):
            yield message

    async def _send_ka_async(self) -> None:
        """Async version of _send_ka() - sends KEEPALIVE message using async I/O"""
        assert self.proto is not None
        await self.proto.new_keepalive_async('OPENCONFIRM')

    def _read_ka(self) -> Generator[Message, None, None]:
        assert self.proto is not None
        assert self.recv_timer is not None
        # Start keeping keepalive timer
        for message in self.proto.read_keepalive():
            self.recv_timer.check_ka_timer(message)
            yield message

    async def _read_ka_async(self) -> None:
        """Async version of _read_ka() - reads KEEPALIVE message using async I/O"""
        assert self.proto is not None
        assert self.recv_timer is not None
        message = await self.proto.read_keepalive_async()
        self.recv_timer.check_ka_timer(message)

    def _establish(self) -> Generator[Message, None, None]:
        # try to establish the outgoing connection
        self.fsm.change(FSM.ACTIVE)

        if getenv().bgp.passive:
            while not self.proto:
                yield _NOP

        self.fsm.change(FSM.IDLE)

        if not self.proto:
            for action in self._connect():
                yield action
        self.fsm.change(FSM.CONNECT)
        assert self.proto is not None  # Set by _connect() or handle_connection()
        assert self.proto.connection is not None

        # normal sending of OPEN first ...
        if self.neighbor.session.local_as:
            for sent_open in self._send_open():
                if sent_open.SCHEDULING:
                    yield sent_open
            self.proto.negotiated.sent(cast(Open, sent_open))
            self.proto.negotiated.sent(cast(Open, sent_open))
            self.fsm.change(FSM.OPENSENT)

        # read the peer's open
        for received_open in self._read_open():
            if received_open.SCHEDULING:
                yield received_open
        self.proto.negotiated.received(cast(Open, received_open))
        self.proto.negotiated.received(cast(Open, received_open))

        self.proto.connection.msg_size = self.proto.negotiated.msg_size

        # if we mirror the ASN, we need to read first and send second
        if not self.neighbor.session.local_as:
            for sent_open in self._send_open():
                if sent_open.SCHEDULING:
                    yield sent_open
            self.proto.negotiated.sent(cast(Open, sent_open))
            self.proto.negotiated.sent(cast(Open, sent_open))
            self.fsm.change(FSM.OPENSENT)

        self.proto.validate_open()
        self.fsm.change(FSM.OPENCONFIRM)

        self.recv_timer = ReceiveTimer(self.proto.connection.session, self.proto.negotiated.holdtime, 4, 0)
        for message in self._send_ka():
            if message.SCHEDULING:
                yield message
        for message in self._read_ka():
            if message.SCHEDULING:
                yield message
        self.fsm.change(FSM.ESTABLISHED)
        self.stats['complete'] = time.time()

        # let the caller know that we were sucesfull
        yield _AWAKE

    async def _establish_async(self) -> None:
        """Async version of _establish() - establishes BGP connection using async I/O"""
        # try to establish the outgoing connection
        self.fsm.change(FSM.ACTIVE)

        if getenv().bgp.passive:
            while not self.proto:
                await asyncio.sleep(0)  # Yield control like _NOP

        self.fsm.change(FSM.IDLE)

        if not self.proto:
            # Use async connect (no generator bridging)
            await self._connect_async()
        self.fsm.change(FSM.CONNECT)
        assert self.proto is not None  # Set by _connect_async() or handle_connection()
        assert self.proto.connection is not None

        # normal sending of OPEN first ...
        if self.neighbor.session.local_as:
            sent_open = await self._send_open_async()
            self.proto.negotiated.sent(sent_open)
            self.proto.negotiated.sent(sent_open)
            self.fsm.change(FSM.OPENSENT)

        # read the peer's open
        received_open = await self._read_open_async()
        self.proto.negotiated.received(received_open)
        self.proto.negotiated.received(received_open)

        self.proto.connection.msg_size = self.proto.negotiated.msg_size

        # if we mirror the ASN, we need to read first and send second
        if not self.neighbor.session.local_as:
            sent_open = await self._send_open_async()
            self.proto.negotiated.sent(sent_open)
            self.proto.negotiated.sent(sent_open)
            self.fsm.change(FSM.OPENSENT)

        self.proto.validate_open()
        self.fsm.change(FSM.OPENCONFIRM)

        self.recv_timer = ReceiveTimer(self.proto.connection.session, self.proto.negotiated.holdtime, 4, 0)
        await self._send_ka_async()
        await self._read_ka_async()
        self.fsm.change(FSM.ESTABLISHED)
        self.stats['complete'] = time.time()

        # let the caller know that we were sucesfull (async version doesn't need return value)

    def _main(self) -> Generator[Message, None, None]:
        """Yield True if we want to come back to it asap, None if nothing urgent, and False if stopped"""
        assert self.proto is not None  # Set by _establish()
        assert self.proto.connection is not None
        assert self.recv_timer is not None  # Set by _establish()
        assert self.neighbor.rib is not None  # Initialized by neighbor

        if self._teardown:
            raise Notify(6, 3)

        self.neighbor.rib.incoming.clear()

        include_withdraw = False

        # Announce to the process BGP is up
        assert self.proto.connection is not None  # Must exist in established state
        log.info(
            lazymsg('peer.connected peer={p} connection={c}', p=self.id(), c=self.proto.connection.name()),
            'reactor',
        )
        self.stats['up'] += 1
        if self.neighbor.api and self.neighbor.api['neighbor-changes']:
            try:
                self.reactor.processes.up(self.neighbor)
            except ProcessError:
                # Process error during neighbor-up notification.
                # Note: broken() check in run() handles persistent process failures.
                raise Notify(6, 0, 'ExaBGP Internal error, sorry.') from None

        routes_per_iteration = 1 if self.neighbor.rate_limit > 0 else 25
        send_eor = not self.neighbor.manual_eor
        new_routes = None

        # Every last asm message should be re-announced on restart
        for family in self.neighbor.asm:
            if family in self.neighbor.families():
                self.neighbor.messages.appendleft(self.neighbor.asm[family])

        operational = None
        refresh = None
        command_eor = None
        number = 0
        refresh_enhanced = self.proto.negotiated.refresh == REFRESH.ENHANCED

        send_ka = KA(self.proto.connection.session, self.proto)

        # we need to make sure to send what was already issued by the api
        # from the previous time
        previous = self.neighbor.previous.changes if self.neighbor.previous else []
        current = self.neighbor.changes
        self.neighbor.rib.outgoing.replace_restart(previous, current)
        self.neighbor.previous = None

        self._delay.reset()
        while not self._teardown:
            # we are here following a configuration change
            if self._neighbor:
                # see what changed in the configuration
                previous = self._neighbor.previous.changes if self._neighbor.previous else []
                current = self._neighbor.changes
                self.neighbor.rib.outgoing.replace_reload(previous, current)
                # do not keep the previous routes in memory as they are not useful anymore
                self._neighbor.previous = None
                self._neighbor = None

            for message in self.proto.read_message():
                self.recv_timer.check_ka(message)

                if send_ka() is not False:
                    # we need and will send a keepalive
                    while send_ka() is None:
                        yield _AWAKE
                for counter_line in self.stats.changed_statistics():
                    log.info(lazymsg('statistics.changed info={counter_line}', counter_line=counter_line), 'statistics')

                # Received update
                if message.TYPE == Update.TYPE:
                    update = cast(Update, message)
                    number += 1
                    log.debug(lazymsg('update.received number={number}', number=number), self.id())

                    for nlri in update.nlris:
                        self.neighbor.rib.incoming.update_cache(Change(nlri, update.attributes))
                        log.debug(
                            lazyformat('update.nlri number=%d nlri=' % number, nlri, str),
                            self.id(),
                        )

                elif message.TYPE == RouteRefresh.TYPE:
                    rr = cast(RouteRefresh, message)
                    enhanced = rr.reserved == RouteRefresh.request
                    enhanced = enhanced and refresh_enhanced
                    self.resend(enhanced, (rr.afi, rr.safi))

                # SEND OPERATIONAL
                if self.neighbor.capability.operational.is_enabled():
                    if not operational:
                        new_operational = self.neighbor.messages.popleft() if self.neighbor.messages else None
                        if new_operational:
                            operational = self.proto.new_operational(new_operational, self.proto.negotiated)

                    if operational:
                        try:
                            next(operational)
                        except StopIteration:
                            operational = None
                # make sure that if some operational message are received via the API
                # that we do not eat memory for nothing
                elif self.neighbor.messages:
                    self.neighbor.messages.popleft()

                # SEND REFRESH
                if self.neighbor.capability.route_refresh:
                    if not refresh:
                        new_refresh = self.neighbor.refresh.popleft() if self.neighbor.refresh else None
                        if new_refresh:
                            refresh = self.proto.new_refresh(new_refresh)

                    if refresh:
                        try:
                            next(refresh)
                        except StopIteration:
                            refresh = None

                # Need to send update
                if not new_routes and self.neighbor.rib.outgoing.pending():
                    # Note: Peer controls timing (rate limit, priorities); Protocol handles sending
                    new_routes = self.proto.new_update(include_withdraw)

                if new_routes:
                    try:
                        for _ in range(routes_per_iteration):
                            # This can raise a NetworkError
                            next(new_routes)
                    except StopIteration:
                        new_routes = None
                        include_withdraw = True
                        # Fire flush callbacks - routes have been sent to wire
                        self.neighbor.rib.outgoing.fire_flush_callbacks()

                elif send_eor:
                    send_eor = False
                    for eor_msg in self.proto.new_eors():
                        if eor_msg.SCHEDULING:
                            yield eor_msg
                    log.debug(lazymsg('eor.sent.all'), self.id())

                # SEND MANUAL KEEPALIVE (only if we have no more routes to send)
                elif not command_eor and self.neighbor.eor:
                    new_eor = cast(Family, self.neighbor.eor.popleft())
                    command_eor = self.proto.new_eors(new_eor.afi, new_eor.safi)

                if command_eor:
                    try:
                        next(command_eor)
                    except StopIteration:
                        command_eor = None

                if (
                    new_routes
                    or not message.SCHEDULING  # Real message received (not NOP)
                    or self.neighbor.messages
                    or operational
                    or self.neighbor.eor
                    or command_eor
                ):
                    yield _AWAKE
                else:
                    yield _NOP

                # read_message will loop until new message arrives with NOP
                if self._teardown:
                    break

        # If graceful restart, silent shutdown
        if self.neighbor.capability.graceful_restart and self.proto.negotiated.sent_open.capabilities.announced(
            Capability.CODE.GRACEFUL_RESTART,
        ):
            log.error(lazymsg('session.closing reason=graceful_restart'), self.id())
            self._close('graceful restarted negotiated, closing without sending any notification')
            raise NetworkError('closing')

        # notify our peer of the shutdown
        raise Notify(6, self._teardown)

    async def _main_async(self) -> int:
        """Async version of _main() - main BGP message processing loop using async I/O"""
        assert self.proto is not None  # Set by _establish_async()
        assert self.proto.connection is not None  # Must exist in established state
        assert self.recv_timer is not None  # Set by _establish_async()
        assert self.neighbor.rib is not None  # Initialized by neighbor

        if self._teardown:
            raise Notify(6, 3)

        self.neighbor.rib.incoming.clear()

        include_withdraw = False

        # Announce to the process BGP is up
        log.info(
            lazymsg('peer.connected peer={p} connection={c}', p=self.id(), c=self.proto.connection.name()),
            'reactor',
        )
        self.stats['up'] += 1
        if self.neighbor.api and self.neighbor.api['neighbor-changes']:
            try:
                self.reactor.processes.up(self.neighbor)
            except ProcessError:
                raise Notify(6, 0, 'ExaBGP Internal error, sorry.') from None

        send_eor = not self.neighbor.manual_eor
        new_routes = None

        # Every last asm message should be re-announced on restart
        for family in self.neighbor.asm:
            if family in self.neighbor.families():
                self.neighbor.messages.appendleft(self.neighbor.asm[family])

        operational = None
        refresh = None
        command_eor = None
        number = 0
        refresh_enhanced = self.proto.negotiated.refresh == REFRESH.ENHANCED

        send_ka = KA(self.proto.connection.session, self.proto)

        # we need to make sure to send what was already issued by the api
        # from the previous time
        previous = self.neighbor.previous.changes if self.neighbor.previous else []
        current = self.neighbor.changes
        routes_per_iteration = 1 if self.neighbor.rate_limit > 0 else 25
        self.neighbor.rib.outgoing.replace_restart(previous, current)
        self.neighbor.previous = None

        self._delay.reset()
        log.debug(lazymsg('async.mainloop.started'), self.id())
        try:
            while not self._teardown:
                # we are here following a configuration change
                if self._neighbor:
                    # see what changed in the configuration
                    previous = self._neighbor.previous.changes if self._neighbor.previous else []
                    current = self._neighbor.changes
                    self.neighbor.rib.outgoing.replace_reload(previous, current)
                    # do not keep the previous routes in memory as they are not useful anymore
                    self._neighbor.previous = None
                    self._neighbor = None

                # Read message using async I/O with timeout to yield control periodically
                # This matches generator mode's behavior where read_message() yields NOP when blocked
                try:
                    message = await asyncio.wait_for(self.proto.read_message_async(), timeout=0.1)
                except asyncio.TimeoutError:
                    # No message within timeout - set to NOP and continue to outbound checks
                    # This matches generator mode where loop body executes even for NOP
                    message = _NOP
                    await asyncio.sleep(0)

                # NOP means no data - continue to outbound checks (matches generator mode)
                # Generator mode executes loop body for NOP, so we must too

                self.recv_timer.check_ka(message)

                if send_ka() is not False:
                    # we need and will send a keepalive
                    while send_ka() is None:
                        await asyncio.sleep(0)  # Yield control like _AWAKE
                for counter_line in self.stats.changed_statistics():
                    log.info(lazymsg('statistics.changed info={counter_line}', counter_line=counter_line), 'statistics')

                # Received update
                if message.TYPE == Update.TYPE:
                    update = cast(Update, message)
                    number += 1
                    log.debug(lazymsg('update.received number={number}', number=number), self.id())

                    for nlri in update.nlris:
                        self.neighbor.rib.incoming.update_cache(Change(nlri, update.attributes))
                        log.debug(
                            lazyformat('update.nlri number=%d nlri=' % number, nlri, str),
                            self.id(),
                        )

                elif message.TYPE == RouteRefresh.TYPE:
                    rr = cast(RouteRefresh, message)
                    enhanced = rr.reserved == RouteRefresh.request
                    enhanced = enhanced and refresh_enhanced
                    self.resend(enhanced, (rr.afi, rr.safi))

                # SEND OPERATIONAL
                if self.neighbor.capability.operational.is_enabled():
                    if not operational:
                        new_operational = self.neighbor.messages.popleft() if self.neighbor.messages else None
                        if new_operational:
                            # Use async version
                            await self.proto.new_operational_async(new_operational, self.proto.negotiated)
                            operational = None  # Mark as sent
                # make sure that if some operational message are received via the API
                # that we do not eat memory for nothing
                elif self.neighbor.messages:
                    self.neighbor.messages.popleft()

                # SEND REFRESH
                if self.neighbor.capability.route_refresh:
                    if not refresh:
                        new_refresh = self.neighbor.refresh.popleft() if self.neighbor.refresh else None
                        if new_refresh:
                            # Use async version
                            await self.proto.new_refresh_async(new_refresh)
                            refresh = None  # Mark as sent

                # Need to send update
                if not new_routes and self.neighbor.rib.outgoing.pending():
                    # Create the updates generator ONCE (matches sync version behavior)
                    log.debug(lazymsg('peer.update.generator.creating'), self.id())
                    new_routes = self.proto.new_update_async_generator(include_withdraw)

                if new_routes:
                    try:
                        # Process routes_per_iteration messages from the generator (matches sync version)
                        for _ in range(routes_per_iteration):
                            await new_routes.__anext__()
                            # Yield control to allow async API readers to process commands
                            # This is critical - without this, all API commands get buffered
                            # and processed together, causing wrong RIB state
                            await asyncio.sleep(0)
                    except StopAsyncIteration:
                        log.debug(lazymsg('peer.update.generator.exhausted'), self.id())
                        new_routes = None
                        include_withdraw = True
                        # Fire flush callbacks - routes have been sent to wire
                        self.neighbor.rib.outgoing.fire_flush_callbacks()

                elif send_eor:
                    send_eor = False
                    await self.proto.new_eors_async()
                    log.debug(lazymsg('eor.sent.all'), self.id())

                # SEND MANUAL KEEPALIVE (only if we have no more routes to send)
                elif not command_eor and self.neighbor.eor:
                    new_eor = cast(Family, self.neighbor.eor.popleft())
                    await self.proto.new_eors_async(new_eor.afi, new_eor.safi)
                    command_eor = None  # Mark as sent

                if (
                    new_routes
                    or not message.SCHEDULING  # Real message received (not NOP)
                    or self.neighbor.messages
                    or operational
                    or self.neighbor.eor
                    or command_eor
                ):
                    await asyncio.sleep(0)  # Yield control like _AWAKE
                else:
                    await asyncio.sleep(0.001)  # Slightly longer sleep for _NOP

                    # read_message will loop until new message arrives with NOP
                    if self._teardown:
                        log.debug(lazymsg('async.mainloop.exiting teardown={td}', td=self._teardown), self.id())
                        break

        except NetworkError as exc:
            # Normal network errors (connection closed, etc.) - log message only, no traceback
            log.debug(lazymsg('async.network.error error={exc}', exc=exc), self.id())
            raise
        except Exception as exc:
            # Unexpected exceptions - log message only
            log.error(lazymsg('async.mainloop.exception error={exc}', exc=exc), self.id())
            raise

        # If graceful restart, silent shutdown
        log.debug(
            lazymsg('async.mainloop.ended graceful_restart={gr}', gr=bool(self.neighbor.capability.graceful_restart)),
            self.id(),
        )
        if self.neighbor.capability.graceful_restart and self.proto.negotiated.sent_open.capabilities.announced(
            Capability.CODE.GRACEFUL_RESTART,
        ):
            log.error(lazymsg('session.closing reason=graceful_restart'), self.id())
            self._close('graceful restarted negotiated, closing without sending any notification')
            raise NetworkError('closing')

        # notify our peer of the shutdown
        raise Notify(6, self._teardown)

    def _run(self) -> Generator[Message, None, None]:
        """Yield True if we want the reactor to give us back the hand with the same peer loop, None if we do not have any more work to do"""
        try:
            for action in self._establish():
                yield action

            for action in self._main():
                yield action

        # CONNECTION FAILURE
        except NetworkError as network:
            # Check if maximum connection attempts reached
            if not self.can_reconnect():
                log.debug(
                    lazymsg('peer.connection.max_attempts_reached'),
                    self.id(),
                )
                self.stop()

            self._reset('closing connection', network)
            return

        # NOTIFY THE PEER OF AN ERROR
        except Notify as notify:
            if self.proto:
                try:
                    for notify_msg in self.proto.new_notification(notify):
                        if notify_msg.SCHEDULING:
                            yield notify_msg
                except (NetworkError, ProcessError):
                    log.error(lazymsg('notification.send.failed'), self.id())
                self._reset(f'notification sent ({notify.code},{notify.subcode})', notify)
            else:
                self._reset()

            if not self.can_reconnect():
                log.debug(
                    lazymsg('peer.connection.max_attempts_reached'),
                    self.id(),
                )
                self.stop()

            return

        # THE PEER NOTIFIED US OF AN ERROR
        except Notification as notification:
            # Check if maximum connection attempts reached
            if not self.can_reconnect():
                log.debug(
                    lazymsg('peer.connection.max_attempts_reached'),
                    self.id(),
                )
                self.stop()

            self._reset(
                f'notification received ({notification.code},{notification.subcode})',
                notification,
            )
            return

        # PROBLEM WRITING TO OUR FORKED PROCESSES
        except ProcessError as process:
            self._reset('process problem', process)
            return

        # ....
        except Interrupted as interruption:
            self._reset(f'connection received before we could fully establish one ({interruption})')
            return

        # UNHANDLED PROBLEMS
        except Exception as exc:
            # Those messages can not be filtered in purpose
            log.error(lazymsg('peer.exception.unhandled error={msg}', msg=format_exception(exc)), 'reactor')
            self._reset()
            return

    async def _run_async(self) -> None:
        """Async version of _run() - main peer loop using async/await"""
        try:
            await self._establish_async()
            await self._main_async()

        # CONNECTION FAILURE
        except NetworkError as network:
            # Check if maximum connection attempts reached
            if not self.can_reconnect():
                log.debug(
                    lazymsg('peer.connection.max_attempts_reached'),
                    self.id(),
                )
                self.stop()

            self._reset('closing connection', network)
            return

        # NOTIFY THE PEER OF AN ERROR
        except Notify as notify:
            if self.proto:
                try:
                    # Bridge to generator for notification sending (for now)
                    generator = self.proto.new_notification(notify)
                    try:
                        while True:
                            next(generator)
                            await asyncio.sleep(0)  # Yield control
                    except StopIteration:
                        pass
                except (NetworkError, ProcessError):
                    log.error(lazymsg('notification.send.failed'), self.id())
                self._reset(f'notification sent ({notify.code},{notify.subcode})', notify)
            else:
                self._reset()

            if not self.can_reconnect():
                log.debug(
                    lazymsg('peer.connection.max_attempts_reached'),
                    self.id(),
                )
                self.stop()

            return

        # THE PEER NOTIFIED US OF AN ERROR
        except Notification as notification:
            # Check if maximum connection attempts reached
            if not self.can_reconnect():
                log.debug(
                    lazymsg('peer.connection.max_attempts_reached'),
                    self.id(),
                )
                self.stop()

            self._reset(
                f'notification received ({notification.code},{notification.subcode})',
                notification,
            )
            return

        # PROBLEM WRITING TO OUR FORKED PROCESSES
        except ProcessError as process:
            self._reset('process problem', process)
            return

        # ....
        except Interrupted as interruption:
            self._reset(f'connection received before we could fully establish one ({interruption})')
            return

        # UNHANDLED PROBLEMS
        except Exception as exc:
            # Those messages can not be filtered in purpose
            log.error(lazymsg('peer.exception.unhandled error={msg}', msg=format_exception(exc)), 'reactor')
            self._reset()
            return

    # loop

    def run(self) -> Message:
        if self.reactor.processes.broken(self.neighbor):
            # Process respawning handled by Processes._handle_problem().
            # This branch handles cases where respawning failed or was disabled.
            log.error(lazymsg('process.lost action=stopping'), 'processes')
            if self.reactor.processes.terminate_on_error:
                self.reactor.shutdown()
            else:
                self.stop()
            return _DONE

        if self.generator and self.generator is not False:
            try:
                # This generator only stops when it raises
                # otherwise return one of the scheduling messages
                assert isinstance(self.generator, Generator)
                return next(self.generator)
            except StopIteration:
                # Trying to run a closed loop, no point continuing
                self.generator = None
                if self._restart:
                    return _NOP
                return _DONE

        elif self.generator is None:
            if self.fsm in [FSM.OPENCONFIRM, FSM.ESTABLISHED]:
                log.debug(lazymsg('peer.stopping reason=other_connection_established'), self.id())
                self.generator = False
                return _NOP
            if self._delay.backoff():
                return _NOP
            if self._restart:
                log.debug(lazymsg('peer.connection.initializing peer={p}', p=self.id()), 'reactor')
                self.generator = self._run()
                return _NOP  # make sure we go through a clean loop
            return _DONE

        # generator is False - peer is closed and should not restart
        return _DONE

    async def run_async(self) -> None:
        """Async entry point for peer - runs the peer FSM using async/await"""
        if self.reactor.processes.broken(self.neighbor):
            # Process respawning handled by Processes._handle_problem().
            # This branch handles cases where respawning failed or was disabled.
            log.error(lazymsg('process.lost action=stopping'), 'processes')
            if self.reactor.processes.terminate_on_error:
                self.reactor.shutdown()
            else:
                self.stop()
            return

        # Wait for restart conditions
        while True:
            if self.fsm in [FSM.OPENCONFIRM, FSM.ESTABLISHED]:
                log.debug(lazymsg('peer.stopping reason=other_connection_established'), self.id())
                await asyncio.sleep(0.1)  # Wait a bit before checking again
                continue

            if self._delay.backoff():
                await asyncio.sleep(0.1)  # Backoff delay
                continue

            if self._restart:
                log.debug(lazymsg('peer.connection.initializing peer={p}', p=self.id()), 'reactor')
                await self._run_async()
                # After _run_async completes, check if we should restart
                if not self._restart:
                    break
                await asyncio.sleep(0.1)  # Clean loop delay
            else:
                break

    def start_async_task(self) -> None:
        """Start the async peer task (for async mode)"""
        if self._async_task is None or self._async_task.done():
            self._async_task = asyncio.create_task(self.run_async())

    def stop_async_task(self) -> None:
        """Stop the async peer task (for async mode)"""
        if self._async_task and not self._async_task.done():
            self._async_task.cancel()

    def cli_data(self) -> dict[str, Any]:
        peer: defaultdict = defaultdict(lambda: None)

        have_peer = self.proto is not None
        have_open = self.proto and self.proto.negotiated.received_open

        if have_peer:
            assert self.proto is not None  # Guarded by have_peer
            peer.update(
                {
                    'multi-session': self.proto.negotiated.multisession,
                    'operational': self.proto.negotiated.operational,
                },
            )

        if have_open:
            assert self.proto is not None  # Guarded by have_open
            assert self.proto.negotiated.received_open is not None
            assert self.proto.negotiated.sent_open is not None
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
                },
            )

        cap = self.neighbor.capability
        capabilities: dict[str, tuple[TriState, TriState]] = {
            'asn4': (cap.asn4, TriState.from_bool(peer['asn4'])),
            'route-refresh': (
                TriState.from_bool(bool(cap.route_refresh)),
                TriState.from_bool(peer['route-refresh']),
            ),
            'multi-session': (
                cap.multi_session,
                TriState.from_bool(peer['multi-session']),
            ),
            'operational': (
                cap.operational,
                TriState.from_bool(peer['operational']),
            ),
            'add-path': (
                TriState.from_bool(bool(cap.add_path)),
                TriState.from_bool(peer['add-path']),
            ),
            'extended-message': (
                cap.extended_message,
                TriState.from_bool(peer['extended-message']),
            ),
            'graceful-restart': (
                TriState.from_bool(bool(cap.graceful_restart)),
                TriState.from_bool(peer['graceful-restart']),
            ),
        }

        families: dict[tuple[AFI, SAFI], tuple[bool, TriState, TriState, TriState]] = {}
        for family in self.neighbor.families():
            common: TriState
            send_addpath: TriState
            recv_addpath: TriState
            if have_open:
                assert self.proto is not None  # Guarded by have_open
                common = TriState.from_bool(family in self.proto.negotiated.families)
                send_addpath = TriState.from_bool(self.proto.negotiated.addpath.send(*family))
                recv_addpath = TriState.from_bool(self.proto.negotiated.addpath.receive(*family))
            else:
                common = TriState.UNSET
                send_addpath = TriState.UNSET if family in self.neighbor.addpaths() else TriState.FALSE
                recv_addpath = TriState.UNSET if family in self.neighbor.addpaths() else TriState.FALSE
            families[family] = (True, common, send_addpath, recv_addpath)

        messages = {}
        total_sent = 0
        total_rcvd = 0
        for message in ('open', 'notification', 'keepalive', 'update', 'refresh'):
            sent = self.stats['send-{}'.format(message)]
            rcvd = self.stats['receive-{}'.format(message)]
            total_sent += sent
            total_rcvd += rcvd
            messages[message] = (sent, rcvd)
        messages['total'] = (total_sent, total_rcvd)

        return {
            'down': int(self.stats['reset'] - self.stats['creation']),
            'duration': (int(time.time() - self.stats['complete']) if self.stats['complete'] else 0),
            'local-address': str(self.neighbor.session.local_address),
            'peer-address': str(self.neighbor.session.peer_address),
            'local-as': int(self.neighbor.session.local_as),
            'peer-as': int(self.neighbor.session.peer_as),
            'local-id': str(self.neighbor.session.router_id),
            'peer-id': None if peer['peer-id'] is None else str(peer['router-id']),
            'local-hold': int(self.neighbor.hold_time),
            'peer-hold': None if peer['hold-time'] is None else int(peer['hold-time']),
            'state': self.fsm.name(),
            'capabilities': capabilities,
            'families': families,
            'messages': messages,
        }
