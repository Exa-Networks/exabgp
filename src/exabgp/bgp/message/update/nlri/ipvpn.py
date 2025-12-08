"""ipvpn.py (BGP/MPLS IP VPNs - VPNv4/VPNv6)

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)

RFC References:
===============

RFC 4364 - BGP/MPLS IP Virtual Private Networks (VPNs)
https://www.rfc-editor.org/rfc/rfc4364.html

    Defines VPN-IPv4 (VPNv4) address family for MPLS VPNs.
    SAFI value: 128 (mpls_vpn)

    VPN-IPv4 NLRI wire format (within MP_REACH_NLRI payload):

        +---------------------------+
        |   Length (1 octet)        |  <- Total bits: labels + RD + prefix
        +---------------------------+
        |   Label(s) (3+ octets)    |  <- MPLS label stack (per RFC 3107)
        +---------------------------+
        |   RD (8 octets)           |  <- Route Distinguisher
        +---------------------------+
        |   Prefix (variable)       |  <- IPv4 prefix bytes
        +---------------------------+

    Length field calculation:
        Length = (num_labels * 24) + 64 + prefix_mask_bits
        Example: /24 with 1 label = 24 + 64 + 24 = 112 bits

RFC 4659 - BGP-MPLS IP VPN Extension for IPv6 VPN
https://www.rfc-editor.org/rfc/rfc4659.html

    Extends RFC 4364 for IPv6 VPNs (VPNv6).
    AFI 2 (IPv6), SAFI 128 (mpls_vpn)

    VPN-IPv6 address: 8-byte RD + 16-byte IPv6 = 24 bytes total

Route Distinguisher (RD) Encoding:
=================================
    RD is 8 bytes: 2-byte type + 6-byte value

    Type 0 (ASN2:NN):
        +---------------------------+
        |   Type (2 octets) = 0     |
        +---------------------------+
        |   ASN (2 octets)          |  <- 2-byte AS number
        +---------------------------+
        |   Assigned (4 octets)     |  <- Admin-assigned value
        +---------------------------+

    Type 1 (IP:NN):
        +---------------------------+
        |   Type (2 octets) = 1     |
        +---------------------------+
        |   IP (4 octets)           |  <- IPv4 address
        +---------------------------+
        |   Assigned (2 octets)     |  <- Admin-assigned value
        +---------------------------+

    Type 2 (ASN4:NN):
        +---------------------------+
        |   Type (2 octets) = 2     |
        +---------------------------+
        |   ASN (4 octets)          |  <- 4-byte AS number
        +---------------------------+
        |   Assigned (2 octets)     |  <- Admin-assigned value
        +---------------------------+

Wire Format (_packed):
=====================
    This class stores ONLY the CIDR payload in _packed (not the full VPN NLRI).

    _packed stores: [mask_byte][truncated_ip_bytes...]  (same as INET/Label)
    self.labels stores: Labels object with the MPLS label stack
    self.rd stores: RouteDistinguisher object

    On pack_nlri(), these are combined:
        output = [length][labels][rd][prefix]
        where length = labels*24 + 64 + mask

    Note: path_info (ADD-PATH) is stored in self.path_info, NOT in _packed.

Class Hierarchy:
===============
    INET (inet.py) - base for unicast/multicast
      └── Label (label.py) - adds MPLS label stack
            └── IPVPN (this class) - adds Route Distinguisher
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import INETSettings

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import (
    LABEL_BOTTOM_OF_STACK_BIT,
    LABEL_NEXTHOP_VALUE,
    LABEL_SIZE_BITS,
    LABEL_WITHDRAW_VALUE,
    PATH_INFO_SIZE,
)
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo, RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP

# ====================================================== IPVPN
# RFC 4364

# Route Distinguisher size in bytes
RD_SIZE = 8
RD_SIZE_BITS = RD_SIZE * 8


@NLRI.register(AFI.ipv4, SAFI.mpls_vpn)
@NLRI.register(AFI.ipv6, SAFI.mpls_vpn)
class IPVPN(Label):
    """IPVPN NLRI with separate storage for CIDR, labels, and RD.

    Wire format: [mask][labels][rd][prefix]
    Storage: _packed (CIDR), _labels_packed (labels bytes), _rd_packed (RD bytes)
    pack_nlri() = concatenation of all parts with computed mask

    Uses class-level SAFI (always mpls_vpn) - no instance storage needed.
    """

    __slots__ = ('_rd_packed',)

    # Fixed SAFI for IPVPN NLRI (class attribute shadows slot)
    # AFI varies (ipv4/ipv6) and is set at instance level by INET
    safi: ClassVar[SAFI] = SAFI.mpls_vpn

    def __init__(self, packed: bytes, afi: AFI, *, has_addpath: bool = False) -> None:
        """Create an IPVPN NLRI from packed wire format bytes.

        Args:
            packed: Wire format bytes [addpath:4?][mask:1][prefix:var]
            afi: Address Family Identifier
            has_addpath: If True, packed includes 4-byte path identifier at start

        SAFI is always mpls_vpn (class-level). Use factory methods for creation.
        """
        Label.__init__(self, packed, afi, has_addpath=has_addpath)
        self._rd_packed: bytes = b''  # RD bytes (empty = NORD)

    @property
    def rd(self) -> RouteDistinguisher:
        """Get Route Distinguisher from stored bytes."""
        if not self._rd_packed:
            return RouteDistinguisher.NORD
        return RouteDistinguisher(self._rd_packed)

    @classmethod
    def from_cidr(
        cls,
        cidr: CIDR,
        afi: AFI,
        safi: SAFI = SAFI.mpls_vpn,  # Default to class SAFI; parameter kept for API compat
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
        labels: Labels | None = None,
        rd: RouteDistinguisher | None = None,
    ) -> 'IPVPN':
        """Factory method to create IPVPN from a CIDR object.

        Args:
            cidr: CIDR prefix
            afi: Address Family Identifier
            safi: Ignored - IPVPN always uses mpls_vpn (kept for API compatibility)
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier
            labels: MPLS label stack (optional, defaults to NOLABEL)
            rd: Route Distinguisher (optional, defaults to NORD)

        Returns:
            New IPVPN instance with SAFI=mpls_vpn
        """
        # Build wire format: [addpath:4?][mask:1][prefix:var]
        # Note: Labels and RD are stored separately in _labels_packed and _rd_packed for now
        cidr_packed = cidr.pack_nlri()
        has_addpath = path_info is not PathInfo.DISABLED
        if has_addpath:
            packed = bytes(path_info.pack_path()) + cidr_packed
        else:
            packed = cidr_packed

        instance = object.__new__(cls)
        # Note: safi parameter is ignored - IPVPN.safi is a class-level property
        NLRI.__init__(instance, afi, cls.safi, action)
        instance._packed = packed
        instance._has_addpath = has_addpath
        instance.nexthop = IP.NoNextHop
        instance._labels_packed = labels.pack_labels() if labels is not None else b''
        instance._rd_packed = rd.pack_rd() if rd is not None else b''
        return instance

    @classmethod
    def from_settings(cls, settings: 'INETSettings') -> 'IPVPN':
        """Create IPVPN NLRI from validated settings.

        This factory method validates settings and creates an immutable IPVPN
        instance with labels and route distinguisher. Use this for deferred
        construction where all values are collected during parsing, then
        validated and used to create the NLRI.

        Args:
            settings: INETSettings with all required fields set (including labels and rd)

        Returns:
            Immutable IPVPN NLRI instance

        Raises:
            ValueError: If settings validation fails
        """
        error = settings.validate()
        if error:
            raise ValueError(error)

        # Assertions for type narrowing after validation
        assert settings.cidr is not None
        assert settings.afi is not None
        assert settings.safi is not None

        instance = cls.from_cidr(
            cidr=settings.cidr,
            afi=settings.afi,
            safi=settings.safi,
            action=settings.action,
            path_info=settings.path_info,
            labels=settings.labels,
            rd=settings.rd,
        )
        instance.nexthop = settings.nexthop
        return instance

    def feedback(self, action: Action) -> str:
        if self.nexthop is IP.NoNextHop and action == Action.ANNOUNCE:
            return 'ip-vpn nlri next-hop missing'
        return ''

    @classmethod
    def make_vpn_route(
        cls,
        afi: AFI,
        safi: SAFI,
        packed: bytes,
        mask: int,
        labels: Labels,
        rd: RouteDistinguisher,
        nexthop: str | None = None,
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
    ) -> 'IPVPN':
        """Factory method to create an IPVPN route."""
        cidr = CIDR.make_cidr(packed, mask)
        instance = cls.from_cidr(cidr, afi, safi, action, path_info, labels=labels, rd=rd)
        instance.nexthop = IP.from_string(nexthop) if nexthop else IP.NoNextHop
        return instance

    def extensive(self) -> str:
        return '{}{}'.format(Label.extensive(self), str(self.rd))

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __len__(self) -> int:
        # Total length = _packed (includes addpath if present) + labels + rd
        return len(self._packed) + len(self._labels_packed) + len(self._rd_packed)

    def __eq__(self, other: Any) -> bool:
        return Label.__eq__(self, other) and self._rd_packed == other._rd_packed

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        mask = len(self._labels_packed) * 8 + len(self._rd_packed) * 8 + self.cidr.mask
        return hash(addpath + bytes([mask]) + self._labels_packed + self._rd_packed + self.cidr.pack_ip())

    def __copy__(self) -> 'IPVPN':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi - safi is class-level)
        new.afi = self.afi
        # NLRI slots
        self._copy_nlri_slots(new)
        # INET slots
        new._has_addpath = self._has_addpath
        # Label slots
        new._labels_packed = self._labels_packed
        # IPVPN slots
        new._rd_packed = self._rd_packed
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'IPVPN':
        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family slots (afi - safi is class-level)
        new.afi = self.afi
        # NLRI slots
        self._deepcopy_nlri_slots(new, memo)
        # INET slots
        new._has_addpath = self._has_addpath  # bool - immutable
        # Label slots
        new._labels_packed = self._labels_packed  # bytes - immutable
        # IPVPN slots
        new._rd_packed = self._rd_packed  # bytes - immutable
        return new

    @classmethod
    def has_rd(cls) -> bool:
        return True

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # Wire format: [addpath?][mask][labels][rd][prefix]
        mask = len(self._labels_packed) * 8 + len(self._rd_packed) * 8 + self.cidr.mask
        packed = bytes([mask]) + self._labels_packed + self._rd_packed + self.cidr.pack_ip()

        if not negotiated.addpath.send(self.afi, self.safi):
            return packed  # No addpath - return directly

        # ADD-PATH negotiated: MUST prepend 4-byte path ID
        if self.path_info is PathInfo.DISABLED:
            addpath = PathInfo.NOPATH.pack_path()
        else:
            addpath = self.path_info.pack_path()
        return bytes(addpath) + packed

    def index(self) -> bytes:
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        # Index uses RD + prefix (without labels) for uniqueness
        mask = bytes([len(self._rd_packed) * 8 + self.cidr.mask])
        return Family.index(self) + addpath + mask + self._rd_packed + self.cidr.pack_ip()

    def _internal(self, announced: bool = True) -> list[str]:
        r = Label._internal(self, announced)
        if announced and self._rd_packed:
            r.append(self.rd.json())
        return r

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        """Unpack IPVPN NLRI from wire format.

        Uses SAFI to determine RD presence (exact, not heuristic).
        Wire format: [mask][labels][rd][prefix]
        """
        from struct import unpack

        # Parse path_info if AddPath is enabled
        if addpath:
            if len(data) <= PATH_INFO_SIZE:
                raise ValueError('Trying to extract path-information but we do not have enough data')
            path_info = PathInfo(bytes(data[:PATH_INFO_SIZE]))
            data = data[PATH_INFO_SIZE:]
        else:
            path_info = PathInfo.DISABLED

        mask = data[0]
        data = data[1:]

        # Get RD size from Family.size (exact, not heuristic)
        _, rd_size = Family.size.get((afi, safi), (0, 0))
        rd_bits = rd_size * 8

        # Parse labels using mask (original algorithm from INET.unpack_nlri)
        labels_list: list[int] = []
        if safi.has_label():
            while mask - rd_bits >= LABEL_SIZE_BITS:
                label = int(unpack('!L', bytes([0]) + bytes(data[:3]))[0])
                data = data[3:]
                mask -= LABEL_SIZE_BITS
                labels_list.append(label >> 4)
                if label == LABEL_WITHDRAW_VALUE and action == Action.WITHDRAW:
                    break
                if label == LABEL_NEXTHOP_VALUE:
                    break
                if label & LABEL_BOTTOM_OF_STACK_BIT:
                    break

        # Parse RD if present (exact from SAFI, not heuristic)
        rd_packed = b''
        if rd_size:
            mask -= rd_bits
            rd_packed = bytes(data[:rd_size])
            data = data[rd_size:]

        if mask < 0:
            raise Notify(3, 10, 'invalid length in NLRI prefix')

        if not data and mask:
            raise Notify(3, 10, 'not enough data for the mask provided')

        # Parse prefix
        size = CIDR.size(mask)
        if len(data) < size:
            raise Notify(3, 10, f'could not decode IPVPN NLRI with family {AFI.from_int(afi)} {SAFI.from_int(safi)}')

        network, data = data[:size], data[size:]

        # Build wire format: [addpath:4?][mask:1][prefix:var]
        cidr_packed = bytes([mask]) + bytes(network)
        has_addpath = path_info is not PathInfo.DISABLED
        if has_addpath:
            packed = bytes(path_info.pack_path()) + cidr_packed
        else:
            packed = cidr_packed

        # Create NLRI
        instance = object.__new__(cls)
        NLRI.__init__(instance, afi, safi, action)
        instance._packed = packed
        instance._has_addpath = has_addpath
        instance.nexthop = IP.NoNextHop
        instance._labels_packed = Labels.make_labels(labels_list).pack_labels() if labels_list else b''
        instance._rd_packed = rd_packed

        return instance, data
