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

Wire Format (_packed) - Packed-Bytes-First Pattern (Complete):
==============================================================
    This class stores complete wire format in _packed (Phase 3 complete).

    _packed stores: [addpath:4?][mask:1][labels:3n][rd:8][prefix:var]
    - mask = combined mask (labels + RD + prefix bits)
    - labels = raw MPLS label bytes (if _has_labels)
    - rd = Route Distinguisher bytes (if _has_rd)
    - prefix = truncated IP prefix bytes

    pack_nlri() returns _packed directly (zero-copy).

    Properties extract data lazily:
    - labels: inherited from Label, scans for BOS bit
    - rd: extracts from _packed[label_end:label_end+8] if _has_rd
    - cidr: extracts from after RD using _rd_end_offset

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

# ====================================================== IPVPN
# RFC 4364

# Route Distinguisher size in bytes
RD_SIZE = 8
RD_SIZE_BITS = RD_SIZE * 8


@NLRI.register(AFI.ipv4, SAFI.mpls_vpn)
@NLRI.register(AFI.ipv6, SAFI.mpls_vpn)
class IPVPN(Label):
    """IPVPN NLRI using complete packed-bytes-first pattern.

    Wire format stored in _packed: [addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]
    - mask = combined mask (labels + RD + prefix bits)
    - labels = raw MPLS label bytes (if _has_labels)
    - rd = Route Distinguisher bytes (if _has_rd)
    - prefix = truncated IP prefix bytes

    pack_nlri() returns _packed directly (zero-copy).

    Properties extract data lazily:
    - labels: inherited from Label, scans for BOS bit
    - rd: extracts from _packed[label_end:label_end+8] if _has_rd
    - cidr: extracts from after RD using _rd_end_offset

    Uses class-level SAFI (always mpls_vpn) - no instance storage needed.
    """

    __slots__ = ('_has_rd',)  # Track whether RD is present in _packed

    # Fixed SAFI for IPVPN NLRI (class attribute shadows slot)
    # AFI varies (ipv4/ipv6) and is set at instance level by INET
    safi: ClassVar[SAFI] = SAFI.mpls_vpn

    def __init__(
        self, packed: Buffer, afi: AFI, *, has_addpath: bool = False, has_labels: bool = False, has_rd: bool = False
    ) -> None:
        """Create an IPVPN NLRI from packed wire format bytes.

        Args:
            packed: Wire format bytes [addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]
            afi: Address Family Identifier
            has_addpath: If True, packed includes 4-byte path identifier at start
            has_labels: If True, packed includes label bytes after the mask
            has_rd: If True, packed includes 8-byte RD after labels

        SAFI is always mpls_vpn (class-level). Use factory methods for creation.
        """
        Label.__init__(self, packed, afi, has_addpath=has_addpath, has_labels=has_labels)
        self._has_rd = has_rd

    @property
    def _rd_end_offset(self) -> int:
        """Offset where RD ends (i.e., where prefix bytes start).

        Uses _has_rd flag to determine if RD is present.
        Returns offset relative to start of _packed.
        For NORD case (no RD), returns label_end offset (same as Label.cidr start).
        """
        label_end = self._label_end_offset
        if not self._has_rd:
            return label_end
        return label_end + RD_SIZE

    @property
    def rd(self) -> RouteDistinguisher:
        """Get Route Distinguisher from wire bytes.

        Extracts RD from _packed[label_end:label_end+8] if _has_rd is True.
        """
        if not self._has_rd:
            return RouteDistinguisher.NORD
        label_end = self._label_end_offset
        return RouteDistinguisher(self._packed[label_end : label_end + RD_SIZE])

    @property
    def cidr(self) -> CIDR:
        """Extract CIDR from after RD in wire format.

        Wire format: [addpath?][mask][labels][rd][prefix]
        CIDR needs [cidr_mask][prefix] where cidr_mask = mask - label_bits - rd_bits
        """
        base = self._mask_offset
        combined_mask = self._packed[base]
        rd_end = self._rd_end_offset

        # Calculate prefix-only mask (subtract label bits and RD bits)
        label_end = self._label_end_offset
        label_bytes_count = label_end - (base + 1)
        label_bits = label_bytes_count * 8
        rd_bits = RD_SIZE_BITS if self._has_rd else 0
        prefix_mask = combined_mask - label_bits - rd_bits

        # Extract prefix bytes from after RD
        prefix_bytes = self._packed[rd_end:]

        # Build CIDR from mask + prefix
        cidr_packed = bytes([prefix_mask]) + prefix_bytes
        if self.afi == AFI.ipv4:
            return CIDR.from_ipv4(cidr_packed)
        return CIDR.from_ipv6(cidr_packed)

    @classmethod
    def from_cidr(
        cls,
        cidr: CIDR,
        afi: AFI,
        safi: SAFI = SAFI.mpls_vpn,  # Default to class SAFI; parameter kept for API compat
        path_info: PathInfo = PathInfo.DISABLED,
        labels: Labels | None = None,
        rd: RouteDistinguisher | None = None,
    ) -> 'IPVPN':
        """Factory method to create IPVPN from a CIDR object.

        Args:
            cidr: CIDR prefix
            afi: Address Family Identifier
            safi: Ignored - IPVPN always uses mpls_vpn (kept for API compatibility)
            path_info: AddPath path identifier
            labels: MPLS label stack (optional, defaults to NOLABEL)
            rd: Route Distinguisher (optional, defaults to NORD)

        Returns:
            New IPVPN instance with SAFI=mpls_vpn
        """
        # Build wire format: [addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]
        labels_packed = labels.pack_labels() if labels is not None else b''
        has_labels = len(labels_packed) > 0
        rd_packed = rd.pack_rd() if rd is not None else b''
        has_rd = len(rd_packed) > 0
        prefix_bytes = cidr.pack_ip()

        # Combined mask includes labels + RD + prefix
        combined_mask = len(labels_packed) * 8 + len(rd_packed) * 8 + cidr.mask

        # Build packed data: [mask][labels][rd][prefix]
        nlri_bytes = bytes([combined_mask]) + labels_packed + rd_packed + prefix_bytes

        has_addpath = path_info is not PathInfo.DISABLED
        if has_addpath:
            packed = bytes(path_info.pack_path()) + nlri_bytes
        else:
            packed = nlri_bytes

        instance = object.__new__(cls)
        # Note: safi parameter is ignored - IPVPN.safi is a class-level property
        NLRI.__init__(instance, afi, cls.safi)
        instance._packed = packed
        instance._has_addpath = has_addpath
        instance._has_labels = has_labels
        instance._has_rd = has_rd
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
            path_info=settings.path_info,
            labels=settings.labels,
            rd=settings.rd,
        )
        # Note: settings.nexthop is now passed to Route, not stored in NLRI
        return instance

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    @classmethod
    def make_vpn_route(
        cls,
        afi: AFI,
        safi: SAFI,
        packed: Buffer,
        mask: int,
        labels: Labels,
        rd: RouteDistinguisher,
        path_info: PathInfo = PathInfo.DISABLED,
    ) -> 'IPVPN':
        """Factory method to create an IPVPN route.

        Note: nexthop is stored in Route, not NLRI. Pass nexthop to Route constructor.
        """
        cidr = CIDR.make_cidr(packed, mask)
        instance = cls.from_cidr(cidr, afi, safi, path_info, labels=labels, rd=rd)
        return instance

    def extensive(self) -> str:
        return '{}{}'.format(Label.extensive(self), str(self.rd))

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __len__(self) -> int:
        # _packed includes everything: [addpath?][mask][labels][rd][prefix]
        return len(self._packed)

    def __eq__(self, other: Any) -> bool:
        # Compare complete wire format (includes RD)
        return Label.__eq__(self, other)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        # _packed includes everything (labels + RD); use _has_addpath as discriminator
        if self._has_addpath:
            return hash(self._packed)
        return hash(b'disabled' + self._packed)

    def __copy__(self) -> 'IPVPN':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi - safi is class-level)
        new.afi = self.afi
        # NLRI slots
        self._copy_nlri_slots(new)
        # INET slots
        new._has_addpath = self._has_addpath
        # Label slots
        new._has_labels = self._has_labels
        # IPVPN slots
        new._has_rd = self._has_rd
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
        new._has_labels = self._has_labels  # bool - immutable
        # IPVPN slots
        new._has_rd = self._has_rd  # bool - immutable
        return new

    @classmethod
    def has_rd(cls) -> bool:
        return True

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        """Pack NLRI for wire transmission (zero-copy when possible).

        _packed format: [addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]
        Wire format: [addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]

        With RD now stored in _packed, we can return it directly.
        """
        send_addpath = negotiated.addpath.send(self.afi, self.safi)

        if send_addpath:
            if self._has_addpath:
                return self._packed  # Zero-copy: return directly
            # Need to prepend NOPATH (4 zero bytes)
            return bytes(PathInfo.NOPATH.pack_path()) + self._packed
        else:
            if self._has_addpath:
                # Strip AddPath bytes (first 4 bytes)
                return self._packed[PATH_INFO_SIZE:]
            return self._packed  # Zero-copy: return directly

    def index(self) -> bytes:
        """Generate unique index for RIB lookup.

        Index uses RD + prefix (without labels) for uniqueness.
        """
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        # Index uses RD + prefix (without labels) for uniqueness
        rd_bits = RD_SIZE_BITS if self._has_rd else 0
        mask = bytes([rd_bits + self.cidr.mask])
        # Extract RD bytes from _packed
        label_end = self._label_end_offset
        rd_packed = self._packed[label_end : label_end + RD_SIZE] if self._has_rd else b''
        return Family.index(self) + addpath + mask + rd_packed + self.cidr.pack_ip()

    def _internal(self, announced: bool = True) -> list[str]:
        r = Label._internal(self, announced)
        if announced and self._has_rd:
            r.append(self.rd.json())
        return r

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        """Unpack IPVPN NLRI from wire format.

        Uses SAFI to determine RD presence (exact, not heuristic).
        Wire format: [addpath?][mask][labels][rd][prefix]
        Storage: _packed = [addpath?][mask][labels][rd][prefix] (complete wire format)
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

        original_mask = data[0]
        data = data[1:]

        # Get RD size from Family.size (exact, not heuristic)
        _, rd_size = Family.size.get((afi, safi), (0, 0))
        rd_bits = rd_size * 8

        # Track consumed labels for storage
        labels_bytes_list: list[bytes] = []
        mask = original_mask

        # Parse labels using mask (original algorithm from INET.unpack_nlri)
        if safi.has_label():
            while mask - rd_bits >= LABEL_SIZE_BITS:
                label_chunk = bytes(data[:3])
                label = int(unpack('!L', bytes([0]) + label_chunk)[0])
                labels_bytes_list.append(label_chunk)
                data = data[3:]
                mask -= LABEL_SIZE_BITS
                if label == LABEL_WITHDRAW_VALUE and action == Action.WITHDRAW:
                    break
                if label == LABEL_NEXTHOP_VALUE:
                    break
                if label & LABEL_BOTTOM_OF_STACK_BIT:
                    break

        labels_packed = b''.join(labels_bytes_list)

        # Parse RD if present (exact from SAFI, not heuristic)
        rd_packed = b''
        has_rd = False
        if rd_size:
            mask -= rd_bits
            rd_packed = bytes(data[:rd_size])
            has_rd = True
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

        # Build _packed format: [addpath:4?][mask:1][labels:3n][rd:8?][prefix:var]
        # Store complete wire format including RD (original_mask already includes RD bits)
        nlri_packed = bytes([original_mask]) + labels_packed + rd_packed + bytes(network)

        has_addpath = path_info is not PathInfo.DISABLED
        if has_addpath:
            packed = bytes(path_info.pack_path()) + nlri_packed
        else:
            packed = nlri_packed

        # Create NLRI
        instance = object.__new__(cls)
        NLRI.__init__(instance, afi, safi, action)
        instance._packed = packed
        instance._has_addpath = has_addpath
        instance._has_labels = len(labels_packed) > 0
        instance._has_rd = has_rd

        return instance, data
