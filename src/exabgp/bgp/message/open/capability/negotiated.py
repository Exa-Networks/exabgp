"""negotiated.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar, TYPE_CHECKING, cast

if TYPE_CHECKING:
    from exabgp.bgp.message import Open
    from exabgp.bgp.message.direction import Direction
    from exabgp.bgp.message.open.capability.capabilities import Capabilities
    from exabgp.bgp.message.update.attribute.collection import AttributeCollection
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.protocol.ip import IP

from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.nexthop import NextHop
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.notification import Notify
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.util.enumeration import TriState


# what labels_limit answers where no capability binds the number of labels
LABELS_UNLIMITED = 0xFFFF


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

    def __init__(self, neighbor: 'Neighbor | None', direction: 'Direction') -> None:
        # None for UNSET only, which is no session: see the neighbor property
        self._neighbor: 'Neighbor | None' = neighbor
        self.direction: 'Direction' = direction

        self.sent_open: 'Open' | None = None  # Open message
        self.received_open: 'Open' | None = None  # Open message

        self.holdtime: HoldTime = HoldTime(0)
        self.local_as: ASN = ASN(0)
        self.peer_as: ASN = ASN(0)
        self.families: list[FamilyTuple] = []
        self.nexthop: list[tuple[AFI, SAFI, AFI]] = []  # RFC5549 - (nlri_afi, nlri_safi, nexthop_afi)
        self.asn4: bool = False
        self.addpath: RequirePath = RequirePath()
        self.multisession: bool | tuple[int, int, str] = False
        # RFC 8654 4: the largest message we send, raised by the peer's capability, and the
        # largest we receive, raised by ours alone
        self.msg_size: int = ExtendedMessage.INITIAL_SIZE
        self.receive_msg_size: int = ExtendedMessage.INITIAL_SIZE
        self.operational: bool = False
        self.refresh: int = REFRESH.ABSENT  # pylint: disable=E1101
        # RFC 7311 3.3: AIGP_SESSION as configured, UNSET for the default, see aigp_session
        self.aigp: TriState = neighbor.capability.aigp if neighbor is not None else TriState.UNSET
        # RFC 7311 3.3: an AIGP ignored on a disabled session is logged, once per session
        self.aigp_ignored_logged: bool = False
        self.role: RoleValue = RoleValue.NO_ROLE
        self.peer_role: RoleValue = RoleValue.NO_ROLE
        self.role_otc: bool = neighbor.session.role_otc if neighbor is not None else False
        self.role_error: tuple[int, int, str] | None = None

        # The last attribute section this session parsed, and what it parsed to. What a
        # given set of bytes decodes to depends on this session's capabilities, so the
        # cache lives with them rather than on AttributeCollection, where one slot was
        # shared by every peer in the process. See AttributeCollection.unpack.
        self.attribute_cache: AttributeCollection | None = None
        self.attribute_cache_packed: bytes = b''
        self.attribute_cache_enabled: bool = True
        self.linklocal_nexthop: bool = False
        self.paths_limit: dict[FamilyTuple, int] = {}
        self.advertised_paths_limit: dict[FamilyTuple, int] = {}
        # RFC 8277 2.1: the labels the peer can take on one prefix, when both sent code 8
        self.multiple_labels: dict[FamilyTuple, int] = {}
        # RFC 8277 2.1: the labels we said we take on one prefix, when both sent code 8
        self.accepted_labels: dict[FamilyTuple, int] = {}
        self.mismatch: list[tuple[str, FamilyTuple]] = []

    @property
    def neighbor(self) -> 'Neighbor':
        if self._neighbor is None:
            # UNSET had no neighbor attribute at all, and asking for it raised the same way
            raise AttributeError('Negotiated.UNSET is not a session and has no neighbor')
        return self._neighbor

    @neighbor.setter
    def neighbor(self, neighbor: 'Neighbor') -> None:
        self._neighbor = neighbor

    @classmethod
    def _create_unset(cls) -> 'Negotiated':
        """Create an uninitialized sentinel instance for use when Negotiated is not needed."""
        from exabgp.bgp.message.direction import Direction

        instance = cls(None, Direction.IN)
        instance.holdtime = HoldTime(0)
        instance.local_as = ASN(0)
        instance.peer_as = ASN(0)
        instance.families = []
        instance.nexthop = []
        instance.asn4 = False
        instance.addpath = RequirePath()
        instance.multisession = False
        instance.msg_size = ExtendedMessage.INITIAL_SIZE
        instance.receive_msg_size = ExtendedMessage.INITIAL_SIZE
        instance.operational = False
        instance.refresh = REFRESH.ABSENT
        instance.aigp = TriState.UNSET
        instance.aigp_ignored_logged = False
        instance.role = RoleValue.NO_ROLE
        instance.peer_role = RoleValue.NO_ROLE
        instance.role_otc = False
        instance.role_error = None
        # UNSET is one process-wide object, never a session: it must not hold a cache,
        # or every caller handing it to AttributeCollection.unpack would share one slot.
        instance.attribute_cache = None
        instance.attribute_cache_packed = b''
        instance.attribute_cache_enabled = False
        instance.linklocal_nexthop = False
        instance.paths_limit = {}
        instance.advertised_paths_limit = {}
        instance.multiple_labels = {}
        instance.accepted_labels = {}
        instance.mismatch = []
        instance.sent_open = None
        instance.received_open = None
        return instance

    def sent(self, sent_open: Any) -> None:  # Open message
        self.sent_open = sent_open
        # RFC 8654 4: advertising the capability is being "capable of receiving a message
        # with a length up to and including 65,535 octets", whatever the peer advertises
        if sent_open.capabilities.announced(Capability.CODE.EXTENDED_MESSAGE):
            self.receive_msg_size = ExtendedMessage.EXTENDED_SIZE
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

        self.holdtime = min(self.sent_open.hold_time, self.received_open.hold_time)

        self.addpath.setup(self.received_open, self.sent_open)
        self.asn4 = sent_capa.announced(Capability.CODE.FOUR_BYTES_ASN) and recv_capa.announced(
            Capability.CODE.FOUR_BYTES_ASN,
        )
        self.operational = sent_capa.announced(Capability.CODE.OPERATIONAL) and recv_capa.announced(
            Capability.CODE.OPERATIONAL,
        )

        self.local_as = self.sent_open.asn
        if self.local_as == AS_TRANS:
            # Our identity does not depend on whether the peer supports four-octet paths.
            self.local_as = sent_capa.four_octet_asn()

        self.peer_as = self.received_open.asn
        # RFC 6793 4.1: the capability's AS number is used "in lieu of" My Autonomous System,
        # with no condition on what that field holds: AS_TRANS or not, the capability rules
        if self.asn4:
            self.peer_as = recv_capa.four_octet_asn()
        self._negotiate_role(sent_capa, recv_capa)

        sent_families = self._multiprotocol(sent_capa)
        self.families = [family for family in self._multiprotocol(recv_capa) if family in sent_families]

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

        # RFC 8654 4: we MAY send extended messages "only if the BGP Extended Message
        # Capability was received from that peer". We also wait for ours to have gone out
        if recv_capa.announced(Capability.CODE.EXTENDED_MESSAGE) and sent_capa.announced(
            Capability.CODE.EXTENDED_MESSAGE,
        ):
            self.msg_size = ExtendedMessage.EXTENDED_SIZE

        self.linklocal_nexthop = sent_capa.announced(Capability.CODE.LINK_LOCAL_NEXTHOP) and recv_capa.announced(
            Capability.CODE.LINK_LOCAL_NEXTHOP,
        )

        self.paths_limit = {}
        self.advertised_paths_limit = {}
        if recv_capa.announced(Capability.CODE.ADD_PATH) and sent_capa.announced(Capability.CODE.ADD_PATH):
            from exabgp.bgp.message.open.capability.pathslimit import PathsLimit
            from exabgp.bgp.message.open.capability.addpath import AddPath

            recv_pl = recv_capa.get(Capability.CODE.PATHS_LIMIT, None)
            recv_ap = recv_capa.get(Capability.CODE.ADD_PATH, None)
            if isinstance(recv_pl, PathsLimit) and isinstance(recv_ap, AddPath):
                for family, limit in recv_pl.items():
                    if family not in recv_ap:
                        continue
                    afi, safi = family
                    if self.addpath.send(afi, safi):
                        self.paths_limit[family] = limit

            sent_pl = sent_capa.get(Capability.CODE.PATHS_LIMIT, None)
            sent_ap = sent_capa.get(Capability.CODE.ADD_PATH, None)
            if isinstance(sent_pl, PathsLimit) and isinstance(sent_ap, AddPath):
                for family, limit in sent_pl.items():
                    if family not in sent_ap:
                        continue
                    afi, safi = family
                    if self.addpath.receive(afi, safi):
                        self.advertised_paths_limit[family] = limit

        self._negotiate_multiple_labels(sent_capa, recv_capa)

        rfc_multisession = sent_capa.announced(Capability.CODE.MULTISESSION) and recv_capa.announced(
            Capability.CODE.MULTISESSION,
        )
        cisco_multisession = sent_capa.announced(Capability.CODE.MULTISESSION_CISCO) and recv_capa.announced(
            Capability.CODE.MULTISESSION_CISCO,
        )
        self.multisession = rfc_multisession or cisco_multisession

        if self.multisession:
            multisession_code = Capability.CODE.MULTISESSION if rfc_multisession else Capability.CODE.MULTISESSION_CISCO
            sent_ms = sent_capa[multisession_code]
            recv_ms = recv_capa[multisession_code]
            sent_ms_capa: set[CapabilityCode] = set(sent_ms) if isinstance(sent_ms, MultiSession) else set()
            recv_ms_capa: set[CapabilityCode] = set(recv_ms) if isinstance(recv_ms, MultiSession) else set()

            if not sent_ms_capa:
                sent_ms_capa = {Capability.CODE.MULTIPROTOCOL}
            if not recv_ms_capa:
                recv_ms_capa = {Capability.CODE.MULTIPROTOCOL}

            # ExaBGP generates MULTIPROTOCOL as its sole Session ID component.
            # The draft defines an empty Session ID list, following the mandatory
            # flags byte, as equivalent to that default.

            if sent_ms_capa != recv_ms_capa:
                self.multisession = (2, 8, 'multisession, our peer did not reply with the same sessionid')
            else:
                # The sets name the capabilities whose values distinguish this
                # session. Locally generated data normally contains only
                # MULTIPROTOCOL, but received Session IDs remain peer input: a
                # named capability must exist on both sides before comparison.
                for capa in sent_ms_capa:
                    if (
                        capa not in sent_capa
                        or capa not in recv_capa
                        or not sent_capa[capa].same_values(recv_capa[capa])
                    ):
                        self.multisession = (
                            2,
                            8,
                            'when checking session id, capability {} did not match'.format(str(capa)),
                        )
                        break

        elif sent_capa.announced(Capability.CODE.MULTISESSION) or sent_capa.announced(
            Capability.CODE.MULTISESSION_CISCO
        ):
            self.multisession = (2, 9, 'multisession is mandatory with this peer')

    @staticmethod
    def _multiprotocol(capabilities: Capabilities) -> list[FamilyTuple]:
        """The families an OPEN offers: those of its Multiprotocol capability, else IPv4 unicast.

        A speaker which sends no Multiprotocol capability is a plain RFC 4271 speaker, and
        RFC 4271 carries IPv4 unicast and nothing else. Refusing it every family left an
        established session which could exchange no route at all.
        """
        if not capabilities.announced(Capability.CODE.MULTIPROTOCOL):
            return [(AFI.ipv4, SAFI.unicast)]
        # the registry decodes code 1 as MultiProtocol
        return list(cast(MultiProtocol, capabilities[Capability.CODE.MULTIPROTOCOL]))

    def _negotiate_role(self, sent_capa: Capabilities, recv_capa: Capabilities) -> None:
        self.role = sent_capa.role()
        self.peer_role = RoleValue.NO_ROLE
        self.role_error = None
        if self.role == RoleValue.NO_ROLE:
            return
        self.peer_role = recv_capa.role()
        if self.peer_role == RoleValue.NO_ROLE:
            if self.neighbor.session.role_strict:
                self.role_error = (2, 11, 'strict role negotiation requires the remote Role capability')
            else:
                self.peer_role = RoleValue.complement(self.role)
            return
        if not RoleValue.pair_allowed(self.role, self.peer_role):
            self.role_error = (2, 11, f'local role {self.role} does not match remote role {self.peer_role}')

    def validate(self, neighbor: Any) -> tuple[int, int, str] | None:
        # Both opens must be set before validate is called
        assert self.sent_open is not None
        assert self.received_open is not None

        # RFC 7607 2: zero as the peer AS, in My Autonomous System or in the capability
        # standing in for it, is a Bad Peer AS, even where peer-as auto would take anything
        if self.received_open.asn == 0 or self._four_octet_asn_is_zero():
            return (2, 2, 'the peer claimed AS 0, which is reserved (RFC 7607)')

        if neighbor.session.peer_as and self.peer_as != neighbor.session.peer_as:
            return (
                2,
                2,
                # the AS compared, which RFC 6793 4.1 has the capability give when there is one
                'ASN in OPEN (%d) did not match ASN expected (%d)' % (self.peer_as, neighbor.session.peer_as),
            )

        # RFC 6286 : https://tools.ietf.org/html/rfc6286
        if self.received_open.router_id == RouterID('0.0.0.0'):
            return (2, 3, '0.0.0.0 is an invalid router_id')

        # RFC 6286 2.2: our identifier from an internal peer. Internal is decided on the
        # negotiated ASes, which the four-octet capability gives (RFC 6793 4.1) and which
        # local-as and peer-as auto have resolved, never on the AS_TRANS of the OPEN
        if self.is_internal_neighbor and self.received_open.router_id == neighbor.session.router_id:
            return (
                2,
                3,
                'BGP Identifier collision, same router-id ({}) on both sides of this IBGP session'.format(
                    self.received_open.router_id
                ),
            )

        if self.received_open.hold_time and self.received_open.hold_time < HoldTime.MIN:
            return (2, 6, 'Hold Time is invalid (%d)' % self.received_open.hold_time)

        if self.role_error is not None:
            return self.role_error

        if isinstance(self.multisession, tuple):
            # multisession is an error tuple (code, subcode, message)
            return self.multisession

        s = set(self._multiprotocol(self.sent_open.capabilities))
        r = set(self._multiprotocol(self.received_open.capabilities))
        mismatch = s ^ r

        for family in mismatch:
            self.mismatch.append(('exabgp' if family in r else 'peer', family))

        return None

    def _four_octet_asn_is_zero(self) -> bool:
        """The peer's four-octet AS capability, whether we sent ours or not, names AS 0."""
        assert self.received_open is not None
        received = self.received_open.capabilities
        return received.announced(Capability.CODE.FOUR_BYTES_ASN) and received.four_octet_asn() == 0

    def unsupported_capability(self) -> Notify | None:
        """The (2, 7) refusing a peer which left out a capability we require, if it did.

        RFC 5492 3: the message "MUST contain the capability or capabilities that cause the
        speaker to send the message", and 5: each "encoded in the same way as it would be
        encoded in the OPEN message".  So the Data field is our own TLVs for what is missing.
        """
        assert self.sent_open is not None
        assert self.received_open is not None
        sent = self.sent_open.capabilities
        received = self.received_open.capabilities
        required = self.neighbor.capability.required
        # configuration turns require into enabled, so what we require we also advertised
        assert required <= sent.keys(), 'a required capability was not in our OPEN'
        # in the order of our OPEN, so the Data field reads as a cut of what we sent
        missing = [code for code in sent if code in required and code not in received]
        if not missing:
            return None
        names = ', '.join(str(code) for code in missing)
        data = b''.join(sent.tlvs(code) for code in missing)
        return Notify(2, 7, f'the peer did not advertise the required capabilities: {names}', data=data)

    def nexthopself(self, afi: AFI) -> 'IP':
        return self.neighbor.ip_self(afi)

    def link_local_address(self) -> 'IP | None':
        """Get the local link-local IPv6 address if available."""
        return self.neighbor.session.ip_link_local()

    def link_local_prefer(self) -> bool:
        """Check if link-local nexthop is preferred over global."""
        return self.neighbor.capability.link_local_prefer

    def is_multihop(self) -> bool:
        """Check if session is multihop (TTL > 1).

        Used to determine if link-local addresses should be excluded from
        next-hop (link-local only valid for directly connected peers).
        """
        ttl = self.neighbor.session.outgoing_ttl
        return ttl is not None and ttl > 1

    @property
    def is_ibgp(self) -> bool:
        """Return True if this is an IBGP session (local_as == peer_as)."""
        return self.local_as == self.peer_as

    @property
    def confederation(self) -> ASN:
        """Our AS Confederation Identifier (RFC 5065), 0 outside one.

        UNSET is a session with no neighbour, so it is in no confederation.
        """
        neighbor = getattr(self, 'neighbor', None)
        return neighbor.session.confederation if neighbor is not None else ASN(0)

    def _negotiate_multiple_labels(self, sent_capa: Capabilities, recv_capa: Capabilities) -> None:
        """RFC 8277 2.1 and 3.2.3: more than one label only when both OPENs carried code 8,
        and never more than the Count the peer gave for the family."""
        from exabgp.bgp.message.open.capability.labels import MultipleLabels

        self.multiple_labels = {}
        self.accepted_labels = {}
        sent = sent_capa.get(Capability.CODE.MULTIPLE_LABELS, None)
        received = recv_capa.get(Capability.CODE.MULTIPLE_LABELS, None)
        if sent is None or received is None:
            return
        # the registry decodes code 8 as MultipleLabels
        self.multiple_labels = dict(cast(MultipleLabels, received))
        # RFC 8277 2.1: a family missing from either capability keeps the section 2.2
        # encoding, one label, so only the families in both take our Count
        ours = cast(MultipleLabels, sent)
        self.accepted_labels = {family: count for family, count in ours.items() if family in self.multiple_labels}

    def labels_limit(self, afi: AFI, safi: SAFI) -> int:
        """The most labels we may bind to one prefix of this family on this session.

        RFC 8277 2 binds SAFI 4 and SAFI 128: one label unless the Multiple Labels
        Capability went both ways. UNSET is no session at all and packs what it is given,
        which is what an index or a comparison of two routes needs.
        """
        if getattr(self, 'neighbor', None) is None or safi not in (SAFI.nlri_mpls, SAFI.mpls_vpn):
            return LABELS_UNLIMITED
        return self.multiple_labels.get((afi, safi), 1)

    def labels_accepted(self, afi: AFI, safi: SAFI) -> int:
        """The most labels a peer may bind to one prefix of this family it sends us.

        RFC 8277 2.1: the Count of our own Multiple Labels Capability, once it went both
        ways, and one label otherwise. labels_limit is the peer's Count, which binds what
        we send. UNSET is no session, and has announced nothing to hold a peer to.
        """
        if getattr(self, 'neighbor', None) is None or safi not in (SAFI.nlri_mpls, SAFI.mpls_vpn):
            return LABELS_UNLIMITED
        return self.accepted_labels.get((afi, safi), 1)

    @property
    def peer_address(self) -> str:
        """The address of the peer, '' for UNSET, which is a session with no neighbour."""
        neighbor = getattr(self, 'neighbor', None)
        if neighbor is None or neighbor.session.peer_address is None:
            return ''
        return str(neighbor.session.peer_address)

    @property
    def filters_by_route_target(self) -> bool:
        """RFC 4684 5: the VPN routes sent are those the peer's membership asks for.

        Only when the operator asked for it (`route-target-filter`) and the session
        negotiated RT-Constraint, since without it the peer has no way to be a member.
        """
        neighbor = getattr(self, 'neighbor', None)
        if neighbor is None or not neighbor.route_target_filter:
            return False
        return (AFI.ipv4, SAFI.rtc) in self.families

    @property
    def confed_member(self) -> bool:
        """The peer is in another Member-AS of our confederation (RFC 5065)."""
        if not self.confederation or self.local_as == self.peer_as:
            return False
        return bool(self.neighbor.session.in_confederation(self.peer_as))

    @property
    def confed_outside(self) -> bool:
        """We are in a confederation and the peer is not (RFC 5065)."""
        return bool(self.confederation) and not self.neighbor.session.in_confederation(self.peer_as)

    @property
    def is_internal_neighbor(self) -> bool:
        """The peer is inside our AS, or in another Member-AS of our confederation.

        RFC 7606 7.5, 7.9 and 7.10 discard LOCAL_PREF, ORIGINATOR_ID and CLUSTER_LIST from
        an external neighbour. A neighbouring Member-AS is not external in that sense:
        RFC 5065 5.2 lifts the restriction on sending it LOCAL_PREF, and 5.3 has what it
        sends selected by the rules for a peer inside the AS.
        """
        return self.is_ibgp or self.confed_member

    @property
    def aigp_session(self) -> bool:
        """RFC 7311 3.3: whether the AIGP attribute is sent and accepted on this session.

        What the operator configured, or by default enabled on an internal session and on
        one to another Member-AS of our confederation, and disabled on every other one.
        Sending used to follow `aigp or is_ibgp` and receiving `aigp` alone, so `aigp
        false` still sent the attribute to an internal peer, and an internal peer left at
        the default was sent the attribute it then had discarded on the way back.
        """
        if self.aigp == TriState.UNSET:
            return self.is_internal_neighbor
        return self.aigp == TriState.TRUE

    @property
    def accepts_tunnel_encapsulation(self) -> bool:
        """Whether a received Tunnel Encapsulation attribute is kept (RFC 9012 11).

        `tunnel-encapsulation auto`, the default, filters it from every external neighbour,
        which RFC 9012 11 requires, and keeps it inside the AS and the confederation: the
        scope the attribute is meant for is a set of ASes run by one administration.
        """
        neighbor = getattr(self, 'neighbor', None)
        setting = neighbor.tunnel_encapsulation if neighbor is not None else 'auto'
        if setting == 'auto':
            return self.is_internal_neighbor
        return setting == 'accept'

    def required(self, afi: AFI, safi: SAFI) -> bool:
        """Get addpath status based on internal direction - if IN use receive, else use send"""
        from exabgp.bgp.message.direction import Direction

        if self.direction == Direction.IN:
            return self.addpath.receive(afi, safi)
        else:
            return self.addpath.send(afi, safi)

    @property
    def from_peer(self) -> bool:
        """Whether what is decoded with this came from the peer, and gets a receiver's checks."""
        from exabgp.bgp.message.direction import Direction

        return self.direction == Direction.IN

    def outbound(self) -> 'Negotiated':
        """This session, to decode what we sent on it rather than what the peer sent us.

        An UPDATE we wrote is read with ADD-PATH as we send it, and without the checks a
        receiver makes on its peer's routes (UpdateCollection._parse_payload). The negotiated
        values are shared, not copied: they are fixed once both OPENs are known. The
        attribute cache is not, so that our own UPDATEs never fill the cache of the peer's.
        """
        from exabgp.bgp.message.direction import Direction

        sent = Negotiated(self._neighbor, Direction.OUT)
        sent.attribute_cache_enabled = False
        sent.sent_open, sent.received_open = self.sent_open, self.received_open
        sent.holdtime, sent.local_as, sent.peer_as = self.holdtime, self.local_as, self.peer_as
        sent.families, sent.nexthop, sent.asn4 = self.families, self.nexthop, self.asn4
        sent.addpath, sent.multisession, sent.msg_size = self.addpath, self.multisession, self.msg_size
        sent.receive_msg_size = self.receive_msg_size
        sent.operational, sent.refresh, sent.aigp = self.operational, self.refresh, self.aigp
        sent.role, sent.peer_role, sent.role_otc = self.role, self.peer_role, self.role_otc
        sent.role_error, sent.linklocal_nexthop = self.role_error, self.linklocal_nexthop
        sent.paths_limit, sent.advertised_paths_limit = self.paths_limit, self.advertised_paths_limit
        sent.multiple_labels, sent.mismatch = self.multiple_labels, self.mismatch
        sent.accepted_labels = self.accepted_labels
        return sent


# =================================================================== RequirePath


class RequirePath:
    CANT: ClassVar[int] = 0b00
    RECEIVE: ClassVar[int] = 0b01
    SEND: ClassVar[int] = 0b10
    BOTH: ClassVar[int] = SEND | RECEIVE

    def __init__(self) -> None:
        self._send: dict[FamilyTuple, bool] = {}
        self._receive: dict[FamilyTuple, bool] = {}

    def setup(self, received_open: Any, sent_open: Any) -> None:  # Open messages
        # a side which did not send ADD-PATH has no family: only keys() and get() are read
        receive = received_open.capabilities.get(Capability.CODE.ADD_PATH, {})
        send = sent_open.capabilities.get(Capability.CODE.ADD_PATH, {})
        if not self._understood(receive):
            receive = {}

        # python 2.4 compatibility mean no simple union but using sets.Set
        union: list[FamilyTuple] = []
        union.extend(send.keys())
        union.extend([k for k in receive.keys() if k not in send.keys()])

        for k in union:
            here_will_send = bool(send.get(k, self.CANT) & self.SEND)
            they_will_recv = bool(receive.get(k, self.CANT) & self.RECEIVE)

            here_will_recv = bool(send.get(k, self.CANT) & self.RECEIVE)
            they_will_send = bool(receive.get(k, self.CANT) & self.SEND)

            self._send[k] = here_will_send and they_will_recv
            self._receive[k] = here_will_recv and they_will_send

    @classmethod
    def _understood(cls, addpath: Any) -> bool:
        """Whether every Send/Receive value of an ADD-PATH capability is one RFC 7911 defines.

        RFC 7911 4: for a value other than 1, 2 or 3 "the capability SHOULD be treated as
        not understood and ignored". Read as a bitmask, 7 claimed send and receive both.
        """
        return all(cls.RECEIVE <= send_receive <= cls.BOTH for send_receive in addpath.values())

    def send(self, afi: AFI, safi: SAFI) -> bool:
        return self._send.get((afi, safi), False)

    def receive(self, afi: AFI, safi: SAFI) -> bool:
        return self._receive.get((afi, safi), False)


# Initialize the sentinel instance
Negotiated.UNSET = Negotiated._create_unset()
