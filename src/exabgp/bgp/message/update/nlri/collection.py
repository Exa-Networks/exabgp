"""collection.py

Wire-format NLRI container classes following the packed-bytes-first pattern.

Created for separation of wire format from semantic representation.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from struct import pack
from collections.abc import Mapping
from typing import cast, ClassVar, Generator, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.attribute.attribute import Attribute
    from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
    from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
    from exabgp.bgp.message.update.collection import RoutedNLRI

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.nlri.nlri import _UNPARSED, NLRI
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, SAFI_WITH_EXTENDED_NEXT_HOP
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

# RFC 4291 2.5.5.2: an IPv4-mapped IPv6 address is these twelve octets and the IPv4 address
IPV4_MAPPED_PREFIX = bytes(10) + b'\xff\xff'

# How much of an NLRI we can not encode goes in the log, so that a route which is dropped can
# be identified and decoded, without a four kilobyte FlowSpec NLRI filling the log on every
# cycle of a RIB which still holds it.
_LOG_NLRI_OCTETS = 32

# The narrowest NLRI there can be: a mask of zero, with no prefix octets behind it.
_MIN_NLRI_OCTETS = 1


class NLRICollection:
    """Wire-format NLRI container for IPv4 announce/withdraw sections.

    Dual-mode:
    - Wire mode: __init__(packed, afi, safi, addpath, action) - stores bytes, lazy parsing
    - Semantic mode: make_collection(afi, safi, nlris, action) - stores NLRI list

    This class follows the packed-bytes-first pattern where wire format
    is the canonical representation and semantic values are derived lazily.
    """

    _MODE_PACKED: ClassVar[int] = 1  # Created from wire bytes (unpack path)
    _MODE_NLRIS: ClassVar[int] = 2  # Created from NLRI list (semantic path)

    def __init__(self, packed: Buffer, afi: AFI, safi: SAFI, addpath: bool, action: Action = Action.UNSET) -> None:
        """Create NLRICollection from wire-format bytes.

        Args:
            packed: Raw NLRI section bytes from UPDATE message.
                    Format: sequence of [mask(1) + prefix_bytes...]
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            addpath: Whether AddPath is enabled for this AFI/SAFI
            action: Whether these are announcements or withdrawals.
        """
        self._packed = packed
        self._afi = afi
        self._safi = safi
        self._addpath = addpath
        self._action = action
        self._mode = self._MODE_PACKED
        self._nlris_cache: list[NLRI] = _UNPARSED

    @classmethod
    def make_collection(cls, afi: AFI, safi: SAFI, nlris: list[NLRI], action: Action) -> 'NLRICollection':
        """Create NLRICollection from semantic data (NLRI list).

        Args:
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            nlris: List of NLRI objects to include.
            action: Whether these are announcements or withdrawals.

        Returns:
            NLRICollection instance in semantic mode.
        """
        # Create instance with empty packed data (addpath=False for semantic mode)
        instance = cls(b'', afi, safi, addpath=False, action=action)
        # Switch to semantic mode
        instance._mode = cls._MODE_NLRIS
        instance._nlris_cache = nlris
        return instance

    @property
    def packed(self) -> Buffer:
        """Raw NLRI bytes.

        In wire mode: returns the stored wire bytes.
        In semantic mode: packs the NLRI list to wire format.
        """
        if self._mode == self._MODE_PACKED:
            return self._packed

        # Semantic mode: pack NLRIs to wire format
        if self._nlris_cache is _UNPARSED:
            return b''

        # Pack each NLRI using its _packed attribute (no addpath)
        # AddPath handling would be done at UPDATE message level
        packed = b''
        for nlri in self._nlris_cache:
            packed += nlri._packed
        return packed

    @property
    def nlris(self) -> list[NLRI]:
        """Get the list of NLRIs, parsing from wire format if needed."""
        if self._nlris_cache is not _UNPARSED:
            return self._nlris_cache

        if self._mode == self._MODE_PACKED:
            self._nlris_cache = self._parse_nlris()
            return self._nlris_cache

        return []

    def _parse_nlris(self) -> list[NLRI]:
        """Parse NLRIs from wire format using stored AFI/SAFI/addpath."""
        nlris: list[NLRI] = []
        data = self._packed

        # Handle empty data
        if not data:
            return nlris

        # Parse NLRIs using the factory
        from exabgp.bgp.message.open.capability.negotiated import Negotiated

        while data:
            nlri, data = NLRI.unpack_nlri(
                self._afi,
                self._safi,
                data,
                self._action,
                self._addpath,
                Negotiated.UNSET,
            )
            if nlri is not NLRI.INVALID:
                nlris.append(nlri)

        return nlris

    def __len__(self) -> int:
        """Return number of NLRIs in collection."""
        return len(self.nlris)

    def __repr__(self) -> str:
        return f'NLRICollection({self._afi}/{self._safi}, {len(self)} NLRIs)'


class MPNLRICollection:
    """Unified semantic container for MP_REACH/MP_UNREACH NLRIs.

    Stores NLRIs and attributes dict. Generates MPRNLRI or MPURNLRI
    wire format based on action (reach vs unreach).

    Two modes:
    - Bare NLRI mode: __init__(nlris, attributes, afi, safi)
      Used for MP_UNREACH (withdraws) where no nexthop is needed.
    - RoutedNLRI mode: from_routed(routed_nlris, attributes, afi, safi)
      Used for MP_REACH (announces) where nexthop comes from RoutedNLRI.
    """

    # Attribute flags and IDs for wire format generation
    _FLAG_OPTIONAL: ClassVar[int] = 0x80
    _CODE_MP_REACH_NLRI: ClassVar[int] = 14
    _CODE_MP_UNREACH_NLRI: ClassVar[int] = 15

    def __init__(
        self,
        nlris: list[NLRI],
        attributes: 'Mapping[int, Attribute]',
        afi: AFI,
        safi: SAFI,
    ) -> None:
        """Create MPNLRICollection from bare NLRIs (for unreach/withdraws).

        Args:
            nlris: List of NLRI objects (without nexthop).
            attributes: Dict of attributes indexed by Attribute.CODE (int).
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
        """
        self._nlris = nlris
        self._routed_nlris: 'list[RoutedNLRI]' = []  # Empty for bare NLRI mode
        self._attributes = attributes
        self._afi = afi
        self._safi = safi

    @classmethod
    def from_routed(
        cls,
        routed_nlris: 'list[RoutedNLRI]',
        attributes: 'Mapping[int, Attribute]',
        afi: AFI,
        safi: SAFI,
    ) -> 'MPNLRICollection':
        """Create MPNLRICollection from RoutedNLRIs (for reach/announces).

        Args:
            routed_nlris: List of RoutedNLRI (nlri + nexthop).
            attributes: Dict of attributes indexed by Attribute.CODE (int).
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier

        Returns:
            MPNLRICollection configured for reach mode with nexthops.
        """
        instance = cls([], attributes, afi, safi)
        instance._routed_nlris = routed_nlris
        # Also populate _nlris for compatibility (e.g., __len__)
        instance._nlris = [routed.nlri for routed in routed_nlris]
        return instance

    @classmethod
    def from_wire(
        cls,
        mprnlri: 'MPRNLRI | None',
        mpurnlri: 'MPURNLRI | None',
        attributes: 'Mapping[int, Attribute]',
        afi: AFI,
        safi: SAFI,
    ) -> 'MPNLRICollection':
        """Create from wire containers (reach and/or unreach).

        Args:
            mprnlri: MPRNLRI wire container (or None).
            mpurnlri: MPURNLRI wire container (or None).
            attributes: Dict of attributes indexed by Attribute.CODE.
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier

        Returns:
            MPNLRICollection with NLRIs from both containers.
        """
        nlris: list[NLRI] = []
        if mprnlri is not None:
            # Use list() to iterate without calling __len__
            nlris.extend(list(mprnlri))
        if mpurnlri is not None:
            nlris.extend(list(mpurnlri))
        return cls(nlris, attributes, afi, safi)

    @property
    def nlris(self) -> list[NLRI]:
        """Get NLRIs in this collection."""
        return self._nlris

    @property
    def attributes(self) -> 'Mapping[int, Attribute]':
        """Get attributes dict indexed by Attribute.CODE."""
        return self._attributes

    @property
    def afi(self) -> AFI:
        """Address Family Identifier."""
        return self._afi

    @property
    def safi(self) -> SAFI:
        """Subsequent Address Family Identifier."""
        return self._safi

    def _attribute_header(self, code: int, length: int) -> bytes:
        """Build attribute header (flag + code + length)."""
        flag = self._FLAG_OPTIONAL
        if length > 255:
            # Extended length
            flag |= 0x10
            return bytes([flag, code]) + pack('!H', length)
        return bytes([flag, code, length])

    def _attr_len(self, payload_len: int) -> int:
        """Calculate total attribute length including header."""
        return payload_len + (4 if payload_len > 255 else 3)

    def _redirects_to_next_hop(self) -> bool:
        """The routes carry draft-simpson-idr-flowspec-redirect-ip, whose target is the next hop.

        That community is the one thing which gives a flow next hop a meaning, and it is only
        sent when the operator wrote `redirect-simpson` or `redirect-to-nexthop-simpson`.
        """
        from exabgp.bgp.message.update.attribute.attribute import Attribute
        from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities
        from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficNextHopSimpson

        communities = self._attributes.get(Attribute.CODE.EXTENDED_COMMUNITY)
        if communities is None:
            return False
        # the attribute stored under EXTENDED_COMMUNITY is the EXTENDED_COMMUNITY attribute
        return any(
            community.COMMUNITY_TYPE == TrafficNextHopSimpson.COMMUNITY_TYPE
            and community.COMMUNITY_SUBTYPE == TrafficNextHopSimpson.COMMUNITY_SUBTYPE
            for community in cast(ExtendedCommunities, communities).communities
        )

    def _encode_nexthop(
        self,
        nlri_nexthop: IP,
        family_key: tuple[AFI, SAFI],
        negotiated: 'Negotiated',
    ) -> bytes:
        """Encode nexthop bytes for MP_REACH_NLRI.

        Handles link-local nexthop capability (RFC draft-ietf-idr-linklocal-capability):
        - 16-byte: link-local only (when LLNH negotiated) or global only
        - 32-byte: global + link-local (for IPv6 unicast/labeled)

        Args:
            nlri_nexthop: The route's next-hop IP address.
            family_key: (AFI, SAFI) tuple for the family.
            negotiated: BGP session parameters.

        Returns:
            Packed nexthop bytes (including RD if applicable).
        """
        from exabgp.protocol.family import Family

        if nlri_nexthop is IP.NoNextHop:
            return b''
        # RFC 8955 4: a flow specification is advertised with a next hop length of 0
        if family_key[1] in (SAFI.flow_ip, SAFI.flow_vpn) and not self._redirects_to_next_hop():
            return b''

        lengths, rd_size = Family.size.get(family_key, ((), 0))
        nh_rd = bytes(rd_size)

        try:
            nh_packed = nlri_nexthop.pack_ip()
        except TypeError:
            # Fallback for invalid nexthop
            return bytes([0]) * 4

        if family_key[0] != AFI.ipv6:
            if family_key[0] == AFI.ipv4 and nlri_nexthop.is_link_local() and not negotiated.linklocal_nexthop:
                # draft-ietf-idr-linklocal-capability 5: without both capabilities "a sender
                # MUST follow the rules in Section 3 of [RFC8950] and encode the Next Hop as
                # 32 octets", the unspecified address first (each behind its RD for VPN-IPv4)
                return nh_rd + bytes(len(nh_packed)) + nh_rd + nh_packed
            return nh_rd + nh_packed
        if nlri_nexthop.afi == AFI.ipv4:
            # RFC 4798 2 and RFC 4659 3.2.1.2: an IPv6 family without a four octet next hop
            # of its own carries an IPv4 one as an IPv4-mapped IPv6 address. Four bare
            # octets is a length RFC 2545 3 does not give an IPv6 next hop.
            if rd_size + len(nh_packed) in lengths:
                return nh_rd + nh_packed
            return nh_rd + IPV4_MAPPED_PREFIX + bytes(nh_packed)
        next_hop = self._ipv6_next_hop(nlri_nexthop, nh_packed, negotiated)
        if rd_size and len(next_hop) == 2 * len(nh_packed):
            # RFC 4659 3.2.1.1: the link-local address is "another VPN-IPv6 address" with
            # its own zero RD, 48 octets in all, not a second address behind one RD
            return nh_rd + next_hop[: len(nh_packed)] + nh_rd + next_hop[len(nh_packed) :]
        return nh_rd + next_hop

    @staticmethod
    def _lacks_extended_next_hop(nlri_nexthop: IP, family_key: tuple[AFI, SAFI], negotiated: 'Negotiated') -> bool:
        """An IPv4 route with an IPv6 next hop the peer did not agree to receive for this family.

        RFC 8950 4: "A BGP speaker MUST only advertise the IPv4 or VPN-IPv4 NLRI with an IPv6
        next hop to a BGP peer if the BGP speaker has first ascertained via the BGP Capability
        Advertisement that the BGP peer supports the Extended Next Hop Encoding capability for
        the relevant AFI/SAFI pair." The configuration refuses such a route; this catches what
        reaches the encoder another way, an API announcement or a capability the peer withheld.
        """
        afi, safi = family_key
        if afi != AFI.ipv4 or nlri_nexthop.afi != AFI.ipv6 or safi not in SAFI_WITH_EXTENDED_NEXT_HOP:
            return False
        return (afi, safi, AFI.ipv6) not in negotiated.nexthop

    @classmethod
    def _next_hop_refused(cls, nlri_nexthop: IP, family_key: tuple[AFI, SAFI], negotiated: 'Negotiated') -> str:
        """Why this session can not carry this next hop, '' when it can.

        Such a route is not sent. draft-ietf-idr-linklocal-capability 4: with "no IPv6 next
        hop addresses included in the next hop, the BGP route MUST not be advertised". The
        configuration and the API refuse what they can see; what is left is a capability the
        peer did not send. It used to raise RuntimeError out of the encoder, which reset the
        session, which came back with the route still in the RIB, and reset again.
        """
        if cls._lacks_extended_next_hop(nlri_nexthop, family_key, negotiated):
            return 'the peer did not negotiate an IPv6 next hop for this family (RFC 8950)'
        if not nlri_nexthop.is_link_local():
            return ''
        # draft-ietf-idr-linklocal-capability 4: "Link-Local IPv6 next hops MUST NOT be
        # included" for a peer more than one hop away, and nothing else is left to send
        if negotiated.is_multihop():
            return 'a link-local next hop can not reach a multihop peer (draft-ietf-idr-linklocal-capability 4)'
        if negotiated.linklocal_nexthop:
            return ''
        # an IPv4 route has the 32 octet form of draft-ietf-idr-linklocal-capability 5
        if family_key[0] == AFI.ipv4 and family_key[1] in SAFI_WITH_EXTENDED_NEXT_HOP:
            return ''
        # RFC 2545 3 gives an IPv6 route a global next hop, and the draft's link-local only
        # one applies "only when the capability ... has been ... negotiated" (section 2)
        return 'the peer did not negotiate the link-local next hop capability (draft-ietf-idr-linklocal-capability 2)'

    @staticmethod
    def _ipv6_next_hop(nlri_nexthop: IP, packed: Buffer, negotiated: 'Negotiated') -> bytes:
        """The IPv6 next hop, 16 octets or global then link-local, 32 (draft-ietf-idr-linklocal-capability)."""
        nh_packed = bytes(packed)
        if nlri_nexthop.is_link_local():
            # _next_hop_refused withheld it where the session can not carry it alone
            assert negotiated.linklocal_nexthop and not negotiated.is_multihop(), 'an unsendable next hop was encoded'
            return nh_packed

        # RFC 2545 3: the link-local address "shall be included ... if and only if" we share
        # a subnet with the global next hop and the peer. We only know that when the global
        # next hop is our own address on a session one hop away, and the capability being
        # negotiated is the operator saying the link is shared: a third party's next hop has
        # a link-local address of its own, not ours. The link-local-prefer option is for the
        # receiver's forwarding choice and never changes the order: global, then link-local.
        if not negotiated.linklocal_nexthop or negotiated.is_multihop():
            return nh_packed
        link_local = negotiated.link_local_address()
        if link_local is None or not negotiated.is_local_address(nlri_nexthop):
            return nh_packed
        return nh_packed + bytes(link_local.pack_ip())

    def _fragmented(
        self,
        code: int,
        preamble: bytes,
        packed_nlris: list[bytes],
        maximum: int,
    ) -> 'Generator[bytes, None, None]':
        """Fill MP attributes of at most `maximum` octets with as many of these NLRIs as fit.

        An NLRI which does not fit an attribute of its own is logged and left out.  No
        fragmentation can place it, and the limit is our own: the maximum here is what is left
        of an UPDATE once our attributes are in it, so the peer has done nothing and cannot be
        told anything useful.

        The two things this used to do instead both ended the session:

        * it raised `RuntimeError` when that NLRI was the first of its group, and nothing
          between here and `Peer._run`'s last resort `except Exception` catches it, so one
          route of ours reset an established session, losing every route of every family; and
          since the route is still in the RIB when the session comes back, it is a flap loop
          rather than a failure;
        * when the NLRI was not the first, it opened the next attribute with it and never
          asked whether it fitted there either, so the last fragment came out over the budget.
          RFC 4271 4.1 gives the maximum message size and 6.1 makes the peer answer a message
          over it with a NOTIFICATION, so the session went down from the other end.

        The native IPv4 pass of `UpdateCollection.messages` has always logged and dropped.

        Args:
            code: MP_REACH_NLRI or MP_UNREACH_NLRI attribute type code.
            preamble: The leading octets of the attribute, repeated in every fragment.
            packed_nlris: The NLRIs of this family, already in wire format.
            maximum: Maximum bytes per attribute, preamble and NLRIs included.

        Yields:
            Wire-format attribute bytes (with flags/type/length header).
        """
        attribute = 'MP_REACH_NLRI' if code == self._CODE_MP_REACH_NLRI else 'MP_UNREACH_NLRI'
        preamble_length = len(preamble)

        if self._attr_len(preamble_length + _MIN_NLRI_OCTETS) > maximum:
            # Not one NLRI of this family can be sent, which is one fact about our attributes
            # rather than one about each route, so it is said once.  Saying it per NLRI would
            # put a critical line per route in the log on every pass over the RIB.
            log.critical(
                lazymsg(
                    'update.pack.error reason=attributes_too_large attribute={attribute} afi={afi} safi={safi} '
                    'nlri_count={nlri_count} maximum_bytes={maximum_bytes} action=not_sent',
                    attribute=attribute,
                    afi=self._afi,
                    safi=self._safi,
                    nlri_count=len(packed_nlris),
                    maximum_bytes=maximum,
                ),
                'parser',
            )
            return

        fragment = preamble

        for packed_nlri in packed_nlris:
            if self._attr_len(preamble_length + len(packed_nlri)) > maximum:
                log.critical(
                    lazymsg(
                        'update.pack.error reason=nlri_too_large attribute={attribute} afi={afi} safi={safi} '
                        'nlri_bytes={nlri_bytes} maximum_bytes={maximum_bytes} nlri={nlri} action=not_sent',
                        attribute=attribute,
                        afi=self._afi,
                        safi=self._safi,
                        nlri_bytes=len(packed_nlri),
                        maximum_bytes=maximum,
                        nlri=packed_nlri[:_LOG_NLRI_OCTETS].hex(),
                    ),
                    'parser',
                )
                continue
            if self._attr_len(len(fragment) + len(packed_nlri)) > maximum:
                assert self._attr_len(len(fragment)) <= maximum, 'an MP attribute grew past the budget'
                yield self._attribute_header(code, len(fragment)) + fragment
                fragment = preamble
            fragment = fragment + packed_nlri

        if len(fragment) > preamble_length:
            assert self._attr_len(len(fragment)) <= maximum, 'the last MP attribute grew past the budget'
            yield self._attribute_header(code, len(fragment)) + fragment

    def packed_reach_attributes(
        self,
        negotiated: 'Negotiated',
        maximum: int = 4096,
    ) -> 'Generator[bytes, None, None]':
        """Generate MP_REACH_NLRI wire-format attributes.

        Groups NLRIs by nexthop, handles fragmentation.

        Args:
            negotiated: BGP session parameters.
            maximum: Maximum bytes per attribute (default 4096).

        Yields:
            Wire-format attribute bytes (with flags/type/length header).
        """
        # Filter NLRIs for this family and group by nexthop
        mpnlri: dict[bytes, list[bytes]] = {}
        family_key = (self._afi, self._safi)

        # Use _routed_nlris to get nexthop from RoutedNLRI container
        for routed in self._routed_nlris:
            nlri = routed.nlri
            nlri_nexthop = routed.nexthop
            if nlri.family().afi_safi() != family_key:
                continue

            refused = self._next_hop_refused(nlri_nexthop, family_key, negotiated)
            if refused:
                log.warning(
                    lazymsg(
                        'update.route.refused nlri={nlri} nexthop={nexthop} reason="{reason}"',
                        nlri=nlri,
                        nexthop=nlri_nexthop,
                        reason=refused,
                    ),
                    'parser',
                )
                continue

            # Encode nexthop with LLNH support
            nexthop = self._encode_nexthop(nlri_nexthop, family_key, negotiated)

            mpnlri.setdefault(nexthop, []).append(bytes(nlri.pack_nlri(negotiated)))

        # Generate attributes for each nexthop group
        afi_bytes = self._afi.pack_afi()
        safi_bytes = self._safi.pack_safi()

        for nexthop, packed_nlris in mpnlri.items():
            # Build header: AFI(2) + SAFI(1) + NH_len(1) + NH + reserved(1)
            header = afi_bytes + safi_bytes + bytes([len(nexthop)]) + nexthop + bytes([0])
            yield from self._fragmented(self._CODE_MP_REACH_NLRI, header, packed_nlris, maximum)

    def packed_unreach_attributes(
        self,
        negotiated: 'Negotiated',
        maximum: int = 4096,
    ) -> 'Generator[bytes, None, None]':
        """Generate MP_UNREACH_NLRI wire-format attributes.

        Handles fragmentation only (no nexthop grouping).

        Args:
            negotiated: BGP session parameters.
            maximum: Maximum bytes per attribute (default 4096).

        Yields:
            Wire-format attribute bytes (with flags/type/length header).
        """
        # Filter and pack NLRIs for this family
        family_key = (self._afi, self._safi)
        packed_nlris: list[bytes] = []

        for nlri in self._nlris:
            if nlri.family().afi_safi() != family_key:
                continue
            packed_nlris.append(bytes(nlri.pack_withdraw(negotiated)))

        if not packed_nlris:
            return

        # Build header: AFI(2) + SAFI(1)
        header = self._afi.pack_afi() + self._safi.pack_safi()
        yield from self._fragmented(self._CODE_MP_UNREACH_NLRI, header, packed_nlris, maximum)

    def __len__(self) -> int:
        """Return number of NLRIs in collection."""
        return len(self._nlris)

    def __repr__(self) -> str:
        return f'MPNLRICollection({self._afi}/{self._safi}, {len(self)} NLRIs)'
