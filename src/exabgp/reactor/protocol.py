"""protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os

import traceback
from typing import Any, Generator, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.peer import Peer
    from exabgp.reactor.network.incoming import Incoming
    from exabgp.bgp.neighbor import Neighbor

# ================================================================ Registration
#

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
from exabgp.bgp.message.refresh import RouteRefresh

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction

from exabgp.bgp.message.update.attribute import Attribute

from exabgp.protocol.ip import IP

from exabgp.logger import log

# This is the number of chuncked message we are willing to buffer, not the number of routes
MAX_BACKLOG = 15000

_UPDATE = Update([], b'')
_OPERATIONAL = Operational(0x00)


class Protocol:
    decode: bool = True

    def __init__(self, peer: 'Peer') -> None:
        self.peer: 'Peer' = peer
        self.neighbor: 'Neighbor' = peer.neighbor
        self.negotiated: Negotiated = Negotiated(self.neighbor, Direction.IN)
        self.connection: Optional[Union['Incoming', Outgoing]] = None

        if self.neighbor['connect']:
            self.port: int = self.neighbor['connect']
        elif os.environ.get('exabgp.tcp.port', '').isdigit():
            self.port = int(os.environ.get('exabgp.tcp.port'))
        elif os.environ.get('exabgp_tcp_port', '').isdigit():
            self.port = int(os.environ.get('exabgp_tcp_port'))
        else:
            self.port = 179

        from exabgp.environment import getenv

        self.log_routes: bool = peer.neighbor['adj-rib-in'] or getenv().log.routes

    def fd(self) -> int:
        if self.connection is None:
            return -1
        return self.connection.fd()

    # XXX: we use self.peer.neighbor['peer-address'] when we could use self.neighbor['peer-address']

    def me(self, message: str) -> str:
        return f'{self.peer.neighbor["peer-address"]}/{self.peer.neighbor["peer-as"]} {message}'

    def accept(self, incoming: 'Incoming') -> Protocol:
        self.connection = incoming

        if self.peer.neighbor.api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        # very important - as we use this function on __init__
        return self

    def connect(self) -> Generator[bool, None, None]:
        # allows to test the protocol code using modified StringIO with a extra 'pending' function
        if self.connection:
            return

        local = self.neighbor['md5-ip'].top() if not self.neighbor.auto_discovery else None
        peer = self.neighbor['peer-address'].top()
        afi = self.neighbor['peer-address'].afi
        md5 = self.neighbor['md5-password']
        md5_base64 = self.neighbor['md5-base64']
        ttl_out = self.neighbor['outgoing-ttl']
        itf = self.neighbor['source-interface']
        self.connection = Outgoing(afi, peer, local, self.port, md5, md5_base64, ttl_out, itf)

        for connected in self.connection.establish():
            yield False

        if self.peer.neighbor.api['neighbor-changes']:
            self.peer.reactor.processes.connected(self.peer.neighbor)

        if not local:
            self.neighbor['local-address'] = IP.create(self.connection.local)
            if self.neighbor['router-id'] is None and self.neighbor['local-address'].afi == AFI.ipv4:
                self.neighbor['router-id'] = self.neighbor['local-address']

        yield True

    def close(self, reason: str = 'protocol closed, reason unspecified') -> None:
        if self.connection:
            log.debug(lambda: reason, self.connection.session())
            self.peer.stats['down'] += 1

            self.connection.close()
            self.connection = None

    def _to_api(self, direction: str, message: Any, raw: bytes) -> None:
        packets: bool = self.neighbor.api['{}-packets'.format(direction)]
        parsed: bool = self.neighbor.api['{}-parsed'.format(direction)]
        consolidate: bool = self.neighbor.api['{}-consolidate'.format(direction)]
        negotiated: Negotiated = self.negotiated

        if consolidate:
            if packets:
                self.peer.reactor.processes.message(
                    message.ID,
                    self.peer.neighbor,
                    direction,
                    message,
                    negotiated,
                    raw[:19],
                    raw[19:],
                )
            else:
                self.peer.reactor.processes.message(
                    message.ID,
                    self.peer.neighbor,
                    direction,
                    message,
                    negotiated,
                    b'',
                    b'',
                )
        else:
            if packets:
                self.peer.reactor.processes.packets(
                    self.peer.neighbor,
                    direction,
                    int(message.ID),
                    negotiated,
                    raw[:19],
                    raw[19:],
                )
            if parsed:
                self.peer.reactor.processes.message(
                    message.ID,
                    self.peer.neighbor,
                    direction,
                    message,
                    negotiated,
                    b'',
                    b'',
                )

    def write(self, message: Any, negotiated: Negotiated) -> Generator[bool, None, None]:
        raw: bytes = message.message(negotiated)

        code: str = 'send-{}'.format(Message.CODE.short(message.ID))
        self.peer.stats[code] += 1
        if self.neighbor.api.get(code, False):
            self._to_api('send', message, raw)

        for boolean in self.connection.writer(raw):
            yield boolean

    def send(self, raw: bytes) -> Generator[bool, None, None]:
        code: str = 'send-{}'.format(Message.CODE.short(raw[18]))
        self.peer.stats[code] += 1
        if self.neighbor.api.get(code, False):
            message: Update = Update.unpack_message(raw[19:], self.negotiated)
            self._to_api('send', message, raw)

        for boolean in self.connection.writer(raw):
            yield boolean

    # Read from network .......................................................

    def read_message(self) -> Generator[Union[Message, NOP], None, None]:
        # This will always be defined by the loop but scope leaking upset scrutinizer/pylint
        msg_id = None

        packets = self.neighbor.api['receive-packets']
        consolidate = self.neighbor.api['receive-consolidate']
        parsed = self.neighbor.api['receive-parsed']

        body, header = b'', b''  # just because pylint/pylama are getting more clever

        for length, msg_id, header, body, notify in self.connection.reader():
            # internal issue
            if notify:
                code = 'receive-{}'.format(Message.CODE.NOTIFICATION.SHORT)
                if self.neighbor.api.get(code, False):
                    if consolidate:
                        self.peer.reactor.processes.notification(
                            self.peer.neighbor,
                            'receive',
                            notify.code,
                            notify.subcode,
                            str(notify),
                            None,
                            header,
                            body,
                        )
                    elif parsed:
                        self.peer.reactor.processes.notification(
                            self.peer.neighbor,
                            'receive',
                            notify.code,
                            notify.subcode,
                            str(notify),
                            None,
                            b'',
                            b'',
                        )
                    elif packets:
                        self.peer.reactor.processes.packets(self.peer.neighbor, 'receive', msg_id, None, header, body)
                # XXX: is notify not already Notify class ?
                raise Notify(notify.code, notify.subcode, str(notify))

            if msg_id not in Message.CODE.MESSAGES:
                raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id)

            if not length:
                yield _NOP
                continue

            log.debug(
                lambda msg_id=msg_id: '<< message of type {}'.format(Message.CODE.name(msg_id)),
                self.connection.session(),
            )

            code = 'receive-{}'.format(Message.CODE.short(msg_id))
            self.peer.stats[code] += 1
            for_api = self.neighbor.api.get(code, False)

            if for_api and packets and not consolidate:
                negotiated = self.negotiated if self.neighbor.api.get('negotiated', False) else None
                self.peer.reactor.processes.packets(self.peer.neighbor, 'receive', msg_id, negotiated, header, body)

            if msg_id == Message.CODE.UPDATE:
                if not self.neighbor['adj-rib-in'] and not (for_api or self.log_routes) and not (parsed or consolidate):
                    yield _UPDATE
                    return

            try:
                message = Message.unpack(msg_id, body, self.negotiated)
            except (KeyboardInterrupt, SystemExit, Notify):
                raise
            except Exception as exc:
                log.debug(lambda msg_id=msg_id: 'could not decode message "%d"' % msg_id, self.connection.session())
                log.debug(lambda exc=exc: '{}'.format(str(exc)), self.connection.session())
                log.debug(lambda: traceback.format_exc(), self.connection.session())
                raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id) from None
                # raise Notify(5,0,'unknown message received')

            if message.TYPE == Update.TYPE:
                if Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in message.attributes:
                    for nlri in message.nlris:
                        nlri.action = Action.WITHDRAW

            if for_api:
                negotiated = self.negotiated if self.neighbor.api.get('negotiated', False) else None
                if consolidate:
                    self.peer.reactor.processes.message(
                        msg_id,
                        self.neighbor,
                        'receive',
                        message,
                        negotiated,
                        header,
                        body,
                    )
                elif parsed:
                    self.peer.reactor.processes.message(msg_id, self.neighbor, 'receive', message, negotiated, b'', b'')

            if message.TYPE == Notification.TYPE:
                raise message

            if message.TYPE == Update.TYPE and Attribute.CODE.INTERNAL_DISCARD in message.attributes:
                yield _NOP
            else:
                yield message

    def validate_open(self) -> None:
        error: Optional[Tuple[int, int, str]] = self.negotiated.validate(self.neighbor)
        if error is not None:
            raise Notify(*error)

        if self.neighbor.api['negotiated']:
            self.peer.reactor.processes.negotiated(self.peer.neighbor, self.negotiated)

        if self.negotiated.mismatch:
            log.warning(
                lambda: '--------------------------------------------------------------------',
                self.connection.session(),
            )
            log.warning(
                lambda: 'the connection can not carry the following family/families',
                self.connection.session(),
            )
            for reason, (afi, safi) in self.negotiated.mismatch:
                log.warning(
                    lambda afi=afi, reason=reason, safi=safi: f' - {reason} is not configured for {afi}/{safi}',
                    self.connection.session(),
                )
            log.warning(
                lambda: 'therefore no routes of this kind can be announced on the connection',
                self.connection.session(),
            )
            log.warning(
                lambda: '--------------------------------------------------------------------',
                self.connection.session(),
            )

    def read_open(self, ip: str) -> Generator[Union[Open, NOP], None, None]:
        for received_open in self.read_message():
            if received_open.TYPE == NOP.TYPE:
                yield received_open
            else:
                break

        if received_open.TYPE != Open.TYPE:
            raise Notify(
                5,
                1,
                'The first packet received is not an open message ({})'.format(received_open),
            )

        log.debug(lambda: '<< {}'.format(received_open), self.connection.session())
        yield received_open

    def read_keepalive(self) -> Generator[Union[KeepAlive, NOP], None, None]:
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

    def new_open(self) -> Generator[Union[Open, NOP], None, None]:
        if self.neighbor['local-as']:
            local_as = self.neighbor['local-as']
        elif self.negotiated.received_open:
            local_as = self.negotiated.received_open.asn
        else:
            raise RuntimeError('no ASN available for the OPEN message')

        sent_open = Open(
            Version(4),
            local_as,
            self.neighbor['hold-time'],
            self.neighbor['router-id'],
            Capabilities().new(self.neighbor, self.peer._restarted),
        )

        # we do not buffer open message in purpose
        for _ in self.write(sent_open, self.negotiated):
            yield _NOP

        log.debug(lambda: '>> {}'.format(sent_open), self.connection.session())
        yield sent_open

    def new_keepalive(self, comment: str = '') -> Generator[Union[KeepAlive, NOP], None, None]:
        keepalive: KeepAlive = KeepAlive()

        for _ in self.write(keepalive, self.negotiated):
            yield _NOP

        log.debug(
            lambda: f'>> KEEPALIVE{f" ({comment})" if comment else ""}',
            self.connection.session(),
        )

        yield keepalive

    def new_notification(self, notification: Notify) -> Generator[Union[Notify, NOP], None, None]:
        for _ in self.write(notification, self.negotiated):
            yield _NOP
        log.debug(
            lambda: f'>> NOTIFICATION ({notification.code},{notification.subcode},"{notification.data.decode("utf-8")}")',
            self.connection.session(),
        )
        yield notification

    def new_update(self, include_withdraw: bool) -> Generator[Union[Update, NOP], None, None]:
        updates = self.neighbor.rib.outgoing.updates(self.neighbor['group-updates'])
        number: int = 0
        for update in updates:
            for message in update.messages(self.negotiated, include_withdraw):
                number += 1
                for boolean in self.send(message):
                    # boolean is a transient network error we already announced
                    yield _NOP
        if number:
            log.debug(lambda: '>> %d UPDATE(s)' % number, self.connection.session())
        yield _UPDATE

    def new_eor(self, afi: AFI, safi: SAFI) -> Generator[Union[EOR, NOP], None, None]:
        eor: EOR = EOR(afi, safi)
        for _ in self.write(eor, self.negotiated):
            yield _NOP
        log.debug(lambda: '>> EOR {} {}'.format(afi, safi), self.connection.session())
        yield eor

    def new_eors(
        self, afi: AFI = AFI.undefined, safi: SAFI = SAFI.undefined
    ) -> Generator[Union[Update, NOP], None, None]:
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
                yield _NOP
            yield _UPDATE

    def new_operational(
        self, operational: Operational, negotiated: Negotiated
    ) -> Generator[Union[Operational, NOP], None, None]:
        for _ in self.write(operational, negotiated):
            yield _NOP
        log.debug(lambda: '>> OPERATIONAL {}'.format(str(operational)), self.connection.session())
        yield operational

    def new_refresh(self, refresh: RouteRefresh) -> Generator[Union[RouteRefresh, NOP], None, None]:
        for _ in self.write(refresh, self.negotiated):
            yield _NOP
        log.debug(lambda: '>> REFRESH {}'.format(str(refresh)), self.connection.session())
        yield refresh
