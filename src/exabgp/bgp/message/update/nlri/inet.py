"""inet.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)

RFC References:
===============

RFC 4271 - A Border Gateway Protocol 4 (BGP-4)
https://www.rfc-editor.org/rfc/rfc4271.html

    Section 4.3 - UPDATE Message Format:
    The base NLRI format for IPv4 unicast/multicast routes in the
    UPDATE message NLRI field (after path attributes):

        +---------------------------+
        |   Length (1 octet)        |  <- Prefix length in BITS
        +---------------------------+
        |   Prefix (variable)       |  <- ceiling(Length/8) bytes
        +---------------------------+

    Multiple NLRI can be packed consecutively in the UPDATE.

RFC 4760 - Multiprotocol Extensions for BGP-4
https://www.rfc-editor.org/rfc/rfc4760.html

    Enables BGP to carry routing information for multiple address families.
    Uses MP_REACH_NLRI (type 14) and MP_UNREACH_NLRI (type 15) attributes.

    Key AFI/SAFI values for INET:
        AFI 1 (IPv4), SAFI 1 (unicast)  - IPv4 unicast
        AFI 1 (IPv4), SAFI 2 (multicast) - IPv4 multicast
        AFI 2 (IPv6), SAFI 1 (unicast)  - IPv6 unicast
        AFI 2 (IPv6), SAFI 2 (multicast) - IPv6 multicast

RFC 7911 - Advertisement of Multiple Paths in BGP (ADD-PATH)
https://www.rfc-editor.org/rfc/rfc7911.html

    Adds a 4-byte Path Identifier before each NLRI to allow
    advertising multiple paths for the same prefix:

        +---------------------------+
        |   Path ID (4 octets)      |  <- Only if ADD-PATH negotiated
        +---------------------------+
        |   Length (1 octet)        |
        +---------------------------+
        |   Prefix (variable)       |
        +---------------------------+

Wire Format (_packed):
=====================
    This class stores ONLY the NLRI payload bytes (not BGP message framing).

    _packed stores: [mask_byte][truncated_ip_bytes...]
    - This is the CIDR portion only (same as CIDR class)
    - path_info, nexthop stored separately (not in _packed)
    - labels, rd are None for base INET (subclasses override)

    Note: path_info (ADD-PATH) is parsed separately during unpack and
    stored in self.path_info. It is NOT included in _packed.

Class Hierarchy:
===============
    INET (this class) - base for unicast/multicast
      └── Label (label.py) - adds MPLS label stack (RFC 3107)
            └── IPVPN (ipvpn.py) - adds Route Distinguisher (RFC 4364)
"""

from __future__ import annotations

from struct import unpack
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.notification import Notify

# INET NLRI label constants (RFC 3107)
LABEL_SIZE_BITS: int = 24  # Each MPLS label is 24 bits (3 bytes)
LABEL_WITHDRAW_VALUE: int = 0x800000  # Special label value for route withdrawal
LABEL_NEXTHOP_VALUE: int = 0x000000  # Special label value indicating next-hop
LABEL_BOTTOM_OF_STACK_BIT: int = 1  # Bottom of stack bit in label

# AddPath path-info size
PATH_INFO_SIZE: int = 4  # Path Identifier is 4 bytes (RFC 7911)


@NLRI.register(AFI.ipv4, SAFI.unicast)
@NLRI.register(AFI.ipv6, SAFI.unicast)
@NLRI.register(AFI.ipv4, SAFI.multicast)
@NLRI.register(AFI.ipv6, SAFI.multicast)
class INET(NLRI):
    # Maximum IPv4 prefix length - masks > 32 indicate IPv6
    _IPV4_MAX_MASK = 32

    def __init__(self, packed: bytes) -> None:
        """Create an INET NLRI from packed CIDR bytes.

        Args:
            packed: CIDR wire format bytes [mask_byte][truncated_ip...]

        AFI is inferred from mask (>32 implies IPv6).
        SAFI defaults to unicast. Use factory methods for other families.
        """
        # Infer AFI from mask: > 32 can only be IPv6
        afi = AFI.ipv6 if packed[0] > self._IPV4_MAX_MASK else AFI.ipv4
        NLRI.__init__(self, afi, SAFI.unicast, Action.UNSET)
        self._packed = packed  # CIDR wire format
        self.path_info = PathInfo.DISABLED
        self.nexthop = IP.NoNextHop
        self.labels: Labels | None = None
        self.rd: RouteDistinguisher | None = None

    @property
    def cidr(self) -> CIDR:
        """Unpack CIDR from stored wire format bytes."""
        if self.afi == AFI.ipv4:
            return CIDR.from_ipv4(self._packed)
        return CIDR.from_ipv6(self._packed)

    @classmethod
    def from_cidr(
        cls,
        cidr: CIDR,
        afi: AFI,
        safi: SAFI,
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
    ) -> 'INET':
        """Factory method to create INET from a CIDR object.

        Args:
            cidr: CIDR prefix
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier

        Returns:
            New INET instance
        """
        instance = object.__new__(cls)
        NLRI.__init__(instance, afi, safi, action)
        instance._packed = cidr.pack_nlri()
        instance.path_info = path_info
        instance.nexthop = IP.NoNextHop
        instance.labels = None
        instance.rd = None
        return instance

    @classmethod
    def make_route(
        cls,
        afi: AFI,
        safi: SAFI,
        packed: bytes,
        mask: int,
        action: Action = Action.ANNOUNCE,
        path_info: PathInfo = PathInfo.DISABLED,
        nexthop: 'IP | None' = None,
    ) -> 'INET':
        """Factory method to create an INET route.

        Args:
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            packed: Packed IP address bytes (full length)
            mask: Prefix length
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier
            nexthop: Next-hop IP address

        Returns:
            New INET instance
        """
        cidr = CIDR.make_cidr(packed, mask)
        instance = cls.from_cidr(cidr, afi, safi, action, path_info)
        if nexthop is not None:
            instance.nexthop = nexthop
        return instance

    def __len__(self) -> int:
        return len(self._packed) + len(self.path_info)

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __hash__(self) -> int:
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        return hash(addpath + self._pack_nlri_simple())

    def feedback(self, action: Action) -> str:  # type: ignore[override]
        if self.nexthop is IP.NoNextHop and action == Action.ANNOUNCE:
            return 'inet nlri next-hop missing'
        return ''

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        return self._packed

    def pack_nlri(self, negotiated: 'Negotiated') -> bytes:
        if negotiated.addpath.send(self.afi, self.safi):
            # ADD-PATH negotiated: MUST send 4-byte path ID
            if self.path_info is PathInfo.DISABLED:
                addpath = PathInfo.NOPATH.pack_path()
            else:
                addpath = self.path_info.pack_path()
        else:
            addpath = b''
        return addpath + self._pack_nlri_simple()

    def index(self) -> bytes:
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        return Family.index(self) + addpath + self._packed

    def prefix(self) -> str:
        return '{}{}'.format(self.cidr.prefix(), str(self.path_info))

    def extensive(self) -> str:
        return '{}{}'.format(self.prefix(), '' if self.nexthop is IP.NoNextHop else ' next-hop {}'.format(self.nexthop))

    def _internal(self, announced: bool = True) -> list[str]:
        return [self.path_info.json()]

    # The announced feature is not used by ExaBGP, is it by BAGPIPE ?

    def json(self, announced: bool = True, compact: bool = False) -> str:  # type: ignore[override]
        internal = ', '.join([_ for _ in self._internal(announced) if _])
        if internal:
            return '{{ "nlri": "{}", {} }}'.format(self.cidr.prefix(), internal)
        if compact:
            return '"{}"'.format(self.cidr.prefix())
        return '{{ "nlri": "{}" }}'.format(self.cidr.prefix())

    @classmethod
    def _pathinfo(cls, data: bytes, addpath: Any) -> tuple[PathInfo, bytes]:
        if addpath:
            return PathInfo(data[:4]), data[4:]
        return PathInfo.DISABLED, data

    # @classmethod
    # def unpack_inet (cls, afi, safi, data, action, addpath):
    # 	pathinfo, data = cls._pathinfo(data,addpath)
    # 	nlri,data = cls.unpack_range(data,action,addpath)
    # 	nlri.path_info = pathinfo
    # 	return nlri,data

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[INET, bytes]:
        # Parse path_info if AddPath is enabled
        if addpath:
            if len(bgp) <= PATH_INFO_SIZE:
                raise ValueError('Trying to extract path-information but we do not have enough data')
            path_info = PathInfo(bgp[:PATH_INFO_SIZE])
            bgp = bgp[PATH_INFO_SIZE:]
        else:
            path_info = PathInfo.DISABLED

        mask = bgp[0]
        bgp = bgp[1:]

        _, rd_size = Family.size.get((afi, safi), (0, 0))
        rd_mask = rd_size * 8

        # Parse labels if present
        labels_list: list[int] | None = None
        if safi.has_label():
            labels_list = []
            while mask - rd_mask >= LABEL_SIZE_BITS:
                label = int(unpack('!L', bytes([0]) + bgp[:3])[0])
                bgp = bgp[3:]
                mask -= LABEL_SIZE_BITS  # 3 bytes
                # The last 4 bits are the bottom of Stack
                # The last bit is set for the last label
                labels_list.append(label >> 4)
                # This is a route withdrawal
                if label == LABEL_WITHDRAW_VALUE and action == Action.WITHDRAW:
                    break
                # This is a next-hop
                if label == LABEL_NEXTHOP_VALUE:
                    break
                if label & LABEL_BOTTOM_OF_STACK_BIT:
                    break

        # Parse route distinguisher if present
        rd: RouteDistinguisher | None = None
        if rd_size:
            mask -= rd_mask  # the route distinguisher
            rd = RouteDistinguisher(bgp[:rd_size])
            bgp = bgp[rd_size:]

        if mask < 0:
            raise Notify(3, 10, 'invalid length in NLRI prefix')

        if not bgp and mask:
            raise Notify(3, 10, 'not enough data for the mask provided to decode the NLRI')

        size = CIDR.size(mask)

        if len(bgp) < size:
            raise Notify(
                3,
                10,
                'could not decode nlri with family %s (AFI %d) %s (SAFI %d)'
                % (AFI(afi), int(afi), SAFI(safi), int(safi)),
            )

        network, bgp = bgp[:size], bgp[size:]

        # Create NLRI from CIDR
        if afi == AFI.ipv4:
            cidr = CIDR.from_ipv4(bytes([mask]) + network)
        else:
            cidr = CIDR.from_ipv6(bytes([mask]) + network)
        nlri = cls.from_cidr(cidr, afi, safi, action, path_info)

        # Set optional attributes
        if labels_list is not None:
            nlri.labels = Labels.make_labels(labels_list)
        if rd is not None:
            nlri.rd = rd

        return nlri, bgp
