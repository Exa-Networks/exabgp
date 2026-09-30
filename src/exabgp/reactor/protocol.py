"""protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import traceback
from typing import TYPE_CHECKING, Any, cast
from collections.abc import Iterator

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.network.error import NotifyError
    from exabgp.reactor.network.incoming import Incoming
    from exabgp.reactor.peer import Peer

# ================================================================ Registration
#

from exabgp.bgp.message import (
    EOR,
    KeepAlive,
    Message,
    Notification,
    NotificationReceived,
    Notify,
    Open,
    Operational,
    Update,
)
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import RouterID, Version
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.open.capability import Capabilities, Capability, Negotiated
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.logger import lazymsg, log

# from exabgp.reactor.network.error import NotifyError
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.network.outgoing import Outgoing
from exabgp.rib.flow_validation import validate_flows
from exabgp.util.types import Buffer
from exabgp.bgp.message.message import MessageCode

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

# RFC 4271 6.1 Message Header Error, and the two subcodes the reactor answers itself
# because the header is read before any decoder sees the message.
MESSAGE_HEADER_ERROR = 1
BAD_MESSAGE_TYPE = 3


class Protocol:
    decode: bool = True

    def __init__(self, peer: 'Peer') -> None:
        self.peer: 'Peer' = peer
        self.neighbor: 'Neighbor' = peer.neighbor
        self.negotiated: Negotiated = Negotiated.make_negotiated(self.neighbor, Direction.IN)
        self.connection: 'Incoming' | Outgoing | None = None

        if self.neighbor.session.connect:
            self.port: int = self.neighbor.session.connect
        elif os.environ.get('exabgp.tcp.port', '').isdigit():
            self.port = int(os.environ['exabgp.tcp.port'])
        elif os.environ.get('exabgp_tcp_port', '').isdigit():
            self.port = int(os.environ['exabgp_tcp_port'])
        else:
            self.port = 179

    def fd(self) -> int:
        if self.connection is None:
            return -1
        return self.connection.fd()

    def _session(self) -> str:
        """Return session identifier for logging. Requires connection to be established."""
        assert self.connection is not None
        return self.connection.session()

    @property
    def _api(self) -> dict[str, Any]:
        """Return neighbor API config."""
        return self.neighbor.api

    # Note: We use self.peer.neighbor for consistency - both reference the same object
    # but self.peer.neighbor is used throughout to maintain clear ownership semantics.

    def me(self, message: str) -> str:
        return f'{self.peer.neighbor.session.peer_address}/{self.peer.neighbor.session.peer_as} {message}'

    def accept(self, incoming: 'Incoming') -> Protocol:
        self.connection = incoming

        if self._api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        # very important - as we use this function on __init__
        return self

    async def connect(self) -> bool:
        """Establish connection using asyncio.

        Returns:
            True if connection successful, False otherwise
        """
        # allows to test the protocol code using modified StringIO with a extra 'pending' function
        if self.connection:
            return True

        assert self.neighbor.session.peer_address is not None
        local = (
            self.neighbor.session.md5_ip.top()
            if not self.neighbor.session.auto_discovery and self.neighbor.session.md5_ip
            else ''
        )
        peer = self.neighbor.session.peer_address.top()
        afi = self.neighbor.session.peer_address.afi
        md5 = self.neighbor.session.md5_password
        md5_base64 = self.neighbor.session.md5_base64
        ttl_out = self.neighbor.session.outgoing_ttl
        itf = self.neighbor.session.source_interface
        # TCP-AO (RFC 5925)
        tcp_ao_keyid = self.neighbor.session.tcp_ao_keyid
        tcp_ao_algorithm = self.neighbor.session.tcp_ao_algorithm
        tcp_ao_password = self.neighbor.session.tcp_ao_password
        tcp_ao_base64 = self.neighbor.session.tcp_ao_base64
        self.connection = Outgoing(
            afi,
            peer,
            local,
            self.port,
            md5,
            md5_base64,
            ttl_out,
            itf,
            tcp_ao_keyid,
            tcp_ao_algorithm,
            tcp_ao_password,
            tcp_ao_base64,
            incoming_ttl=self.neighbor.session.incoming_ttl,
        )

        # Use async establish instead of generator
        connected = await self.connection.establish_async()

        if not connected:
            return False

        if self._api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        if not local:
            self.neighbor.session.local_address = IP.from_string(self.connection.local)
            if self.neighbor.session.router_id is None and self.neighbor.session.local_address.afi == AFI.ipv4:
                self.neighbor.session.router_id = RouterID(self.neighbor.session.local_address.top())

        return True

    def close(self, reason: str = 'protocol closed, reason unspecified') -> None:
        if self.connection:
            log.debug(lazymsg('protocol.close reason={r}', r=reason), self._session())
            self.peer.stats['down'] += 1

            self.connection.close()
            self.connection = None

    def _to_api(self, direction: str, message: Any, raw: bytes) -> None:
        # the API entries are the lists of processes which asked, so only their truth is kept
        packets = bool(self._api['{}-packets'.format(direction)])
        parsed = bool(self._api['{}-parsed'.format(direction)])
        consolidate = bool(self._api['{}-consolidate'.format(direction)])
        neg: Negotiated = self.negotiated

        if consolidate:
            if packets:
                self.peer.reactor.processes.message(
                    message.ID, self.peer, direction, message, raw[:19], raw[19:], negotiated=neg
                )
            else:
                self.peer.reactor.processes.message(message.ID, self.peer, direction, message, b'', b'', negotiated=neg)
        else:
            if packets:
                self.peer.reactor.processes.packets(self.peer.neighbor, direction, message.ID, raw[:19], raw[19:], neg)
            if parsed:
                self.peer.reactor.processes.message(message.ID, self.peer, direction, message, b'', b'', negotiated=neg)

    async def write(self, message: Any, negotiated: Negotiated) -> None:
        """Send BGP message using async I/O."""
        assert self.connection is not None
        raw: bytes = message.pack_message(negotiated)

        code: str = 'send-{}'.format(Message.CODE.short(message.ID))
        self.peer.stats[code] += 1

        await self.connection.writer_async(raw)

        # told after the write, not before it: a process which waits on this to
        # know a route has gone out gets an answer which is true, and a write
        # which raised is no longer reported as a message we sent
        if self._api.get(code, False):
            self._to_api('send', message, raw)

    async def send(self, raw: bytes) -> None:
        """Send raw BGP message using async I/O."""
        assert self.connection is not None
        code: str = 'send-{}'.format(Message.CODE.short(Message.CODE.of(raw[18])))
        self.peer.stats[code] += 1

        await self.connection.writer_async(raw)

        if self._api.get(code, False):
            # Parse the raw bytes to get an Update for API
            update = Update(raw[19:])
            update.parse(self.negotiated)
            self._to_api('send', update, raw)

    # Read from network .......................................................

    async def read_message(self) -> Message | None:
        """Read one BGP message using async I/O, or None when there is nothing to process."""
        assert self.connection is not None

        # Read message using async I/O
        length, msg_id, header, body, notify = await self.connection.reader_async()

        # internal issue
        if notify:
            raise self._header_error(notify, msg_id, header, body)

        # RFC 4271 6.1: if the Type field is not recognised the Error Subcode MUST be Bad
        # Message Type.  Message.unpack answers the same 1/3 but is never reached for these
        # codes, as the statistics counter and the API fan-out below both index the type,
        # so the answer has to be given here.  It used to be 1/0, which names neither the
        # right error nor the right message.
        if msg_id not in Message.CODE.MESSAGES:
            # and the Data field MUST contain the erroneous Type field, the octet itself
            raise Notify(MESSAGE_HEADER_ERROR, BAD_MESSAGE_TYPE, f'type {msg_id.value}', data=bytes([msg_id.value]))

        if not length:
            return None

        for_api = self._count_received(msg_id, header, body)

        message = self._decode(msg_id, body)

        revalidated = self._check_update(message)

        if for_api:
            self._tell_api_received(message, header, body, revalidated)

        if message.ID == Message.CODE.NOTIFICATION:
            raise NotificationReceived(cast(Notification, message))

        # RFC 7606 2: "attribute discard" drops the malformed attribute and processes the
        # rest of the UPDATE. The Discard marker the parser leaves behind records that it
        # happened, for the API; it is not a reason to ignore the routes beside it.
        return message

    def _count_received(self, msg_id: MessageCode, header: Buffer, body: Buffer) -> bool:
        """Log and count a message received, return if the API asked for its type."""
        log.debug(lazymsg('message.received type={t}', t=Message.CODE.name(msg_id)), self._session())

        code = 'receive-{}'.format(Message.CODE.short(msg_id))
        self.peer.stats[code] += 1
        # the API entries are the lists of processes which asked, so only their truth is kept
        for_api = bool(self._api.get(code, False))

        # the raw packets are told before decoding, so a message which fails to decode is seen
        if for_api and self._api['receive-packets'] and not self._api['receive-consolidate']:
            self.peer.reactor.processes.packets(
                self.peer.neighbor, 'receive', msg_id, bytes(header), bytes(body), self.negotiated
            )
        return for_api

    def _check_update(self, message: Message) -> list[UpdateCollection]:
        """Classify the OTC of an UPDATE and return the flows its routes revalidated."""
        if message.ID != Message.CODE.UPDATE:
            return []
        # the one decoder registered for the type is Update's, and it returns an Update
        update = cast(Update, message)
        update.data.classify_otc(self.negotiated)
        return validate_flows(self.neighbor, update.data)

    def _decode(self, msg_id: MessageCode, body: Buffer) -> Message:
        """Decode the body of a message, a decoder failing on it is a header error."""
        try:
            return Message.unpack(msg_id, body, self.negotiated)
        except (KeyboardInterrupt, SystemExit, Notify):
            raise
        except Exception as exc:
            log.debug(lazymsg('message.decode.failed type={t}', t=msg_id), self._session())
            log.debug(lazymsg('message.decode.error error={e}', e=str(exc)), self._session())
            log.debug(lazymsg('message.decode.traceback trace={t}', t=traceback.format_exc()), self._session())
            raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id.value) from None

    def _header_error(self, notify: 'NotifyError', msg_id: MessageCode, header: Buffer, body: Buffer) -> Notify:
        """Turn an error found reading the header into the Notify to raise, telling the API."""
        consolidate = self._api['receive-consolidate']
        parsed = self._api['receive-parsed']
        packets = self._api['receive-packets']
        code = 'receive-{}'.format(Message.CODE.NOTIFICATION.SHORT)
        # Convert NotifyError to Notify for API and exception.  Connection fills the
        # Data field where an RFC defines it (RFC 4271 6.1, the erroneous Length field
        # of a Bad Message Length); its sentence stays in our log
        notify_msg = Notify(notify.code, notify.subcode, str(notify), data=notify.data or None)
        if self._api.get(code, False):
            if consolidate:
                self.peer.reactor.processes.notification(
                    self.peer.neighbor,
                    'receive',
                    notify_msg.notification,
                    bytes(header),
                    bytes(body),
                    self.negotiated,
                )
            elif parsed:
                self.peer.reactor.processes.notification(
                    self.peer.neighbor, 'receive', notify_msg.notification, b'', b'', self.negotiated
                )
            elif packets:
                self.peer.reactor.processes.packets(
                    self.peer.neighbor, 'receive', msg_id, bytes(header), bytes(body), self.negotiated
                )
        return notify_msg

    def _tell_api_received(
        self, message: Message, header: Buffer, body: Buffer, revalidated: list[UpdateCollection]
    ) -> None:
        """Tell the API processes about a message received, the way they asked to hear of it."""
        processes = self.peer.reactor.processes
        if self._api['receive-consolidate']:
            processes.message(message.ID, self.peer, 'receive', message, bytes(header), bytes(body), self.negotiated)
        elif self._api['receive-parsed']:
            processes.message(message.ID, self.peer, 'receive', message, b'', b'', self.negotiated)
        # RFC 8955 6: flow specifications the unicast routes of this UPDATE made, or unmade, feasible
        for change in revalidated:
            update = Update.from_collection(change)
            processes.message(Message.CODE.UPDATE, self.peer, 'receive', update, b'', b'', self.negotiated)

    def validate_open(self) -> None:
        error: tuple[int, int, str] | None = self.negotiated.validate(self.neighbor)
        if error is not None:
            raise Notify(*error)

        unsupported = self.negotiated.unsupported_capability()
        if unsupported is not None:
            raise unsupported

        if self._api['negotiated']:
            self.peer.reactor.processes.negotiated(self.peer.neighbor, self.negotiated)

        if self.negotiated.mismatch and self.connection is not None:
            log.warning(
                lazymsg('negotiation.family.mismatch count={c}', c=len(self.negotiated.mismatch)),
                self._session(),
            )
            for reason, (afi, safi) in self.negotiated.mismatch:
                current_afi, current_reason, current_safi = afi, reason, safi
                log.warning(
                    lazymsg(
                        'negotiation.family.unconfigured reason={r} afi={a} safi={s}',
                        r=current_reason,
                        a=current_afi,
                        s=current_safi,
                    ),
                    self._session(),
                )

    async def read_open(self, ip: str) -> Open:
        """Read OPEN message using async I/O."""
        while True:
            received_open = await self.read_message()
            if received_open is not None:
                break

        if received_open.ID != Message.CODE.OPEN:
            raise Notify(5, 1, f'{received_open} where the OPEN was expected')

        log.debug(lazymsg('open.received message={m}', m=received_open), self._session())
        return cast(Open, received_open)

    async def read_keepalive(self) -> KeepAlive:
        """Read KEEPALIVE message using async I/O."""
        while True:
            message = await self.read_message()
            if message is not None:
                break

        if message.ID != Message.CODE.KEEPALIVE:
            raise Notify(5, 2)

        return cast(KeepAlive, message)

    #
    # Sending message to peer
    #

    async def new_open(self) -> Open:
        """Create and send OPEN message using async I/O."""
        assert self.connection is not None
        assert self.neighbor.session.router_id is not None
        if self.neighbor.session.local_as:
            local_as = self.neighbor.session.open_asn()
        elif self.negotiated.received_open:
            local_as = self.negotiated.received_open.asn
            if local_as == AS_TRANS and Capability.CODE.FOUR_BYTES_ASN in self.negotiated.received_open.capabilities:
                local_as = self.negotiated.received_open.capabilities.four_octet_asn()
        else:
            raise RuntimeError('no ASN available for the OPEN message')

        # RFC 5492 3: SHOULD retry without the Capabilities Optional Parameter once refused
        if self.peer.capabilities_refused:
            capabilities = Capabilities()
        else:
            capabilities = Capabilities().new(self.neighbor, self.peer._restarted, local_as=local_as)
        sent_open = Open.make_open(
            Version(4), local_as, self.neighbor.hold_time, self.neighbor.session.router_id, capabilities
        )

        # we do not buffer open message in purpose
        await self.write(sent_open, self.negotiated)

        log.debug(lazymsg('open.sent message={m}', m=sent_open), self._session())
        return sent_open

    async def new_keepalive(self, comment: str = '') -> KeepAlive:
        """Create and send KEEPALIVE message using async I/O."""
        assert self.connection is not None
        keepalive: KeepAlive = KeepAlive()

        await self.write(keepalive, self.negotiated)

        log.debug(
            lazymsg('keepalive.sent comment={c}', c=comment if comment else 'none'),
            self._session(),
        )

        return keepalive

    async def new_notification(self, notification: Notify) -> Notify:
        """Send BGP NOTIFICATION message."""
        assert self.connection is not None
        await self.write(notification.notification, self.negotiated)
        log.debug(
            lazymsg(
                'notification.sent code={c} subcode={sc} {d}',
                c=notification.code,
                sc=notification.subcode,
                # str(), not the Data field decoded: RFC 7313 puts a whole message, marker
                # of 0xFF octets included, in the Data field of an Invalid Message Length
                d=str(notification),
            ),
            self._session(),
        )
        return notification

    def new_update_generator(self, include_withdraw: bool) -> UpdateSender:
        """The pending UPDATE messages, sent one per `UpdateSender.step()`.

        Each step awaits one send, so the event loop runs other tasks between messages.
        """
        return UpdateSender(self, include_withdraw)

    async def new_update(self, include_withdraw: bool) -> int:
        """Send BGP UPDATE messages (runs to completion), and say how many were sent."""
        assert self.connection is not None
        log.debug(lazymsg('update.started'), self._session())
        updates = self.neighbor.rib.outgoing.updates(
            self.neighbor.group_updates,
            paths_limit=self.negotiated.paths_limit or None,
            negotiated=self.negotiated,
        )
        number: int = 0
        for update in updates:
            current_update = update
            log.debug(
                lazymsg('update.processing update={upd}', upd=current_update),
                self._session(),
            )
            for message in update.messages(self.negotiated, include_withdraw):
                number += 1
                current_msg = message
                log.debug(
                    lazymsg('update.message.sending num={num} msg={msg}', num=number, msg=repr(current_msg)),
                    self._session(),
                )
                await self.send(message)
        if number:
            log.debug(lazymsg('update.sent count={n}', n=number), self._session())
        log.debug(lazymsg('update.completed count={count}', count=number), self._session())
        return number

    async def new_eor(self, afi: AFI, safi: SAFI) -> EOR:
        """Send BGP End-of-RIB marker."""
        assert self.connection is not None
        eor: EOR = EOR.make_eor(afi, safi)
        await self.write(eor, self.negotiated)
        log.debug(lazymsg('eor.sent afi={a} safi={s}', a=afi, s=safi), self._session())
        return eor

    async def new_eors(self, afi: AFI = AFI.undefined, safi: SAFI = SAFI.undefined) -> None:
        """Send End-of-RIB markers for all families."""
        if self.negotiated.families:
            families = self.negotiated.families if (afi, safi) == (AFI.undefined, SAFI.undefined) else [(afi, safi)]
            for eor_afi, eor_safi in families:
                await self.new_eor(eor_afi, eor_safi)
        else:
            # If not sending EOR, send keepalive
            await self.new_keepalive('EOR')

    async def new_operational(self, operational: Operational, negotiated: Negotiated) -> Operational:
        """Send BGP OPERATIONAL message."""
        assert self.connection is not None
        await self.write(operational, negotiated)
        log.debug(lazymsg('operational.sent message={m}', m=str(operational)), self._session())
        return operational

    async def new_refresh(self, refresh: RouteRefresh) -> RouteRefresh:
        """Send BGP ROUTE-REFRESH message."""
        assert self.connection is not None
        await self.write(refresh, self.negotiated)
        log.debug(lazymsg('refresh.sent message={m}', m=str(refresh)), self._session())
        return refresh


class UpdateSender:
    """Sends the pending UPDATE messages of the outgoing RIB, one message per step.

    This was an async generator, which mypyc 1.20 does not compile. Its protocol is not
    used either: a compiled coroutine raising StopAsyncIteration fails with a TypeError.
    `step()` says instead whether it sent a message, False once every one has gone.

    Like a generator, nothing is read from the RIB before the first step, and an exception
    out of a step ends the sending.
    """

    def __init__(self, protocol: Protocol, include_withdraw: bool) -> None:
        self._protocol = protocol
        self._include_withdraw = include_withdraw
        self._updates: Iterator[UpdateCollection | RouteRefresh] | None = None
        self._messages: Iterator[bytes] = iter(())
        self._number = 0
        self._done = False

    def _start(self) -> Iterator[UpdateCollection | RouteRefresh]:
        protocol = self._protocol
        assert protocol.connection is not None
        log.debug(lazymsg('update.generator.started'), protocol._session())
        return iter(
            protocol.neighbor.rib.outgoing.updates(
                protocol.neighbor.group_updates,
                paths_limit=protocol.negotiated.paths_limit or None,
                negotiated=protocol.negotiated,
            )
        )

    def _next_message(self, updates: Iterator[UpdateCollection | RouteRefresh]) -> bytes | None:
        message = next(self._messages, None)
        if message is not None:
            return message
        # the RIB iterator is finite and each turn consumes one update from it
        for update in updates:
            self._messages = update.messages(self._protocol.negotiated, self._include_withdraw)
            message = next(self._messages, None)
            if message is not None:
                return message
        return None

    def _finish(self) -> None:
        self._done = True
        session = self._protocol._session()
        if self._number:
            log.debug(lazymsg('update.sent count={n}', n=self._number), session)
        log.debug(lazymsg('update.generator.completed count={count}', count=self._number), session)

    async def step(self) -> bool:
        """Send the next UPDATE message, False when there is none left."""
        if self._done:
            return False
        if self._updates is None:
            self._updates = self._start()
        try:
            message = self._next_message(self._updates)
            if message is None:
                self._finish()
                return False
            self._number += 1
            log.debug(
                lazymsg('update.message.sending num={num} msg={msg}', num=self._number, msg=repr(message)),
                self._protocol._session(),
            )
            await self._protocol.send(message)
        except BaseException:
            # a generator which raised is finished: it never sends the rest
            self._done = True
            raise
        return True
