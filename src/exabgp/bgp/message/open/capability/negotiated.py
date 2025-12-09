"""negotiated.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message import Open
    from exabgp.bgp.message.direction import Direction
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.protocol.ip import IP

from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.nexthop import NextHop
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI


class Negotiated:
    FREE_SIZE: ClassVar[int] = ExtendedMessage.INITIAL_SIZE - 19 - 2 - 2

    # Sentinel instance for when Negotiated is required but not used
    UNSET: ClassVar['Negotiated']

    @classmethod
    def make_negotiated(cls, neighbor: 'Neighbor', direction: 'Direction') -> 'Negotiated':
        """Factory method to create Negotiated instances.

        Use this instead of calling __init__ directly.
        """
        return cls(neighbor, direction)

    def __init__(self, neighbor: 'Neighbor', direction: 'Direction') -> None:
        self.neighbor: 'Neighbor' = neighbor
        self.direction: 'Direction' = direction

        self.sent_open: 'Open' | None = None  # Open message
        self.received_open: 'Open' | None = None  # Open message

        self.holdtime: HoldTime = HoldTime(0)
        self.local_as: ASN = ASN(0)
        self.peer_as: ASN = ASN(0)
        self.families: list[tuple[AFI, SAFI]] = []
        self.nexthop: list[tuple[AFI, SAFI, AFI]] = []  # RFC5549 - (nlri_afi, nlri_safi, nexthop_afi)
        self.asn4: bool = False
        self.addpath: RequirePath = RequirePath()
        self.multisession: bool | tuple[int, int, str] = False
        self.msg_size: int = ExtendedMessage.INITIAL_SIZE
        self.operational: bool = False
        self.refresh: int = REFRESH.ABSENT  # pylint: disable=E1101
        self.aigp: bool = neighbor.capability.aigp.is_enabled()
        self.mismatch: list[tuple[str, tuple[AFI, SAFI]]] = []

    @classmethod
    def _create_unset(cls) -> 'Negotiated':
        """Create an uninitialized sentinel instance for use when Negotiated is not needed."""
        instance = object.__new__(cls)
        instance.holdtime = HoldTime(0)
        instance.local_as = ASN(0)
        instance.peer_as = ASN(0)
        instance.families = []
        instance.nexthop = []
        instance.asn4 = False
        instance.addpath = RequirePath()
        instance.multisession = False
        instance.msg_size = ExtendedMessage.INITIAL_SIZE
        instance.operational = False
        instance.refresh = REFRESH.ABSENT
        instance.aigp = False
        instance.mismatch = []
        instance.sent_open = None
        instance.received_open = None
        return instance

    def sent(self, sent_open: Any) -> None:  # Open message
        self.sent_open = sent_open
        if self.received_open:
            self._negotiate()

    def received(self, received_open: Any) -> None:  # Open message
        self.received_open = received_open
        if self.sent_open:
            self._negotiate()

    def _negotiate(self) -> None:
        # Both opens are guaranteed to be set when _negotiate is called
        assert self.sent_open is not None
        assert self.received_open is not None

        sent_capa = self.sent_open.capabilities
        recv_capa = self.received_open.capabilities

        self.holdtime = HoldTime(min(self.sent_open.hold_time, self.received_open.hold_time))

        self.addpath.setup(self.received_open, self.sent_open)
        self.asn4 = sent_capa.announced(Capability.CODE.FOUR_BYTES_ASN) and recv_capa.announced(
            Capability.CODE.FOUR_BYTES_ASN,
        )
        self.operational = sent_capa.announced(Capability.CODE.OPERATIONAL) and recv_capa.announced(
            Capability.CODE.OPERATIONAL,
        )

        self.local_as = self.sent_open.asn
        self.peer_as = self.received_open.asn
        if self.received_open.asn == AS_TRANS and self.asn4:
            asn4_capa = recv_capa.get(Capability.CODE.FOUR_BYTES_ASN, None)
            # ASN4 extends both Capability and ASN
            if isinstance(asn4_capa, ASN):
                self.peer_as = asn4_capa

        self.families = []
        if recv_capa.announced(Capability.CODE.MULTIPROTOCOL) and sent_capa.announced(Capability.CODE.MULTIPROTOCOL):
            recv_mp = recv_capa[Capability.CODE.MULTIPROTOCOL]
            sent_mp = sent_capa[Capability.CODE.MULTIPROTOCOL]
            if isinstance(recv_mp, MultiProtocol) and isinstance(sent_mp, MultiProtocol):
                for family in recv_mp:
                    if family in sent_mp:
                        self.families.append(family)

        self.nexthop = []
        if recv_capa.announced(Capability.CODE.NEXTHOP) and sent_capa.announced(Capability.CODE.NEXTHOP):
            recv_nh = recv_capa[Capability.CODE.NEXTHOP]
            sent_nh = sent_capa[Capability.CODE.NEXTHOP]
            if isinstance(recv_nh, NextHop) and isinstance(sent_nh, NextHop):
                for nh_entry in recv_nh:
                    if nh_entry in sent_nh:
                        self.nexthop.append(nh_entry)

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
            sent_ms = sent_capa[Capability.CODE.MULTISESSION]
            recv_ms = recv_capa[Capability.CODE.MULTISESSION]
            sent_ms_capa: set[int] = set(sent_ms) if isinstance(sent_ms, MultiSession) else set()
            recv_ms_capa: set[int] = set(recv_ms) if isinstance(recv_ms, MultiSession) else set()

            if sent_ms_capa == set():
                sent_ms_capa = set([Capability.CODE.MULTIPROTOCOL])
            if recv_ms_capa == set():
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

    def validate(self, neighbor: Any) -> tuple[int, int, str] | None:
        # Both opens must be set before validate is called
        assert self.sent_open is not None
        assert self.received_open is not None

        if neighbor.session.peer_as and self.peer_as != neighbor.session.peer_as:
            return (
                2,
                2,
                'ASN in OPEN (%d) did not match ASN expected (%d)' % (self.received_open.asn, neighbor.session.peer_as),
            )

        # RFC 6286 : https://tools.ietf.org/html/rfc6286
        # XXX: FIXME: check that router id is not self
        if self.received_open.router_id == RouterID('0.0.0.0'):
            return (2, 3, '0.0.0.0 is an invalid router_id')

        if self.received_open.asn == neighbor.session.local_as:
            # router-id must be unique within an ASN
            if self.received_open.router_id == neighbor.session.router_id:
                return (
                    2,
                    3,
                    'BGP Identifier collision, same router-id ({}) on both sides of this IBGP session'.format(
                        self.received_open.router_id
                    ),
                )

        if self.received_open.hold_time and self.received_open.hold_time < HoldTime.MIN:
            return (2, 6, 'Hold Time is invalid (%d)' % self.received_open.hold_time)

        if isinstance(self.multisession, tuple):
            # multisession is an error tuple (code, subcode, message)
            return self.multisession

        sent_mp = self.sent_open.capabilities.get(Capability.CODE.MULTIPROTOCOL, None)
        recv_mp = self.received_open.capabilities.get(Capability.CODE.MULTIPROTOCOL, None)
        s: set[tuple[AFI, SAFI]] = set(sent_mp) if isinstance(sent_mp, MultiProtocol) else set()
        r: set[tuple[AFI, SAFI]] = set(recv_mp) if isinstance(recv_mp, MultiProtocol) else set()
        mismatch = s ^ r

        for family in mismatch:
            self.mismatch.append(('exabgp' if family in r else 'peer', family))

        return None

    def nexthopself(self, afi: AFI) -> 'IP':
        return self.neighbor.ip_self(afi)

    @property
    def is_ibgp(self) -> bool:
        """Return True if this is an IBGP session (local_as == peer_as)."""
        return self.local_as == self.peer_as

    def required(self, afi: AFI, safi: SAFI) -> bool:
        """Get addpath status based on internal direction - if IN use receive, else use send"""
        from exabgp.bgp.message.direction import Direction

        if self.direction == Direction.IN:
            return self.addpath.receive(afi, safi)
        else:
            return self.addpath.send(afi, safi)


# =================================================================== RequirePath


class RequirePath:
    CANT: ClassVar[int] = 0b00
    RECEIVE: ClassVar[int] = 0b01
    SEND: ClassVar[int] = 0b10
    BOTH: ClassVar[int] = SEND | RECEIVE

    def __init__(self) -> None:
        self._send: dict[tuple[AFI, SAFI], bool] = {}
        self._receive: dict[tuple[AFI, SAFI], bool] = {}

    def setup(self, received_open: Any, sent_open: Any) -> None:  # Open messages
        # A Dict always returning False
        class FalseDict(dict):
            def __getitem__(self, key: Any) -> bool:
                return False

        receive = received_open.capabilities.get(Capability.CODE.ADD_PATH, FalseDict())
        send = sent_open.capabilities.get(Capability.CODE.ADD_PATH, FalseDict())

        # python 2.4 compatibility mean no simple union but using sets.Set
        union: list[tuple[AFI, SAFI]] = []
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


# Initialize the sentinel instance
Negotiated.UNSET = Negotiated._create_unset()
