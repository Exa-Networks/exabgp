"""protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import traceback
from typing import TYPE_CHECKING, Any, cast
from collections.abc import AsyncGenerator

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.network.incoming import Incoming
    from exabgp.reactor.peer import Peer

# ================================================================ Registration
#

from exabgp.bgp.message import _NOP, EOR, KeepAlive, Message, Notification, Notify, Open, Operational, Update
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Negotiated
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.logger import lazymsg, log

# from exabgp.reactor.network.error import NotifyError
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.network.outgoing import Outgoing

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

_UPDATE = UpdateCollection([], [], AttributeCollection())
_OPERATIONAL = Operational(0x00)


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

        from exabgp.environment import getenv

        self.log_routes: bool = peer.neighbor.adj_rib_in or getenv().log.routes

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
        self.connection = Outgoing(afi, peer, local, self.port, md5, md5_base64, ttl_out, itf)

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
        packets: bool = self._api['{}-packets'.format(direction)]
        parsed: bool = self._api['{}-parsed'.format(direction)]
        consolidate: bool = self._api['{}-consolidate'.format(direction)]
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
                self.peer.reactor.processes.packets(
                    self.peer.neighbor, direction, int(message.ID), raw[:19], raw[19:], neg
                )
            if parsed:
                self.peer.reactor.processes.message(message.ID, self.peer, direction, message, b'', b'', negotiated=neg)

    async def write(self, message: Any, negotiated: Negotiated) -> None:
        """Send BGP message using async I/O."""
        assert self.connection is not None
        raw: bytes = message.pack_message(negotiated)

        code: str = 'send-{}'.format(Message.CODE.short(message.ID))
        self.peer.stats[code] += 1
        if self._api.get(code, False):
            self._to_api('send', message, raw)

        await self.connection.writer_async(raw)

    async def send(self, raw: bytes) -> None:
        """Send raw BGP message using async I/O."""
        assert self.connection is not None
        code: str = 'send-{}'.format(Message.CODE.short(raw[18]))
        self.peer.stats[code] += 1
        if self._api.get(code, False):
            # Parse the raw bytes to get an Update for API
            update = Update(raw[19:])
            update.parse(self.negotiated)
            self._to_api('send', update, raw)

        await self.connection.writer_async(raw)

    # Read from network .......................................................

    async def read_message(self) -> Message:
        """Read BGP message using async I/O."""
        assert self.connection is not None
        packets = self._api['receive-packets']
        consolidate = self._api['receive-consolidate']
        parsed = self._api['receive-parsed']

        # Read message using async I/O
        length, msg_id, header, body, notify = await self.connection.reader_async()

        # internal issue
        if notify:
            code = 'receive-{}'.format(Message.CODE.NOTIFICATION.SHORT)
            # Convert NotifyError to Notify for API and exception
            notify_msg = Notify(notify.code, notify.subcode, str(notify))
            if self._api.get(code, False):
                if consolidate:
                    self.peer.reactor.processes.notification(
                        self.peer.neighbor, 'receive', notify_msg, bytes(header), bytes(body), self.negotiated
                    )
                elif parsed:
                    self.peer.reactor.processes.notification(
                        self.peer.neighbor, 'receive', notify_msg, b'', b'', self.negotiated
                    )
                elif packets:
                    self.peer.reactor.processes.packets(
                        self.peer.neighbor, 'receive', msg_id, bytes(header), bytes(body), self.negotiated
                    )
            raise notify_msg

        if msg_id not in Message.CODE.MESSAGES:
            raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id)

        if not length:
            return _NOP

        current_msg_id = msg_id
        log.debug(
            lazymsg('message.received type={t}', t=Message.CODE.name(current_msg_id)),
            self._session(),
        )

        code = 'receive-{}'.format(Message.CODE.short(msg_id))
        self.peer.stats[code] += 1
        for_api = self._api.get(code, False)

        if for_api and packets and not consolidate:
            self.peer.reactor.processes.packets(
                self.peer.neighbor, 'receive', msg_id, bytes(header), bytes(body), self.negotiated
            )

        if msg_id == Message.CODE.UPDATE:
            if not self.neighbor.adj_rib_in and not (for_api or self.log_routes) and not (parsed or consolidate):
                return _UPDATE

        try:
            message = Message.unpack(msg_id, body, self.negotiated)
        except (KeyboardInterrupt, SystemExit, Notify):
            raise
        except Exception as exc:
            current_msg_id = msg_id
            log.debug(lazymsg('message.decode.failed type={t}', t=current_msg_id), self._session())
            current_exc = exc
            log.debug(lazymsg('message.decode.error error={e}', e=str(current_exc)), self._session())
            log.debug(lazymsg('message.decode.traceback trace={t}', t=traceback.format_exc()), self._session())
            raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id) from None
            # raise Notify(5,0,'unknown message received')

        if message.TYPE == Update.TYPE:
            # Both Update and EOR have TYPE == Update.TYPE
            # Update: use .data to get parsed collection
            # EOR: has .attributes and .nlris directly
            if isinstance(message, Update):
                # Note: TREAT_AS_WITHDRAW handling is done at the Update level
                # The UpdateCollection (message.data) already tracks which NLRIs
                # are withdraws via the announces vs withdraws lists
                pass

        if for_api:
            if consolidate:
                self.peer.reactor.processes.message(
                    msg_id, self.peer, 'receive', message, bytes(header), bytes(body), self.negotiated
                )
            elif parsed:
                self.peer.reactor.processes.message(msg_id, self.peer, 'receive', message, b'', b'', self.negotiated)

        if message.TYPE == Notification.TYPE:
            raise cast(Notification, message)

        if isinstance(message, Update) and Attribute.CODE.INTERNAL_DISCARD in message.data.attributes:
            return _NOP
        else:
            return message

    def validate_open(self) -> None:
        error: tuple[int, int, str] | None = self.negotiated.validate(self.neighbor)
        if error is not None:
            raise Notify(*error)

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
            if not received_open.SCHEDULING:  # Real message (not NOP)
                break

        if received_open.TYPE != Open.TYPE:
            raise Notify(
                5,
                1,
                'The first packet received is not an open message ({})'.format(received_open),
            )

        log.debug(lazymsg('open.received message={m}', m=received_open), self._session())
        return cast(Open, received_open)

    async def read_keepalive(self) -> KeepAlive:
        """Read KEEPALIVE message using async I/O."""
        while True:
            message = await self.read_message()
            if not message.SCHEDULING:  # Real message (not NOP)
                break

        if message.TYPE != KeepAlive.TYPE:
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
            local_as = self.neighbor.session.local_as
        elif self.negotiated.received_open:
            local_as = self.negotiated.received_open.asn
        else:
            raise RuntimeError('no ASN available for the OPEN message')

        sent_open = Open.make_open(
            Version(4),
            local_as,
            self.neighbor.hold_time,
            self.neighbor.session.router_id,
            Capabilities().new(self.neighbor, self.peer._restarted),
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
        await self.write(notification, self.negotiated)
        log.debug(
            lazymsg(
                'notification.sent code={c} subcode={sc} data={d}',
                c=notification.code,
                sc=notification.subcode,
                d=notification.data.decode('utf-8'),
            ),
            self._session(),
        )
        return notification

    async def new_update_generator(self, include_withdraw: bool) -> AsyncGenerator[None, None]:
        """Async generator for sending UPDATE messages - yields control between messages.

        This yields after each message to allow the event loop to process other tasks.
        """
        assert self.connection is not None
        log.debug(lazymsg('update.generator.started'), self._session())
        updates = self.neighbor.rib.outgoing.updates(self.neighbor.group_updates)
        number: int = 0
        for update in updates:
            for message in update.messages(self.negotiated, include_withdraw):
                number += 1
                current_msg = message
                log.debug(
                    lazymsg('update.message.sending num={num} msg={msg}', num=number, msg=repr(current_msg)),
                    self._session(),
                )
                await self.send(message)
                yield
        if number:
            final_number = number
            log.debug(lazymsg('update.sent count={n}', n=final_number), self._session())
        log.debug(lazymsg('update.generator.completed count={count}', count=number), self._session())

    async def new_update(self, include_withdraw: bool) -> Update:
        """Send BGP UPDATE messages (runs to completion)."""
        assert self.connection is not None
        log.debug(lazymsg('update.started'), self._session())
        updates = self.neighbor.rib.outgoing.updates(self.neighbor.group_updates)
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
        return _UPDATE

    async def new_eor(self, afi: AFI, safi: SAFI) -> EOR:
        """Send BGP End-of-RIB marker."""
        assert self.connection is not None
        eor: EOR = EOR(afi, safi)
        await self.write(eor, self.negotiated)
        log.debug(lazymsg('eor.sent afi={a} safi={s}', a=afi, s=safi), self._session())
        return eor

    async def new_eors(self, afi: AFI = AFI.undefined, safi: SAFI = SAFI.undefined) -> Update:
        """Send End-of-RIB markers for all families."""
        if self.negotiated.families:
            families = self.negotiated.families if (afi, safi) == (AFI.undefined, SAFI.undefined) else [(afi, safi)]
            for eor_afi, eor_safi in families:
                await self.new_eor(eor_afi, eor_safi)
        else:
            # If not sending EOR, send keepalive
            await self.new_keepalive('EOR')
        return _UPDATE

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
