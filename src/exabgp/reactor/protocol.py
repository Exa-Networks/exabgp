"""protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import asyncio  # noqa: F401 - Used by async methods (write_async, send_async, read_message_async)
import os
import traceback
from typing import TYPE_CHECKING, Any, Generator, cast
from collections.abc import AsyncGenerator

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.network.incoming import Incoming
    from exabgp.reactor.peer import Peer

# ================================================================ Registration
#

from exabgp.bgp.message import _NOP, EOR, KeepAlive, Message, Notification, Notify, Open, Operational, Update
from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Negotiated
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute import Attribute, Attributes
from exabgp.logger import lazymsg, log

# from exabgp.reactor.network.error import NotifyError
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.reactor.network.outgoing import Outgoing

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

_UPDATE = Update([], Attributes())
_OPERATIONAL = Operational(0x00)


class Protocol:
    decode: bool = True

    def __init__(self, peer: 'Peer') -> None:
        self.peer: 'Peer' = peer
        self.neighbor: 'Neighbor' = peer.neighbor
        self.negotiated: Negotiated = Negotiated(self.neighbor, Direction.IN)
        self.connection: 'Incoming' | Outgoing | None = None

        if self.neighbor.connect:
            self.port: int = self.neighbor.connect
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
        return f'{self.peer.neighbor.peer_address}/{self.peer.neighbor.peer_as} {message}'

    def accept(self, incoming: 'Incoming') -> Protocol:
        self.connection = incoming

        if self._api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        # very important - as we use this function on __init__
        return self

    def connect(self) -> Generator[bool, None, None]:
        # allows to test the protocol code using modified StringIO with a extra 'pending' function
        if self.connection:
            return

        assert self.neighbor.peer_address is not None
        local = self.neighbor.md5_ip.top() if not self.neighbor.auto_discovery and self.neighbor.md5_ip else ''
        peer = self.neighbor.peer_address.top()
        afi = self.neighbor.peer_address.afi
        md5 = self.neighbor.md5_password
        md5_base64 = self.neighbor.md5_base64
        ttl_out = self.neighbor.outgoing_ttl
        itf = self.neighbor.source_interface
        self.connection = Outgoing(afi, peer, local, self.port, md5, md5_base64, ttl_out, itf)

        for connected in self.connection.establish():
            yield False

        if self._api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        if not local:
            self.neighbor.local_address = IP.create(self.connection.local)
            if self.neighbor.router_id is None and self.neighbor.local_address.afi == AFI.ipv4:
                self.neighbor.router_id = RouterID(self.neighbor.local_address.top())

        yield True

    async def connect_async(self) -> bool:
        """Async version of connect() - establishes connection using asyncio

        Returns:
            True if connection successful, False otherwise

        Uses Outgoing.establish_async() which properly integrates with asyncio
        instead of generator-based polling.
        """
        # allows to test the protocol code using modified StringIO with a extra 'pending' function
        if self.connection:
            return True

        assert self.neighbor.peer_address is not None
        local = self.neighbor.md5_ip.top() if not self.neighbor.auto_discovery and self.neighbor.md5_ip else ''
        peer = self.neighbor.peer_address.top()
        afi = self.neighbor.peer_address.afi
        md5 = self.neighbor.md5_password
        md5_base64 = self.neighbor.md5_base64
        ttl_out = self.neighbor.outgoing_ttl
        itf = self.neighbor.source_interface
        self.connection = Outgoing(afi, peer, local, self.port, md5, md5_base64, ttl_out, itf)

        # Use async establish instead of generator
        connected = await self.connection.establish_async()

        if not connected:
            return False

        if self._api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        if not local:
            self.neighbor.local_address = IP.create(self.connection.local)
            if self.neighbor.router_id is None and self.neighbor.local_address.afi == AFI.ipv4:
                self.neighbor.router_id = RouterID(self.neighbor.local_address.top())

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

    def write(self, message: Any, negotiated: Negotiated) -> Generator[bool, None, None]:
        assert self.connection is not None
        raw: bytes = message.pack_message(negotiated)

        code: str = 'send-{}'.format(Message.CODE.short(message.ID))
        self.peer.stats[code] += 1
        if self._api.get(code, False):
            self._to_api('send', message, raw)

        for boolean in self.connection.writer(raw):
            yield boolean

    async def write_async(self, message: Any, negotiated: Negotiated) -> None:
        """Async version of write() - sends BGP message using async I/O"""
        assert self.connection is not None
        raw: bytes = message.pack_message(negotiated)

        code: str = 'send-{}'.format(Message.CODE.short(message.ID))
        self.peer.stats[code] += 1
        if self._api.get(code, False):
            self._to_api('send', message, raw)

        await self.connection.writer_async(raw)

    def send(self, raw: bytes) -> Generator[bool, None, None]:
        assert self.connection is not None
        code: str = 'send-{}'.format(Message.CODE.short(raw[18]))
        self.peer.stats[code] += 1
        if self._api.get(code, False):
            message: Update = Update.unpack_message(raw[19:], self.negotiated)
            self._to_api('send', message, raw)

        for boolean in self.connection.writer(raw):
            yield boolean

    async def send_async(self, raw: bytes) -> None:
        """Async version of send() - sends raw BGP message using async I/O"""
        assert self.connection is not None
        code: str = 'send-{}'.format(Message.CODE.short(raw[18]))
        self.peer.stats[code] += 1
        if self._api.get(code, False):
            message: Update = Update.unpack_message(raw[19:], self.negotiated)
            self._to_api('send', message, raw)

        await self.connection.writer_async(raw)

    # Read from network .......................................................

    def read_message(self) -> Generator[Message, None, None]:
        assert self.connection is not None
        # This will always be defined by the loop but scope leaking upset scrutinizer/pylint
        msg_id = None

        packets = self._api['receive-packets']
        consolidate = self._api['receive-consolidate']
        parsed = self._api['receive-parsed']

        body, header = b'', b''  # just because pylint/pylama are getting more clever

        for length, msg_id, header, body, notify in self.connection.reader():
            # internal issue
            if notify:
                code = 'receive-{}'.format(Message.CODE.NOTIFICATION.SHORT)
                # Convert NotifyError to Notify for API and exception
                notify_msg = Notify(notify.code, notify.subcode, str(notify))
                if self._api.get(code, False):
                    if consolidate:
                        self.peer.reactor.processes.notification(
                            self.peer.neighbor, 'receive', notify_msg, header, body, self.negotiated
                        )
                    elif parsed:
                        self.peer.reactor.processes.notification(
                            self.peer.neighbor, 'receive', notify_msg, b'', b'', self.negotiated
                        )
                    elif packets:
                        self.peer.reactor.processes.packets(
                            self.peer.neighbor, 'receive', msg_id, header, body, self.negotiated
                        )
                raise notify_msg

            if not length:
                yield cast(Message, _NOP)
                continue

            if msg_id not in Message.CODE.MESSAGES:
                raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id)

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
                    self.peer.neighbor, 'receive', msg_id, header, body, self.negotiated
                )

            if msg_id == Message.CODE.UPDATE:
                if not self.neighbor.adj_rib_in and not (for_api or self.log_routes) and not (parsed or consolidate):
                    yield cast(Message, _UPDATE)
                    return

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
                update = cast(Update, message)
                if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in update.attributes:
                    for nlri in update.nlris:
                        nlri.action = Action.WITHDRAW

            if for_api:
                if consolidate:
                    self.peer.reactor.processes.message(
                        msg_id, self.peer, 'receive', message, header, body, self.negotiated
                    )
                elif parsed:
                    self.peer.reactor.processes.message(
                        msg_id, self.peer, 'receive', message, b'', b'', self.negotiated
                    )

            if message.TYPE == Notification.TYPE:
                raise cast(Notification, message)

            if message.TYPE == Update.TYPE and Attribute.CODE.INTERNAL_DISCARD in cast(Update, message).attributes:
                yield cast(Message, _NOP)
            else:
                yield message

    async def read_message_async(self) -> Message:
        """Async version of read_message() - reads BGP message using async I/O"""
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
                        self.peer.neighbor, 'receive', notify_msg, header, body, self.negotiated
                    )
                elif parsed:
                    self.peer.reactor.processes.notification(
                        self.peer.neighbor, 'receive', notify_msg, b'', b'', self.negotiated
                    )
                elif packets:
                    self.peer.reactor.processes.packets(
                        self.peer.neighbor, 'receive', msg_id, header, body, self.negotiated
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
            self.peer.reactor.processes.packets(self.peer.neighbor, 'receive', msg_id, header, body, self.negotiated)

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
            update = cast(Update, message)
            if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in update.attributes:
                for nlri in update.nlris:
                    nlri.action = Action.WITHDRAW

        if for_api:
            if consolidate:
                self.peer.reactor.processes.message(
                    msg_id, self.peer, 'receive', message, header, body, self.negotiated
                )
            elif parsed:
                self.peer.reactor.processes.message(msg_id, self.peer, 'receive', message, b'', b'', self.negotiated)

        if message.TYPE == Notification.TYPE:
            raise cast(Notification, message)

        if message.TYPE == Update.TYPE and Attribute.CODE.INTERNAL_DISCARD in cast(Update, message).attributes:
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

    def read_open(self, ip: str) -> Generator[Message, None, None]:
        for received_open in self.read_message():
            if received_open.SCHEDULING:  # NOP - keep waiting
                yield received_open
            else:
                break

        if received_open.TYPE != Open.TYPE:
            raise Notify(
                5,
                1,
                'The first packet received is not an open message ({})'.format(received_open),
            )

        log.debug(lazymsg('open.received message={m}', m=received_open), self._session())
        yield received_open

    async def read_open_async(self, ip: str) -> Open:
        """Async version of read_open() - reads OPEN message using async I/O"""
        while True:
            received_open = await self.read_message_async()
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

    def read_keepalive(self) -> Generator[Message, None, None]:
        for message in self.read_message():
            if message.SCHEDULING:  # NOP - keep waiting
                yield message
            else:
                break

        if message.TYPE != KeepAlive.TYPE:
            raise Notify(5, 2)

        yield message

    async def read_keepalive_async(self) -> KeepAlive:
        """Async version of read_keepalive() - reads KEEPALIVE message using async I/O"""
        while True:
            message = await self.read_message_async()
            if not message.SCHEDULING:  # Real message (not NOP)
                break

        if message.TYPE != KeepAlive.TYPE:
            raise Notify(5, 2)

        return cast(KeepAlive, message)

    #
    # Sending message to peer
    #

    def new_open(self) -> Generator[Message, None, None]:
        assert self.connection is not None
        assert self.neighbor.router_id is not None
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
        for _ in self.write(sent_open, self.negotiated):
            yield cast(Message, _NOP)

        log.debug(lazymsg('open.sent message={m}', m=sent_open), self._session())
        yield cast(Message, sent_open)

    async def new_open_async(self) -> Open:
        """Async version of new_open() - creates and sends OPEN message using async I/O"""
        assert self.connection is not None
        assert self.neighbor.router_id is not None
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
        await self.write_async(sent_open, self.negotiated)

        log.debug(lazymsg('open.sent message={m}', m=sent_open), self._session())
        return sent_open

    def new_keepalive(self, comment: str = '') -> Generator[Message, None, None]:
        assert self.connection is not None
        keepalive: KeepAlive = KeepAlive()

        for _ in self.write(keepalive, self.negotiated):
            yield cast(Message, _NOP)

        log.debug(
            lazymsg('keepalive.sent comment={c}', c=comment if comment else 'none'),
            self._session(),
        )

        yield cast(Message, keepalive)

    async def new_keepalive_async(self, comment: str = '') -> KeepAlive:
        """Async version of new_keepalive() - creates and sends KEEPALIVE message using async I/O"""
        assert self.connection is not None
        keepalive: KeepAlive = KeepAlive()

        await self.write_async(keepalive, self.negotiated)

        log.debug(
            lazymsg('keepalive.sent comment={c}', c=comment if comment else 'none'),
            self._session(),
        )

        return keepalive

    def new_notification(self, notification: Notify) -> Generator[Message, None, None]:
        assert self.connection is not None
        for _ in self.write(notification, self.negotiated):
            yield cast(Message, _NOP)
        log.debug(
            lazymsg(
                'notification.sent code={c} subcode={sc} data={d}',
                c=notification.code,
                sc=notification.subcode,
                d=notification.data.decode('utf-8'),
            ),
            self._session(),
        )
        yield cast(Message, notification)

    async def new_notification_async(self, notification: Notify) -> Notify:
        """Async version of new_notification - send BGP NOTIFICATION message"""
        assert self.connection is not None
        await self.write_async(notification, self.negotiated)
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

    def new_update(self, include_withdraw: bool) -> Generator[Message, None, None]:
        assert self.connection is not None
        assert self.neighbor.rib is not None
        updates = self.neighbor.rib.outgoing.updates(self.neighbor.group_updates)
        number: int = 0
        for update in updates:
            for message in update.messages(self.negotiated, include_withdraw):
                number += 1
                for boolean in self.send(message):
                    # boolean is a transient network error we already announced
                    yield cast(Message, _NOP)
        if number:
            log.debug(lazymsg('update.sent count={n}', n=number), self._session())
        yield cast(Message, _UPDATE)

    async def new_update_async_generator(self, include_withdraw: bool) -> AsyncGenerator[None, None]:
        """Async generator version of new_update - yields control between sending messages

        This matches the sync version's behavior where the generator is created once and
        iterated over multiple event loop cycles, preserving RIB state correctly.

        The sync version yields for each send() operation. We yield once per message sent.
        """
        assert self.connection is not None
        assert self.neighbor.rib is not None
        log.debug(lazymsg('update.async.generator.started'), self._session())
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
                # Send message using async I/O
                await self.send_async(message)
                # Yield control after each message (matches sync version yielding _NOP)
                yield
        if number:
            final_number = number
            log.debug(lazymsg('update.sent count={n}', n=final_number), self._session())
        final_count = number
        log.debug(lazymsg('update.async.generator.completed count={count}', count=final_count), self._session())

    async def new_update_async(self, include_withdraw: bool) -> Update:
        """Async version of new_update - send BGP UPDATE messages (legacy, runs to completion)"""
        assert self.connection is not None
        assert self.neighbor.rib is not None
        log.debug(lazymsg('update.async.started'), self._session())
        updates = self.neighbor.rib.outgoing.updates(self.neighbor.group_updates)
        log.debug(lazymsg('update.async.iterating'), self._session())
        number: int = 0
        for update in updates:
            current_update = update
            log.debug(
                lazymsg('update.async.processing update={upd}', upd=current_update),
                self._session(),
            )
            for message in update.messages(self.negotiated, include_withdraw):
                number += 1
                current_msg = message
                log.debug(
                    lazymsg('update.message.sending num={num} msg={msg}', num=number, msg=repr(current_msg)),
                    self._session(),
                )
                await self.send_async(message)
        if number:
            log.debug(lazymsg('update.sent count={n}', n=number), self._session())
        log.debug(lazymsg('update.async.completed count={count}', count=number), self._session())
        return _UPDATE

    def new_eor(self, afi: AFI, safi: SAFI) -> Generator[Message, None, None]:
        assert self.connection is not None
        eor: EOR = EOR(afi, safi)
        for _ in self.write(eor, self.negotiated):
            yield cast(Message, _NOP)
        log.debug(lazymsg('eor.sent afi={a} safi={s}', a=afi, s=safi), self._session())
        yield cast(Message, eor)

    async def new_eor_async(self, afi: AFI, safi: SAFI) -> EOR:
        """Async version of new_eor - send BGP End-of-RIB marker"""
        assert self.connection is not None
        eor: EOR = EOR(afi, safi)
        await self.write_async(eor, self.negotiated)
        log.debug(lazymsg('eor.sent afi={a} safi={s}', a=afi, s=safi), self._session())
        return eor

    async def new_eors_async(self, afi: AFI = AFI.undefined, safi: SAFI = SAFI.undefined) -> Update:
        """Async version of new_eors - send End-of-RIB markers for all families"""
        if self.negotiated.families:
            families = self.negotiated.families if (afi, safi) == (AFI.undefined, SAFI.undefined) else [(afi, safi)]
            for eor_afi, eor_safi in families:
                await self.new_eor_async(eor_afi, eor_safi)
        else:
            # If not sending EOR, send keepalive
            await self.new_keepalive_async('EOR')
        return _UPDATE

    def new_eors(self, afi: AFI = AFI.undefined, safi: SAFI = SAFI.undefined) -> Generator[Message, None, None]:
        # Send EOR to let our peer know he can perform a RIB update
        if self.negotiated.families:
            families = (
                self.negotiated.families
                if (afi, safi) == (AFI.undefined, SAFI.undefined)
                else [
                    (afi, safi),
                ]
            )
            for eor_afi, eor_safi in families:
                for _ in self.new_eor(eor_afi, eor_safi):
                    yield _
        else:
            # If we are not sending an EOR, send a keepalive as soon as when finished
            # So the other routers knows that we have no (more) routes to send ...
            # (is that behaviour documented somewhere ??)
            for eor in self.new_keepalive('EOR'):
                yield cast(Message, _NOP)
            yield cast(Message, _UPDATE)

    def new_operational(self, operational: Operational, negotiated: Negotiated) -> Generator[Message, None, None]:
        assert self.connection is not None
        for _ in self.write(operational, negotiated):
            yield cast(Message, _NOP)
        log.debug(lazymsg('operational.sent message={m}', m=str(operational)), self._session())
        yield cast(Message, operational)

    async def new_operational_async(self, operational: Operational, negotiated: Negotiated) -> Operational:
        """Async version of new_operational - send BGP OPERATIONAL message"""
        assert self.connection is not None
        await self.write_async(operational, negotiated)
        log.debug(lazymsg('operational.sent message={m}', m=str(operational)), self._session())
        return operational

    def new_refresh(self, refresh: RouteRefresh) -> Generator[Message, None, None]:
        assert self.connection is not None
        for _ in self.write(refresh, self.negotiated):
            yield cast(Message, _NOP)
        log.debug(lazymsg('refresh.sent message={m}', m=str(refresh)), self._session())
        yield cast(Message, refresh)

    async def new_refresh_async(self, refresh: RouteRefresh) -> RouteRefresh:
        """Async version of new_refresh - send BGP ROUTE-REFRESH message"""
        assert self.connection is not None
        await self.write_async(refresh, self.negotiated)
        log.debug(lazymsg('refresh.sent message={m}', m=str(refresh)), self._session())
        return refresh
