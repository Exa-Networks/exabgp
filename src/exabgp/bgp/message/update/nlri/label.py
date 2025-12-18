"""label.py (MPLS Labeled Routes)

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)

RFC References:
===============

RFC 3107 - Carrying Label Information in BGP-4
https://www.rfc-editor.org/rfc/rfc3107.html

    Defines how MPLS labels are carried in BGP UPDATE messages.
    Labels are prepended to the NLRI prefix within MP_REACH_NLRI.

    SAFI value: 4 (SAFI_NLRI_MPLS / nlri_mpls)

    Wire format for labeled NLRI:

        +---------------------------+
        |   Length (1 octet)        |  <- Total bits: label_bits + prefix_bits
        +---------------------------+
        |   Label 1 (3 octets)      |  <- 20-bit label + 3 exp + 1 BoS
        +---------------------------+
        |   Label 2 (3 octets)      |  <- Optional, if label stack
        +---------------------------+
        |   ...                     |
        +---------------------------+
        |   Label N (3 octets)      |  <- Last label has BoS=1
        +---------------------------+
        |   Prefix (variable)       |  <- IP prefix bytes
        +---------------------------+

    Label encoding (3 bytes / 24 bits):
        - Bits 0-19:  Label value (20 bits)
        - Bits 20-22: Experimental/TC (3 bits)
        - Bit 23:     Bottom of Stack (BoS) - 1 if last label

    Special label values:
        - 0x800000: Withdrawal label (label=524288 with BoS)
        - 0x000000: Next-hop label

    Length field calculation:
        Length = (num_labels * 24) + prefix_mask_bits

    Example: /24 prefix with one label
        Length = 24 + 24 = 48 bits
        Wire: [0x30][label 3 bytes][prefix 3 bytes] = 7 bytes total

RFC 8277 - Using BGP to Bind MPLS Labels to Address Prefixes
https://www.rfc-editor.org/rfc/rfc8277.html

    Updates RFC 3107 with clarifications on label binding.
    Deprecates the use of SAFI 4 for some cases in favor of
    SAFI 1 with label binding via attributes.

Wire Format (_packed) - Packed-Bytes-First Pattern:
===================================================
    This class stores the complete wire format in _packed:

    _packed stores: [addpath:4?][mask:1][labels:3n][prefix:var]
    - mask = combined mask (label_bits + prefix_bits)
    - labels = raw MPLS label bytes (3 bytes per label)
    - prefix = truncated IP prefix bytes

    pack_nlri() returns _packed directly (zero-copy).

    Properties extract data lazily:
    - labels: scans for BOS bit to find label end
    - cidr: extracts from after labels

Class Hierarchy:
===============
    INET (inet.py) - base for unicast/multicast
      └── Label (this class) - adds MPLS label stack
            └── IPVPN (ipvpn.py) - adds Route Distinguisher
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import INETSettings

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET, PATH_INFO_SIZE
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.util.types import Buffer

# MPLS label size in bytes
LABEL_SIZE_BYTES = 3
# Bottom of Stack bit mask (lowest bit of the 24-bit label)
LABEL_BOS_MASK = 0x01

# ====================================================== MPLS
# RFC 3107


@NLRI.register(AFI.ipv4, SAFI.nlri_mpls)
@NLRI.register(AFI.ipv6, SAFI.nlri_mpls)
class Label(INET):
    """Label NLRI using packed-bytes-first pattern.

    Wire format stored in _packed: [addpath:4?][mask:1][labels:3n][prefix:var]
    - mask = combined mask (label_bits + prefix_bits)
    - labels = raw MPLS label bytes, last has BOS bit set
    - prefix = truncated IP prefix bytes

    Properties extract data lazily:
    - labels: scans for BOS bit to find label end (if _has_labels)
    - cidr: extracts from after labels using _label_end_offset

    Uses class-level SAFI (always nlri_mpls) - no instance storage needed.
    """

    __slots__ = ('_has_labels',)  # Track whether labels are present

    # Fixed SAFI for Label NLRI - AFI varies (ipv4/ipv6) and is set at instance level by INET
    @property
    def safi(self) -> SAFI:
        return SAFI.nlri_mpls

    def __init__(self, packed: Buffer, afi: AFI, *, has_addpath: bool = False, has_labels: bool = False) -> None:
        """Create a Label NLRI from packed wire format bytes.

        Args:
            packed: Wire format bytes [addpath:4?][mask:1][labels:3n][prefix:var]
            afi: Address Family Identifier
            has_addpath: If True, packed includes 4-byte path identifier at start
            has_labels: If True, packed includes label bytes after the mask

        SAFI is always nlri_mpls (class-level). Use factory methods for creation.
        """
        INET.__init__(self, packed, afi, self.safi, has_addpath=has_addpath)
        self._has_labels = has_labels
        # Note: inherited rd=None from INET is fine (IPVPN overrides)

    @property
    def _label_end_offset(self) -> int:
        """Offset where labels end (i.e., where prefix bytes start).

        Uses _has_labels flag to determine if labels are present.
        If present, scans from mask+1 for BOS bit to find end of label stack.
        Returns offset relative to start of _packed.
        For NOLABEL case (no labels), returns mask offset + 1 (just after mask).
        """
        base = self._mask_offset  # 0 or 4 depending on AddPath

        # If no labels flag is set, return immediately after mask
        if not self._has_labels:
            return base + 1

        # Scan labels starting after mask byte
        label_start = base + 1
        offset = label_start
        data = self._packed[offset:]

        while len(data) >= LABEL_SIZE_BYTES:
            # Read 24-bit label value
            raw = unpack('!L', bytes([0]) + bytes(data[:LABEL_SIZE_BYTES]))[0]
            offset += LABEL_SIZE_BYTES
            data = data[LABEL_SIZE_BYTES:]

            # Check BOS bit (lowest bit)
            if raw & LABEL_BOS_MASK:
                return offset

        # No BOS found - return current offset (all data was labels)
        return offset

    @property
    def labels(self) -> Labels:
        """Get Labels from wire bytes by scanning for BOS bit."""
        # Fast path: no labels
        if not self._has_labels:
            return Labels.NOLABEL

        base = self._mask_offset
        label_start = base + 1
        label_end = self._label_end_offset
        label_bytes = self._packed[label_start:label_end]

        if not label_bytes:
            return Labels.NOLABEL
        return Labels(label_bytes)

    @property
    def cidr(self) -> CIDR:
        """Extract CIDR from after labels in wire format.

        Wire format: [addpath?][mask][labels][prefix]
        CIDR needs [cidr_mask][prefix] where cidr_mask = mask - label_bits
        """
        base = self._mask_offset
        combined_mask = self._packed[base]
        label_end = self._label_end_offset

        # Calculate prefix-only mask (subtract label bits)
        label_bytes_count = label_end - (base + 1)
        label_bits = label_bytes_count * 8
        prefix_mask = combined_mask - label_bits

        # Extract prefix bytes from after labels
        prefix_bytes = self._packed[label_end:]

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
        safi: SAFI = SAFI.nlri_mpls,  # Default to class SAFI; parameter kept for API compat
        path_info: PathInfo = PathInfo.DISABLED,
        labels: Labels | None = None,
    ) -> 'Label':
        """Factory method to create Label from a CIDR object.

        Args:
            cidr: CIDR prefix
            afi: Address Family Identifier
            safi: Ignored - Label always uses nlri_mpls (kept for API compatibility)
            path_info: AddPath path identifier
            labels: MPLS label stack (optional, defaults to NOLABEL)

        Returns:
            New Label instance with SAFI=nlri_mpls
        """
        # Build wire format: [addpath:4?][mask:1][labels:3n][prefix:var]
        labels_packed = labels.pack_labels() if labels is not None else b''
        has_labels = len(labels_packed) > 0
        combined_mask = len(labels_packed) * 8 + cidr.mask
        prefix_bytes = cidr.pack_ip()

        # Build packed data: [mask][labels][prefix]
        nlri_bytes = bytes([combined_mask]) + labels_packed + prefix_bytes

        has_addpath = path_info is not PathInfo.DISABLED
        if has_addpath:
            packed = bytes(path_info.pack_path()) + nlri_bytes
        else:
            packed = nlri_bytes

        instance = object.__new__(cls)
        # Note: safi parameter is ignored - Label always uses nlri_mpls
        NLRI.__init__(instance, afi, SAFI.nlri_mpls)
        instance._packed = packed
        instance._has_addpath = has_addpath
        instance._has_labels = has_labels
        instance._rd = None
        return instance

    @classmethod
    def from_settings(cls, settings: 'INETSettings') -> 'Label':
        """Create Label NLRI from validated settings.

        This factory method validates settings and creates an immutable Label
        instance with labels. Use this for deferred construction where all values
        are collected during parsing, then validated and used to create the NLRI.

        Args:
            settings: INETSettings with all required fields set (including labels)

        Returns:
            Immutable Label NLRI instance

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
        )
        # Note: settings.nexthop is now passed to Route, not stored in NLRI
        return instance

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def extensive(self) -> str:
        return self.prefix()

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __len__(self) -> int:
        # _packed includes everything: [addpath?][mask][labels][prefix]
        return len(self._packed)

    def __eq__(self, other: Any) -> bool:
        # Compare complete wire format (includes labels)
        return INET.__eq__(self, other)

    def __hash__(self) -> int:
        # _packed includes everything; use _has_addpath as discriminator
        if self._has_addpath:
            return hash(self._packed)
        return hash(b'disabled' + self._packed)

    def __copy__(self) -> 'Label':
        new = self.__class__.__new__(self.__class__)
        # NLRI slots (includes Family slots: _afi, _safi)
        self._copy_nlri_slots(new)
        # INET slots
        new._has_addpath = self._has_addpath
        new._rd = self._rd
        # Label slots
        new._has_labels = self._has_labels
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'Label':
        from copy import deepcopy

        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # NLRI slots (includes Family slots: _afi, _safi)
        self._deepcopy_nlri_slots(new, memo)
        # INET slots
        new._has_addpath = self._has_addpath  # bool - immutable
        new._rd = deepcopy(self._rd, memo) if self._rd else None
        # Label slots
        new._has_labels = self._has_labels  # bool - immutable
        return new

    def prefix(self) -> str:
        return '{}{}'.format(INET.prefix(self), self.labels)

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        """Pack NLRI for wire transmission (zero-copy when possible).

        _packed format: [addpath:4?][mask:1][labels:3n][prefix:var]
        Wire format: [addpath:4?][mask:1][labels:3n][prefix:var]
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

        Index uses prefix only (without labels) for uniqueness.
        """
        addpath: Buffer
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        mask = bytes([self.cidr.mask])
        return Family.index(self) + bytes(addpath) + mask + self.cidr.pack_ip()

    def _internal(self, announced: bool = True) -> list[str]:
        r = INET._internal(self, announced)
        labels = self.labels
        if announced and labels is not Labels.NOLABEL:
            r.append(labels.json())
        return r

    # @classmethod
    # def _labels (cls, data, action):
    # 	mask = data[0]
    # 	data = data[1:]
    # 	labels = []
    # 	while data and mask >= 8:
    # 		label = int(unpack('!L',character(0) + data[:3])[0])
    # 		data = data[3:]
    # 		mask -= 24  	# 3 bytes
    # 		# The last 4 bits are the bottom of Stack
    # 		# The last bit is set for the last label
    # 		labels.append(label >> 4)
    # 		# This is a route withdrawal
    # 		if label == 0x800000 and action == Action.WITHDRAW:
    # 			break
    # 		# This is a next-hop
    # 		if label == 0x000000:
    # 			break
    # 		if label & 1:
    # 			break
    # 	return mask, Labels(labels), data
    #
    # @classmethod
    # def unpack_label (cls, afi, safi, data, action, addpath):
    # 	pathinfo, data = cls._pathinfo(data,addpath)
    # 	mask, labels, data = cls._labels(data,action)
    # 	nlri, data = cls.unpack_cidr(afi,safi,mask,data,action)
    # 	nlri.path_info = pathinfo
    # 	nlri.labels = labels
    # 	return nlri,data
    #
    # @classmethod
    # def unpack_nlri (cls, afi, safi, data, addpath):
    # 	return cls.unpack_label(afi,safi,data,addpath)
