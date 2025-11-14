"""negotiated.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message import Open

from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI


class Negotiated:
    FREE_SIZE: ClassVar[int] = ExtendedMessage.INITIAL_SIZE - 19 - 2 - 2

    def __init__(self, neighbor: Any) -> None:
        self.neighbor: Any = neighbor

        self.sent_open: Optional['Open'] = None  # Open message
        self.received_open: Optional['Open'] = None  # Open message

        self.holdtime: HoldTime = HoldTime(0)
        self.local_as: ASN = ASN(0)
        self.peer_as: ASN = ASN(0)
        self.families: List[Tuple[AFI, SAFI]] = []
        self.nexthop: List[Tuple[AFI, SAFI]] = []
        self.asn4: bool = False
        self.addpath: RequirePath = RequirePath()
        self.multisession: Union[bool, Tuple[int, int, str]] = False
        self.msg_size: int = ExtendedMessage.INITIAL_SIZE
        self.operational: bool = False
        self.refresh: int = REFRESH.ABSENT  # pylint: disable=E1101
        self.aigp: bool = neighbor['capability']['aigp']
        self.mismatch: List[Tuple[str, Tuple[AFI, SAFI]]] = []

    def sent(self, sent_open: Any) -> None:  # Open message
        self.sent_open = sent_open
        if self.received_open:
            self._negotiate()

    def received(self, received_open: Any) -> None:  # Open message
        self.received_open = received_open
        if self.sent_open:
            self._negotiate()

    def _negotiate(self) -> None:
        sent_capa = self.sent_open.capabilities  # type: ignore[union-attr]
        recv_capa = self.received_open.capabilities  # type: ignore[union-attr]

        self.holdtime = HoldTime(min(self.sent_open.hold_time, self.received_open.hold_time))  # type: ignore[union-attr]

        self.addpath.setup(self.received_open, self.sent_open)
        self.asn4 = sent_capa.announced(Capability.CODE.FOUR_BYTES_ASN) and recv_capa.announced(
            Capability.CODE.FOUR_BYTES_ASN,
        )
        self.operational = sent_capa.announced(Capability.CODE.OPERATIONAL) and recv_capa.announced(
            Capability.CODE.OPERATIONAL,
        )

        self.local_as = self.sent_open.asn  # type: ignore[union-attr]
        self.peer_as = self.received_open.asn  # type: ignore[union-attr]
        if self.received_open.asn == AS_TRANS and self.asn4:  # type: ignore[union-attr]
            self.peer_as = recv_capa.get(Capability.CODE.FOUR_BYTES_ASN, self.peer_as)

        self.families = []
        if recv_capa.announced(Capability.CODE.MULTIPROTOCOL) and sent_capa.announced(Capability.CODE.MULTIPROTOCOL):
            for family in recv_capa[Capability.CODE.MULTIPROTOCOL]:
                if family in sent_capa[Capability.CODE.MULTIPROTOCOL]:
                    self.families.append(family)

        self.nexthop = []
        if recv_capa.announced(Capability.CODE.NEXTHOP) and sent_capa.announced(Capability.CODE.NEXTHOP):
            for family in recv_capa[Capability.CODE.NEXTHOP]:
                if family in sent_capa[Capability.CODE.NEXTHOP]:
                    self.nexthop.append(family)

        if recv_capa.announced(Capability.CODE.ENHANCED_ROUTE_REFRESH) and sent_capa.announced(
            Capability.CODE.ENHANCED_ROUTE_REFRESH,
        ):
            self.refresh = REFRESH.ENHANCED  # pylint: disable=E1101
        elif recv_capa.announced(Capability.CODE.ROUTE_REFRESH) and sent_capa.announced(Capability.CODE.ROUTE_REFRESH):
            self.refresh = REFRESH.NORMAL  # pylint: disable=E1101

        if recv_capa.announced(Capability.CODE.EXTENDED_MESSAGE) and sent_capa.announced(
            Capability.CODE.EXTENDED_MESSAGE,
        ):
            self.msg_size = ExtendedMessage.EXTENDED_SIZE

        self.multisession = sent_capa.announced(Capability.CODE.MULTISESSION) and recv_capa.announced(
            Capability.CODE.MULTISESSION,
        )
        self.multisession |= sent_capa.announced(Capability.CODE.MULTISESSION_CISCO) and recv_capa.announced(
            Capability.CODE.MULTISESSION_CISCO,
        )

        if self.multisession:
            sent_ms_capa = set(sent_capa[Capability.CODE.MULTISESSION])
            recv_ms_capa = set(recv_capa[Capability.CODE.MULTISESSION])

            if sent_ms_capa == set([]):
                sent_ms_capa = set([Capability.CODE.MULTIPROTOCOL])
            if recv_ms_capa == set([]):
                recv_ms_capa = set([Capability.CODE.MULTIPROTOCOL])

            if sent_ms_capa != recv_ms_capa:
                self.multisession = (2, 8, 'multisession, our peer did not reply with the same sessionid')

            # The way we implement MS-BGP, we only send one MP per session
            # therefore we can not collide due to the way we generate the configuration

            for capa in sent_ms_capa:
                # no need to check that the capability exists, we generated it
                # checked it is what we sent and only send MULTIPROTOCOL
                if sent_capa[capa] != recv_capa[capa]:
                    self.multisession = (
                        2,
                        8,
                        'when checking session id, capability {} did not match'.format(str(capa)),
                    )
                    break

        elif sent_capa.announced(Capability.CODE.MULTISESSION):
            self.multisession = (2, 9, 'multisession is mandatory with this peer')

        # XXX: Does not work as the capa is not yet defined
        # if received_open.capabilities.announced(Capability.CODE.EXTENDED_MESSAGE) \
        # and sent_open.capabilities.announced(Capability.CODE.EXTENDED_MESSAGE):
        # 	if self.peer.bgp.received_open_size:
        # 		self.received_open_size = self.peer.bgp.received_open_size - 19

    def validate(self, neighbor: Any) -> Optional[Tuple[int, int, str]]:
        if neighbor['peer-as'] is not None and self.peer_as != neighbor['peer-as']:
            return (
                2,
                2,
                'ASN in OPEN (%d) did not match ASN expected (%d)' % (self.received_open.asn, neighbor['peer-as']),  # type: ignore[union-attr]
            )

        # RFC 6286 : https://tools.ietf.org/html/rfc6286
        # XXX: FIXME: check that router id is not self
        if self.received_open.router_id == RouterID('0.0.0.0'):  # type: ignore[union-attr]
            return (2, 3, '0.0.0.0 is an invalid router_id')

        if self.received_open.asn == neighbor['local-as']:  # type: ignore[union-attr]
            # router-id must be unique within an ASN
            if self.received_open.router_id == neighbor['router-id']:  # type: ignore[union-attr]
                return (
                    2,
                    3,
                    'BGP Identifier collision, same router-id ({}) on both sides of this IBGP session'.format(
                        self.received_open.router_id  # type: ignore[union-attr]
                    ),
                )

        if self.received_open.hold_time and self.received_open.hold_time < HoldTime.MIN:  # type: ignore[union-attr]
            return (2, 6, 'Hold Time is invalid (%d)' % self.received_open.hold_time)  # type: ignore[union-attr]

        if self.multisession not in (True, False):
            # XXX: FIXME: should we not use a string and perform a split like we do elswhere ?
            # XXX: FIXME: or should we use this trick in the other case ?
            return self.multisession  # type: ignore[return-value]

        s = set(self.sent_open.capabilities.get(Capability.CODE.MULTIPROTOCOL, []))  # type: ignore[union-attr]
        r = set(self.received_open.capabilities.get(Capability.CODE.MULTIPROTOCOL, []))  # type: ignore[union-attr]
        mismatch = s ^ r

        for family in mismatch:
            self.mismatch.append(('exabgp' if family in r else 'peer', family))

        return None

    def nexthopself(self, afi: AFI) -> Any:
        return self.neighbor.ip_self(afi)


# =================================================================== RequirePath


class RequirePath:
    CANT: ClassVar[int] = 0b00
    RECEIVE: ClassVar[int] = 0b01
    SEND: ClassVar[int] = 0b10
    BOTH: ClassVar[int] = SEND | RECEIVE

    def __init__(self) -> None:
        self._send: Dict[Tuple[AFI, SAFI], bool] = {}
        self._receive: Dict[Tuple[AFI, SAFI], bool] = {}

    def setup(self, received_open: Any, sent_open: Any) -> None:  # Open messages
        # A Dict always returning False
        class FalseDict(dict):
            def __getitem__(self, key: Any) -> bool:
                return False

        receive = received_open.capabilities.get(Capability.CODE.ADD_PATH, FalseDict())
        send = sent_open.capabilities.get(Capability.CODE.ADD_PATH, FalseDict())

        # python 2.4 compatibility mean no simple union but using sets.Set
        union: List[Tuple[AFI, SAFI]] = []
        union.extend(send.keys())
        union.extend([k for k in receive.keys() if k not in send.keys()])

        for k in union:
            here_will_send = bool(send.get(k, self.CANT) & self.SEND)
            they_will_recv = bool(receive.get(k, self.CANT) & self.RECEIVE)

            here_will_recv = bool(send.get(k, self.CANT) & self.RECEIVE)
            they_will_send = bool(receive.get(k, self.CANT) & self.SEND)

            self._send[k] = here_will_send and they_will_recv
            self._receive[k] = here_will_recv and they_will_send

    def send(self, afi: AFI, safi: SAFI) -> bool:
        return self._send.get((afi, safi), False)

    def receive(self, afi: AFI, safi: SAFI) -> bool:
        return self._receive.get((afi, safi), False)
