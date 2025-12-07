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

Wire Format (_packed):
=====================
    This class stores ONLY the CIDR payload in _packed (not the full labeled NLRI).

    _packed stores: [mask_byte][truncated_ip_bytes...]  (same as INET)
    _labels_packed stores: raw label bytes (empty = NOLABEL)

    On pack_nlri(), these are combined:
        output = [length][labels][prefix] where length = labels*24 + mask

    Note: path_info (ADD-PATH) is stored in self.path_info, NOT in _packed.

Class Hierarchy:
===============
    INET (inet.py) - base for unicast/multicast
      └── Label (this class) - adds MPLS label stack
            └── IPVPN (ipvpn.py) - adds Route Distinguisher
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import INETSettings

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP
from exabgp.util.types import Buffer

# ====================================================== MPLS
# RFC 3107


@NLRI.register(AFI.ipv4, SAFI.nlri_mpls)
@NLRI.register(AFI.ipv6, SAFI.nlri_mpls)
class Label(INET):
    """Label NLRI with separate storage for CIDR and labels.

    Wire format: [mask][labels][prefix]
    Storage: _packed (CIDR), _labels_packed (label bytes)
    pack_nlri() = concatenation with computed mask

    Uses class-level SAFI (always nlri_mpls) - no instance storage needed.
    """

    __slots__ = ('_labels_packed',)

    # Fixed SAFI for Label NLRI (class attribute shadows slot)
    # AFI varies (ipv4/ipv6) and is set at instance level by INET
    safi: ClassVar[SAFI] = SAFI.nlri_mpls

    def __init__(self, packed: bytes) -> None:
        """Create a Label NLRI from packed CIDR bytes.

        Args:
            packed: CIDR wire format bytes [mask_byte][truncated_ip...]

        AFI is inferred from mask (>32 implies IPv6).
        SAFI is always nlri_mpls (class-level). Use factory methods for creation.

        NOTE: This __init__ is broken (INET requires afi parameter).
        Use from_cidr() factory method instead.
        """
        INET.__init__(self, packed)
        # Note: safi is now a property, setter is a no-op
        self._labels_packed: bytes = b''  # Label bytes (empty = NOLABEL)

    @property
    def labels(self) -> Labels:
        """Get Labels from stored bytes."""
        if not self._labels_packed:
            return Labels.NOLABEL
        return Labels(self._labels_packed)

    @labels.setter
    def labels(self, value: Labels) -> None:
        """Set Labels by storing packed bytes."""
        self._labels_packed = value.pack_labels()

    @classmethod
    def from_cidr(
        cls,
        cidr: CIDR,
        afi: AFI,
        safi: SAFI = SAFI.nlri_mpls,  # Default to class SAFI; parameter kept for API compat
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
    ) -> 'Label':
        """Factory method to create Label from a CIDR object.

        Args:
            cidr: CIDR prefix
            afi: Address Family Identifier
            safi: Ignored - Label always uses nlri_mpls (kept for API compatibility)
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier

        Returns:
            New Label instance with SAFI=nlri_mpls
        """
        instance = object.__new__(cls)
        # Note: safi parameter is ignored - Label.safi is a class-level constant
        NLRI.__init__(instance, afi, cls.safi, action)
        instance._packed = cidr.pack_nlri()
        instance.path_info = path_info
        instance.nexthop = IP.NoNextHop
        instance._labels_packed = b''  # NOLABEL
        instance.rd = None
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
            action=settings.action,
            path_info=settings.path_info,
        )
        instance.nexthop = settings.nexthop

        # Set labels if provided
        if settings.labels is not None:
            instance.labels = settings.labels

        return instance

    def feedback(self, action: Action) -> str:
        if self.nexthop is IP.NoNextHop and action == Action.ANNOUNCE:
            return 'labelled nlri next-hop missing'
        return ''

    def extensive(self) -> str:
        return '{}{}'.format(self.prefix(), '' if self.nexthop is IP.NoNextHop else ' next-hop {}'.format(self.nexthop))

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __len__(self) -> int:
        return INET.__len__(self) + len(self._labels_packed)

    def __eq__(self, other: Any) -> bool:
        return self._labels_packed == other._labels_packed and INET.__eq__(self, other)

    def __hash__(self) -> int:
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        return hash(addpath + self._pack_nlri_simple())

    def __copy__(self) -> 'Label':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi - safi is class-level)
        new.afi = self.afi
        # NLRI slots
        self._copy_nlri_slots(new)
        # INET slots
        new.path_info = self.path_info
        new.labels = self.labels
        new.rd = self.rd
        # Label slots
        new._labels_packed = self._labels_packed
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'Label':
        from copy import deepcopy

        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # Family slots (afi - safi is class-level)
        new.afi = self.afi
        # NLRI slots
        self._deepcopy_nlri_slots(new, memo)
        # INET slots
        new.path_info = self.path_info
        new.labels = deepcopy(self.labels, memo) if self.labels else None
        new.rd = deepcopy(self.rd, memo) if self.rd else None
        # Label slots
        new._labels_packed = self._labels_packed  # bytes - immutable
        return new

    def prefix(self) -> str:
        return '{}{}'.format(INET.prefix(self), self.labels)

    def _pack_nlri_simple(self) -> Buffer:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        mask = bytes([len(self._labels_packed) * 8 + self.cidr.mask])
        return mask + self._labels_packed + self.cidr.pack_ip()

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        if negotiated.addpath.send(self.afi, self.safi):
            # ADD-PATH negotiated: MUST send 4-byte path ID
            if self.path_info is PathInfo.DISABLED:
                addpath = PathInfo.NOPATH.pack_path()
            else:
                addpath = self.path_info.pack_path()
        else:
            addpath = b''
        return addpath + self._pack_nlri_simple()

    def index(self) -> Buffer:
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        mask = bytes([self.cidr.mask])
        return Family.index(self) + addpath + mask + self.cidr.pack_ip()

    def _internal(self, announced: bool = True) -> list[str]:
        r = INET._internal(self, announced)
        if announced and self._labels_packed:
            r.append(self.labels.json())
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
