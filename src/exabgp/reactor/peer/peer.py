"""BGP peer management and FSM implementation.

This module implements the BGP Finite State Machine (FSM) for managing
peer connections. Each Peer object represents a BGP neighbor and handles
connection establishment, message exchange, and session teardown.

Key classes:
    Peer: Main class managing a single BGP neighbor connection
    FSMRunner: Encapsulates generator-based FSM state
    Stats: Tracks peer statistics (messages sent/received, uptime)

FSM States (RFC 4271):
    IDLE: Initial state, waiting to start connection
    ACTIVE: Listening for incoming connection
    CONNECT: Attempting outbound connection
    OPENSENT: OPEN message sent, waiting for peer's OPEN
    OPENCONFIRM: OPENs exchanged, waiting for KEEPALIVE
    ESTABLISHED: Session active, exchanging UPDATE messages

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar, Generator, Iterator, NoReturn, cast

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.loop import Reactor
    from exabgp.reactor.network.incoming import Incoming
    from exabgp.reactor.peer.context import PeerContext
    from exabgp.reactor.peer.handlers import RouteRefreshHandler, UpdateHandler

# import traceback
from exabgp.bgp.fsm import FSM
from exabgp.bgp.message import Message, NotificationReceived, Notify, Open
from exabgp.bgp.message.open.capability import REFRESH, Capability, Negotiated
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.timer import ReceiveTimer
from exabgp.debug.report import format_exception
from exabgp.environment import getenv
from exabgp.logger import lazyexc, lazymsg, log
from exabgp.protocol.family import FamilyTuple
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.delay import Delay
from exabgp.reactor.keepalive import KA
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.protocol import Protocol, UpdateSender
from exabgp.reactor.timing import LoopTimer, timed_async
from exabgp.rib.route import Route
from exabgp.util.enumeration import TriState


# RFC 4724 4.1 and 4.2 pull in opposite directions on the very first OPEN a process sends.
# If this run follows an earlier one we are the Restarting Speaker and MUST set the Restart
# State bit; if it is a genuine first start we are the Receiving Speaker and MUST NOT.
# Nothing on this box can tell the two apart: exabgp keeps no state between runs, and the
# pid file is optional, is not per neighbor, and says nothing about the session. So the
# first OPEN claims the restart. The bit only asks the peer not to wait for our End-of-RIB
# before advertising to us, so that is the cheap way to be wrong, and it is right in the
# case which costs something. Every later OPEN of this process is a reconnection rather
# than a restart, and _establish() clears the flag so that it says so.
FORCE_GRACEFUL = True


# RFC 5492 3: the NOTIFICATION a speaker which predates capabilities sends for them
UNSUPPORTED_OPTIONAL_PARAMETER = (2, 4)


class Interrupted(Exception):
    pass


class Stop(Exception):
    pass


# ======================================================================== Counter


class Stats(dict[str, Any]):
    """Tracks peer statistics with change notification.

    Stores message counters, timestamps, and FSM state.
    Yields formatted strings for changed values via changed_statistics().
    """

    # one underscore, not two: mypyc does not mangle a private name the way Python does
    _format: ClassVar[dict[str, Callable[[Any], str]]] = {
        'complete': lambda t: 'time {}'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(t)))
    }

    def __init__(self, *args: tuple[Any, ...]) -> None:
        dict.__init__(self, args)
        self._changed: set[str] = set()

    def __setitem__(self, key: str, val: Any) -> None:
        dict.__setitem__(self, key, val)
        self._changed.add(key)

    def changed_statistics(self) -> Iterator[str]:
        for name in self._changed:
            formater = self._format.get(name, lambda v: f'counter {v}')
            yield f'statistics for {name} {formater(self[name])}'
        self._changed = set()


# ======================================================================== FSMRunner


class FSMRunner:
    """Encapsulates peer generator state machine.

    Replaces the old tri-state: None (ready), False (terminated), Generator (running).
    """

    def __init__(self) -> None:
        self._generator: Generator[Message, None, None] | None = None
        self._terminated: bool = False

    @property
    def running(self) -> bool:
        """True if generator is active."""
        return self._generator is not None

    @property
    def terminated(self) -> bool:
        """True if peer should not restart."""
        return self._terminated

    def set(self, gen: Generator[Message, None, None]) -> None:
        """Start running a generator."""
        self._generator = gen
        self._terminated = False

    def clear(self) -> None:
        """Stop generator, allow restart."""
        self._generator = None

    def terminate(self) -> None:
        """Stop generator, prevent restart."""
        self._generator = None
        self._terminated = True

    def reset(self) -> None:
        """Clear terminated flag (for reestablish)."""
        self._terminated = False

    def advance(self) -> Message:
        """Call next() on generator. Raises StopIteration when done."""
        if self._generator is None:
            raise StopIteration
        return next(self._generator)


# ======================================================================== Peer


class Peer:
    """Manages a single BGP peer connection and FSM.

    Handles the complete lifecycle of a BGP session:
    - Connection establishment (active/passive)
    - OPEN message exchange and capability negotiation
    - UPDATE message sending/receiving
    - KEEPALIVE timer management
    - Graceful restart and session teardown

    Supports both sync (generator) and async (asyncio) operation modes.
    """

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
                'receive-operational': 0,
                'send-operational': 0,
                'receive-prefixes': 0,
                'receive-withdraws': 0,
            },
        )

        self.fsm_runner: FSMRunner = FSMRunner()
        self._async_task: asyncio.Task[None] | None = None  # For async mode

        # The peer should restart after a stop
        self._restart: bool = True
        # Whether the next OPEN we send claims the RFC 4724 Restart State bit. True until
        # this process has held a session with this neighbor, and again after an operator
        # asked for the session to be re-established.
        self._restarted: bool = FORCE_GRACEFUL

        # We have been asked to teardown the session with this code
        # The NOTIFICATION to close the session with, once one is asked for.  It was the
        # Cease subcode as an int, which made a subcode of 0 look like no teardown at all
        self._teardown: Notify | None = None
        # the families our End-of-RIB went out for on this session (RFC 7313 4)
        self._end_of_rib_sent: set[FamilyTuple] = set()
        # The Cease the operator disabled the session with, None while it is enabled.  It is
        # also the teardown disable() asked for, so enable() can tell that one from any other.
        self._disable: Notify | None = Notify(6, 2) if neighbor.shutdown else None

        self._delay: Delay = Delay()
        self.recv_timer: ReceiveTimer | None = None
        # RFC 4724 4.2: the peer's Restart Time, counting from the loss of its Graceful
        # Restart session, and the session its stale routes were received on
        self._restart_timer: asyncio.TimerHandle | None = None
        self._restart_negotiated: Negotiated | None = None
        # RFC 5492 3: the peer refused an OPEN for its Capabilities Optional Parameter
        # (Unsupported Optional Parameter, 2/4), so our OPENs to it carry none from now on
        self.capabilities_refused = False

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
                'receive-operational': 0,
                'send-operational': 0,
                'receive-prefixes': 0,
                'receive-withdraws': 0,
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
        # RFC 4724 4.2 is about the TCP session being lost; a NOTIFICATION ends the
        # session without Graceful Restart
        if isinstance(error, NetworkError):
            self._retain_for_restart()
        self._close(message, error)

        if not self._restart or self.neighbor.ephemeral:
            self.fsm_runner.terminate()
            return

        self.fsm_runner.clear()
        self._teardown = None
        self.neighbor.reset_rib()

        # If we are restarting, and the neighbor definition is different, update the neighbor
        if self._neighbor:
            self.neighbor = self._neighbor
            self._neighbor = None

    def _retain_for_restart(self) -> None:
        """RFC 4724 4.2: keep a Graceful Restart peer's routes as stale for its Restart Time."""
        if self.proto is None or self.fsm != FSM.ESTABLISHED:
            return
        negotiated = self.proto.negotiated
        received = negotiated.received_open
        if received is None or not received.capabilities.announced(Capability.CODE.GRACEFUL_RESTART):
            return
        graceful = received.capabilities[Capability.CODE.GRACEFUL_RESTART]
        # a mocked session answers every attribute; only the capability says it is the capability
        if graceful.ID != Capability.CODE.GRACEFUL_RESTART:
            return
        restart = cast(Graceful, graceful)
        self.neighbor.rib.incoming.retain_for_restart(list(restart.families()))
        self._restart_negotiated = negotiated
        self._cancel_restart_timer()
        self._restart_timer = asyncio.get_running_loop().call_later(restart.restart_time, self._restart_time_expired)
        log.info(lazymsg('graceful-restart.retained restart-time={t}', t=restart.restart_time), self.id())

    def _cancel_restart_timer(self) -> None:
        if self._restart_timer is not None:
            self._restart_timer.cancel()
            self._restart_timer = None

    def _restart_time_expired(self) -> None:
        """RFC 4724 4.2: no new session within the Restart Time, the stale routes go."""
        self._restart_timer = None
        expired = self.neighbor.rib.incoming.expire_restart()
        log.info(lazymsg('graceful-restart.expired removed={n}', n=len(expired)), self.id())
        self.tell_api_withdrawn(expired, self._restart_negotiated)

    def _resume_incoming(self) -> None:
        """A session starts: keep what a restart retained for the families its new OPEN allows.

        RFC 4724 4.2: the stale routes of a family go at once when the new OPEN has no
        Graceful Restart capability, does not name the family, or clears its Forwarding
        State bit for it.
        """
        self._cancel_restart_timer()
        incoming = self.neighbor.rib.incoming
        assert self.proto is not None
        received = self.proto.negotiated.received_open
        graceful: Graceful | None = None
        if received is not None and received.capabilities.announced(Capability.CODE.GRACEFUL_RESTART):
            graceful = cast(Graceful, received.capabilities[Capability.CODE.GRACEFUL_RESTART])
        kept: set[FamilyTuple] = set()
        removed: list[Route] = []
        for family in incoming.restarting_families():
            if graceful is not None and graceful.get(family, 0) & Graceful.FORWARDING_STATE:
                kept.add(family)
                continue
            removed.extend(incoming.end_restart(family))
        incoming.start_session(kept)
        self.tell_api_withdrawn(removed, self._restart_negotiated)

    def tell_api_withdrawn(self, routes: list[Route], negotiated: Negotiated | None) -> None:
        """Tell the API processes that routes the peer sent are gone, as a withdrawal would."""
        if not routes or negotiated is None or not self.neighbor.api:
            return
        api = self.neighbor.api
        if not api['receive-update'] or not (api['receive-parsed'] or api['receive-consolidate']):
            return
        collection = UpdateCollection([], [route.nlri for route in routes], AttributeCollection())
        update = Update.from_collection(collection)
        self.reactor.processes.message(Message.CODE.UPDATE, self, 'receive', update, b'', b'', negotiated)

    def _stop(self, message: str) -> None:
        self.fsm_runner.clear()
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

    def stopping(self) -> bool:
        """The peer has been told to go away and is not coming back.

        reestablish() sets a teardown too, and that peer is returning, so the teardown
        alone does not say this. Only a peer which will not restart is on its way out.
        """
        return self._teardown is not None and not self._restart

    def stop(self) -> None:
        self._teardown = Notify(6, 3)
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
                'receive-operational': 0,
                'send-operational': 0,
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

    def resend(self, enhanced: bool, family: FamilyTuple | None = None) -> None:
        if self.neighbor.rib:
            outgoing = self.neighbor.rib.outgoing
            held_back = self._borr_held_back(enhanced, family)
            if not held_back:
                outgoing.resend(enhanced, family)
            else:
                requested = set(outgoing.families) if family is None else {family}
                for each in requested:
                    outgoing.resend(each not in held_back, each)
        self._delay.reset()

    def _borr_held_back(self, enhanced: bool, family: FamilyTuple | None) -> set[FamilyTuple]:
        """The families a BoRR may not be sent for yet.

        RFC 7313 4: a speaker doing Graceful Restart "MUST NOT send a BoRR for an <AFI, SAFI>
        to a neighbor before it sends the EoR".  Those families are replayed without the
        markers, as a plain refresh.
        """
        if not enhanced or self.proto is None or self.proto.negotiated.sent_open is None:
            return set()
        if not self.proto.negotiated.sent_open.capabilities.announced(Capability.CODE.GRACEFUL_RESTART):
            return set()
        requested = set(self.neighbor.rib.outgoing.families) if family is None else {family}
        return requested - self._end_of_rib_sent

    def reestablish(self, restart_neighbor: 'Neighbor' | None = None) -> None:
        # we want to tear down the session and re-establish it
        self._teardown = Notify(6, 3)
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

            # If peer is not ESTABLISHED, update RIB directly since the main loop
            # isn't running to process the _neighbor variable later.
            # GitHub issue #1126: stale adj-rib when neighbor offline during reload
            if self.fsm != FSM.ESTABLISHED and self.neighbor.rib:
                previous = restart_neighbor.previous.routes if restart_neighbor.previous else []
                current = restart_neighbor.routes
                self.neighbor.rib.outgoing.replace_reload(previous, current)
                restart_neighbor.previous = None
                self._neighbor = None  # Prevent double-processing when peer connects

    def _announce_up_to_the_api(self) -> None:
        if not (self.neighbor.api and self.neighbor.api['neighbor-changes']):
            return
        try:
            self.reactor.processes.up(self.neighbor)
        except ProcessError:
            # RFC 4486 Out of Resources: we cannot carry on for want of a local resource,
            # the helper process.  This was (6, 0), which IANA lists as Reserved
            raise Notify(6, 8, 'the API process could not be told the session is up') from None

    def teardown(self, notify: Notify, restart: bool = True) -> None:
        self._restart = restart
        self._teardown = notify
        self._delay.reset()

    def disabled(self) -> bool:
        return self._disable is not None

    def disable(self, notify: Notify) -> None:
        """Close the session with `notify` and do not open another until enable().

        The peer stays in the reactor, so its RIB, and what the API announces to it while it
        is down, is sent once it is enabled again (issue #1013).
        """
        self._disable = notify
        self.teardown(notify)

    def enable(self) -> None:
        # a disable the session has not acted on yet is withdrawn, not carried out later
        # against the next session
        if self._teardown is not None and self._teardown is self._disable:
            self._teardown = None
        self._disable = None
        self._delay.reset()

    def _park(self) -> None:
        """What _reset would do, for a disabled peer which has no session to reset.

        A teardown asked for meanwhile, by disable() or by a reload's reestablish(), has
        nothing to close, and left pending it would close the first session after enable().
        The neighbour a reload handed over is taken now, not after that session.
        """
        self._teardown = None
        if self._neighbor:
            self.neighbor = self._neighbor
            self._neighbor = None

    def socket(self) -> int:
        if self.proto:
            return self.proto.fd()
        return -1

    def handle_connection(self, connection: 'Incoming') -> Iterator[bool] | None:
        log.debug(lazymsg('peer.fsm.state state={s}', s=self.fsm.name()), self.id())

        # a peer whose neighbour has been removed from the configuration cannot serve this
        # connection: its next turn drops it from the reactor. Accepting one anyway left
        # the socket owned by an object nobody held any more, stuck in CLOSE_WAIT.
        if self.stopping():
            log.debug(
                lazymsg('peer.connection.rejected connection={c} reason=peer_removed', c=connection.name()),
                self.id(),
            )
            return connection.notification(6, 3, b'no session configured for the peer')

        # RFC 4486 4: a connection the speaker "decides to disallow" is Connection Rejected
        if self._disable is not None:
            log.debug(
                lazymsg('peer.connection.rejected connection={c} reason=disabled', c=connection.name()),
                self.id(),
            )
            return connection.notification(6, 5, b'the session is administratively disabled')

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

            if bytes(remote_id) < bytes(local_id):
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
        self.fsm_runner.clear()
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

    async def _connect(self) -> None:
        """Establishes connection using asyncio

        Raises:
            Interrupted: If connection fails or is interrupted
        """
        # Increment connection attempt counter
        self.connection_attempts += 1

        proto = Protocol(self)
        try:
            # Use async connect instead of generator
            connected = await proto.connect()

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

    async def _send_open(self) -> Open:
        """Sends OPEN message using async I/O"""
        assert self.proto is not None
        return await self.proto.new_open()

    async def _read_open(self) -> Open:
        """Reads OPEN message using async I/O"""
        assert self.proto is not None
        assert self.neighbor.session.peer_address is not None
        wait = getenv().bgp.openwait
        try:
            # Use asyncio timeout instead of ReceiveTimer
            message = await asyncio.wait_for(
                self.proto.read_open(self.neighbor.session.peer_address.top()), timeout=wait
            )
            return message
        except asyncio.TimeoutError:
            # RFC 4271 8.2.2: the hold timer expiring in OpenSent sends Hold Timer Expired.
            # (5, 1) is RFC 6608's for a message which arrived, and here none did
            raise Notify(4, 0, f'no OPEN received within {wait} seconds') from None

    async def _send_ka(self) -> None:
        """Sends KEEPALIVE message using async I/O"""
        assert self.proto is not None
        await self.proto.new_keepalive('OPENCONFIRM')

    async def _read_ka(self) -> None:
        """Reads KEEPALIVE message using async I/O"""
        assert self.proto is not None
        assert self.recv_timer is not None
        message = await self.proto.read_keepalive()
        self.recv_timer.check_ka_timer(message)

    async def _establish(self) -> None:
        """Establishes BGP connection using async I/O"""
        async with timed_async(f'peer_establish_{self.id()}', warn_threshold_ms=5000):
            # try to establish the outgoing connection
            self.fsm.change(FSM.ACTIVE)

            if getenv().bgp.passive:
                while not self.proto:
                    await asyncio.sleep(0)  # Yield control while nothing is read

            self.fsm.change(FSM.IDLE)

            if not self.proto:
                await self._connect()
            self.fsm.change(FSM.CONNECT)
            assert self.proto is not None  # Set by _connect() or handle_connection()
            assert self.proto.connection is not None

            # normal sending of OPEN first ...
            if self.neighbor.session.local_as:
                sent_open = await self._send_open()
                self.proto.negotiated.sent(sent_open)
                self.fsm.change(FSM.OPENSENT)

            # read the peer's open
            received_open = await self._read_open()
            self.proto.negotiated.received(received_open)

            self.proto.connection.msg_size = self.proto.negotiated.msg_size

            # if we mirror the ASN, we need to read first and send second
            if not self.neighbor.session.local_as:
                sent_open = await self._send_open()
                self.proto.negotiated.sent(sent_open)
                self.fsm.change(FSM.OPENSENT)

            self.proto.validate_open()
            self.fsm.change(FSM.OPENCONFIRM)

            self.recv_timer = ReceiveTimer(self.proto.connection.session, self.proto.negotiated.holdtime, 4, 0)
            await self._send_ka()
            await self._read_ka()
            self.fsm.change(FSM.ESTABLISHED)
            self.stats['complete'] = time.time()
            # RFC 4724 4.2: whatever this process may have been a restart of, it has now
            # peered. A session we re-establish from here is a reconnection and not a
            # restart of this speaker, so the next OPEN must not claim the Restart State
            # bit. Only reestablish(), where an operator asked for one, sets it again.
            self._restarted = False

        # let the caller know that we were sucesfull (async version doesn't need return value)

    # -------------------------------------------------------------------------
    # Helper methods for _main()
    # -------------------------------------------------------------------------

    async def _send_operational_messages(self) -> None:
        """Send operational messages from the neighbor's message queue."""
        assert self.proto is not None, 'Protocol must be established'
        if self.neighbor.capability.operational.is_enabled():
            new_operational = self.neighbor.messages.popleft() if self.neighbor.messages else None
            if new_operational:
                await self.proto.new_operational(new_operational, self.proto.negotiated)
        # Make sure that if some operational message are received via the API
        # that we do not eat memory for nothing
        elif self.neighbor.messages:
            self.neighbor.messages.popleft()

    async def _send_refresh_messages(self) -> None:
        """Send route refresh messages from the neighbor's refresh queue."""
        assert self.proto is not None, 'Protocol must be established'
        if self.neighbor.capability.route_refresh.is_enabled():
            new_refresh = self.neighbor.refresh.popleft() if self.neighbor.refresh else None
            if new_refresh:
                await self.proto.new_refresh(new_refresh)

    async def _send_route_updates(
        self,
        new_routes: UpdateSender | None,
        include_withdraw: bool,
        routes_per_iteration: int,
    ) -> tuple[UpdateSender | None, bool]:
        """Send route updates from the outgoing RIB.

        Returns:
            Tuple of (updated new_routes generator, updated include_withdraw flag)
        """
        assert self.proto is not None, 'Protocol must be established'
        if not new_routes and not self._holding_for_commands() and self.neighbor.rib.outgoing.pending():
            log.debug(lazymsg('peer.update.generator.creating'), self.id())
            new_routes = self.proto.new_update_generator(include_withdraw)

        if new_routes:
            for _ in range(routes_per_iteration):
                if not await new_routes.step():
                    log.debug(lazymsg('peer.update.generator.exhausted'), self.id())
                    new_routes = None
                    include_withdraw = True
                    self.neighbor.rib.outgoing.fire_flush_callbacks()
                    break
                # Yield control to allow async API readers to process commands
                await asyncio.sleep(0)

        return (new_routes, include_withdraw)

    async def _send_eor_messages(
        self,
        send_eor: bool,
        new_routes: UpdateSender | None,
    ) -> bool:
        """Send End-of-RIB markers.

        Returns:
            Updated send_eor flag
        """
        assert self.proto is not None, 'Protocol must be established'
        # an End-of-RIB says the routes before it are all there, which they are not yet
        if self._holding_for_commands():
            return send_eor

        if not new_routes and send_eor:
            send_eor = False
            await self.proto.new_eors()
            self._end_of_rib_sent.update(self.proto.negotiated.families)
            log.debug(lazymsg('eor.sent.all'), self.id())

        # Manual EOR from API commands
        elif self.neighbor.eor:
            new_eor = self.neighbor.eor.popleft()
            await self.proto.new_eors(new_eor.afi, new_eor.safi)
            self._end_of_rib_sent.add((new_eor.afi, new_eor.safi))

        return send_eor

    def _holding_for_commands(self) -> bool:
        """Whether to leave the RIB alone while the reactor applies API commands.

        The commands a helper wrote together are applied in one pass, but their
        coroutines yield to the loop: a batch started then would carry the first of
        them without the rest. A command waiting for this very flush (sync) is not
        kept waiting, or it and the peer would each wait for the other.
        """
        if not self.reactor.asynchronous.applying_commands:
            return False
        return not self.neighbor.rib.outgoing.flush_awaited()

    def _teardown_asked(self) -> bool:
        """Read teardown state afresh after another task may have changed it.

        Testing the attribute directly in a loop narrows it to None across awaits.
        The compiled build enforces that stale narrowing when another task sets a Notify.
        """
        return self._teardown is not None

    def _has_pending_work(
        self,
        new_routes: UpdateSender | None,
        message: Message | None,
    ) -> bool:
        """Check if there's pending work that requires immediate attention."""
        return bool(new_routes or message is not None or self.neighbor.messages or self.neighbor.eor)

    def _session_context(self, routes_per_iteration: int) -> PeerContext:
        """The context the inbound message handlers share for this session."""
        assert self.proto is not None
        refresh_enhanced = self.proto.negotiated.refresh == REFRESH.ENHANCED

        from exabgp.reactor.peer.context import PeerContext

        return PeerContext(
            proto=self.proto,
            neighbor=self.neighbor,
            negotiated=self.proto.negotiated,
            refresh_enhanced=refresh_enhanced,
            routes_per_iteration=routes_per_iteration,
            peer_id=self.id(),
            stats=self.stats,
        )

    def _announce_session_up(self) -> None:
        """Log the session up, count it, and tell the API processes."""
        assert self.proto is not None
        assert self.proto.connection is not None
        log.info(
            lazymsg('peer.connected peer={p} connection={c}', p=self.id(), c=self.proto.connection.name()),
            'reactor',
        )
        self.stats['up'] += 1
        self._announce_up_to_the_api()

    def _reannounce_asm(self) -> None:
        """Re-announce ASM messages on restart, for the families this neighbor has."""
        for family in self.neighbor.asm:
            if family in self.neighbor.families():
                self.neighbor.messages.appendleft(self.neighbor.asm[family])

    def _restore_outgoing_rib(self) -> None:
        """Initialize the outgoing RIB with the routes of the previous configuration."""
        previous = self.neighbor.previous.routes if self.neighbor.previous else []
        current = self.neighbor.routes
        self.neighbor.rib.outgoing.replace_restart(previous, current)
        self.neighbor.previous = None

    def _apply_reload(self) -> None:
        """Move the outgoing RIB to the routes of a configuration reloaded while established."""
        if self._neighbor:
            pending = self._neighbor
            previous = pending.previous.routes if pending.previous else []
            current = pending.routes
            self.neighbor.rib.outgoing.replace_reload(previous, current)
            pending.previous = None
            self._neighbor = None

    async def _read_message_or_none(self) -> Message | None:
        """Read the next message, or None when none arrived within 100ms."""
        assert self.proto is not None
        message: Message | None
        try:
            message = await asyncio.wait_for(self.proto.read_message(), timeout=0.1)
        except asyncio.TimeoutError:
            message = None
            await asyncio.sleep(0)
        return message

    def _log_changed_statistics(self) -> None:
        """Log every statistic which changed since the last time we asked."""
        for counter_line in self.stats.changed_statistics():
            log.info(lazymsg('statistics.changed info={counter_line}', counter_line=counter_line), 'statistics')

    async def _handle_inbound(
        self,
        ctx: PeerContext,
        message: Message,
        update_handler: UpdateHandler,
        route_refresh_handler: RouteRefreshHandler,
    ) -> None:
        """Give a received message to the handler which takes it, if any does."""
        if update_handler.can_handle(message):
            await update_handler.handle_async(ctx, message)
        elif route_refresh_handler.can_handle(message):
            await route_refresh_handler.handle_async(ctx, message)

    def _raise_session_end(self) -> NoReturn:
        """Close quietly if Graceful Restart was negotiated, else raise the teardown which ended the loop."""
        assert self.proto is not None
        assert self.proto.negotiated.sent_open is not None
        # Graceful restart handling
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

        assert self._teardown is not None
        raise self._teardown

    async def _main(self) -> int:
        """Main BGP message processing loop using async I/O.

        Uses extracted helper methods for cleaner code structure.
        """
        assert self.proto is not None
        assert self.proto.connection is not None
        assert self.recv_timer is not None
        assert self.proto.negotiated.sent_open is not None

        if self._teardown is not None:
            raise self._teardown

        # Initialize session state, keeping what a Graceful Restart retained (RFC 4724 4.2)
        self._resume_incoming()
        self._end_of_rib_sent = set()
        send_eor = not self.neighbor.manual_eor
        routes_per_iteration = 1 if self.neighbor.rate_limit > 0 else 25

        # Create context for handlers
        ctx = self._session_context(routes_per_iteration)

        # Announce to the process BGP is up
        self._announce_session_up()
        self._reannounce_asm()
        send_ka = KA(self.proto.connection.session, self.proto)
        self._restore_outgoing_rib()

        self._delay.reset()
        log.debug(lazymsg('async.mainloop.started'), self.id())

        await self._main_loop(ctx, send_ka, routes_per_iteration, send_eor)
        self._raise_session_end()

    async def _main_loop(self, ctx: PeerContext, send_ka: KA, routes_per_iteration: int, send_eor: bool) -> None:
        """Read, handle and send until a teardown is asked for, or an exception ends the session."""
        assert self.proto is not None
        assert self.recv_timer is not None
        include_withdraw = False
        new_routes: UpdateSender | None = None

        from exabgp.reactor.peer.handlers import UpdateHandler, RouteRefreshHandler

        update_handler = UpdateHandler()
        route_refresh_handler = RouteRefreshHandler(self.resend)

        # Timing instrumentation for peer message loop
        peer_loop_timer = LoopTimer(f'peer_main_{self.id()}', warn_threshold_ms=50)

        try:
            while not self._teardown_asked():
                peer_loop_timer.start()

                # Handle configuration reload
                self._apply_reload()
                ctx.neighbor = self.neighbor

                # Read message with timeout
                message = await self._read_message_or_none()

                # Keepalive handling
                self.recv_timer.check_ka(message)
                await send_ka.send_if_needed()

                # Log statistics changes
                self._log_changed_statistics()

                # Process inbound messages using handlers
                if message is not None:
                    await self._handle_inbound(ctx, message, update_handler, route_refresh_handler)

                # Send outbound messages using async helpers
                await self._send_operational_messages()
                await self._send_refresh_messages()
                new_routes, include_withdraw = await self._send_route_updates(
                    new_routes, include_withdraw, routes_per_iteration
                )
                send_eor = await self._send_eor_messages(send_eor, new_routes)

                # Yield control based on pending work
                if self._has_pending_work(new_routes, message):
                    await asyncio.sleep(0)
                else:
                    await asyncio.sleep(0.001)
                    if self._teardown_asked():
                        log.debug(lazymsg('async.mainloop.exiting teardown={td}', td=str(self._teardown)), self.id())
                        break

                # Log timing for this iteration
                peer_loop_timer.stop()
                peer_loop_timer.log_if_slow()

        except NetworkError as network:
            # Separate names keep compiled handlers from sharing incompatible exception types.
            log.debug(lazymsg('async.network.error error={exc}', exc=network), self.id())
            raise
        except Exception as exc:
            log.error(lazyexc('async.mainloop.exception error={exc}', exc), self.id())
            raise

    async def _run(self) -> None:
        """Main peer loop using async/await"""
        try:
            await self._establish()
            await self._main()

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
            # RFC 5492 3: a peering refused for want of a capability "SHOULD NOT be
            # re-established automatically", the peer would only be refused again
            if (notify.code, notify.subcode) == Notify.UNSUPPORTED_CAPABILITY:
                self.stop()
            if self.proto:
                try:
                    await self.proto.new_notification(notify)
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
        except NotificationReceived as notification:
            if (notification.code, notification.subcode) == UNSUPPORTED_OPTIONAL_PARAMETER:
                self.capabilities_refused = True
                log.warning(lazymsg('open.capabilities.refused action=retry-without-capabilities'), self.id())
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

    async def run(self) -> None:
        """Entry point for peer - runs the peer FSM using async/await"""
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

            # a disabled peer waits here, with no session.  A stop() still ends the loop, and
            # a connection accepted just before the disable runs on, to be sent its Cease
            if self._disable is not None and self._restart and self.proto is None:
                self._park()
                await asyncio.sleep(0.1)
                continue

            if self._delay.backoff():
                await asyncio.sleep(0.1)  # Backoff delay
                continue

            if self._restart:
                log.debug(lazymsg('peer.connection.initializing peer={p}', p=self.id()), 'reactor')
                await self._run()
                # _reset clears restartable teardowns; a remaining request ends this task.
                if self._teardown_asked():
                    break
                await asyncio.sleep(0.1)  # Clean loop delay
            else:
                break

    def start_async_task(self) -> None:
        """Start the async peer task"""
        if self._async_task is None or self._async_task.done():
            self._async_task = asyncio.create_task(self.run())

    def stop_async_task(self) -> None:
        """Stop the async peer task (for async mode)"""
        if self._async_task and not self._async_task.done():
            self._async_task.cancel()

    def cli_data(self) -> dict[str, Any]:
        peer: defaultdict[str, Any] = defaultdict(lambda: None)

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
            'route-refresh': (cap.route_refresh, TriState.from_bool(peer['route-refresh'])),
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

        families: dict[FamilyTuple, tuple[bool, TriState, TriState, TriState]] = {}
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

        prefixes = {
            'received': self.stats['receive-prefixes'],
            'withdrawn': self.stats['receive-withdraws'],
        }

        return {
            'down': int(self.stats['reset'] - self.stats['creation']),
            'duration': (int(time.time() - self.stats['complete']) if self.stats['complete'] else 0),
            'local-address': str(self.neighbor.session.local_address),
            'peer-address': str(self.neighbor.session.peer_address),
            'local-as': int(self.neighbor.session.local_as),
            'peer-as': int(self.neighbor.session.peer_as),
            'local-id': str(self.neighbor.session.router_id),
            'peer-id': None if peer['peer-id'] is None else str(peer['peer-id']),
            'local-hold': int(self.neighbor.hold_time),
            'peer-hold': None if peer['hold-time'] is None else int(peer['hold-time']),
            'state': 'DISABLED' if self._disable is not None and self.fsm == FSM.IDLE else self.fsm.name(),
            'capabilities': capabilities,
            'families': families,
            'messages': messages,
            'prefixes': prefixes,
        }
