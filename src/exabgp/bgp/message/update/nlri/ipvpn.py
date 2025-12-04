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

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo, RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP

# ====================================================== IPVPN
# RFC 4364


@NLRI.register(AFI.ipv4, SAFI.mpls_vpn)
@NLRI.register(AFI.ipv6, SAFI.mpls_vpn)
class IPVPN(Label):
    def __init__(self, packed: bytes) -> None:
        """Create an IPVPN NLRI from packed CIDR bytes.

        Args:
            packed: CIDR wire format bytes [mask_byte][truncated_ip...]

        AFI is inferred from mask (>32 implies IPv6).
        SAFI defaults to mpls_vpn. Use factory methods for other families.
        """
        Label.__init__(self, packed)
        self._safi = SAFI.mpls_vpn  # Override default
        self.rd = RouteDistinguisher.NORD

    @classmethod
    def from_cidr(
        cls,
        cidr: CIDR,
        afi: AFI,
        safi: SAFI,
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
    ) -> 'IPVPN':
        """Factory method to create IPVPN from a CIDR object.

        Args:
            cidr: CIDR prefix
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier

        Returns:
            New IPVPN instance
        """
        instance = object.__new__(cls)
        NLRI.__init__(instance, afi, safi, action)
        instance._packed = cidr.pack_nlri()
        instance.path_info = path_info
        instance.nexthop = IP.NoNextHop
        instance.labels = Labels.NOLABEL
        instance.rd = RouteDistinguisher.NORD
        return instance

    def feedback(self, action: Action) -> str:  # type: ignore[override]
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
        """Factory method to create an IPVPN route.

        Args:
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            packed: Packed IP address bytes (full length)
            mask: Prefix length
            labels: MPLS labels
            rd: Route Distinguisher
            nexthop: Next-hop IP address (as string)
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier

        Returns:
            New IPVPN instance
        """
        cidr = CIDR.make_cidr(packed, mask)
        instance = cls.from_cidr(cidr, afi, safi, action, path_info)
        instance.labels = labels
        instance.rd = rd
        instance.nexthop = IP.create(nexthop) if nexthop else IP.NoNextHop
        return instance

    def extensive(self) -> str:
        return '{}{}'.format(Label.extensive(self), str(self.rd))

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __len__(self) -> int:
        return Label.__len__(self) + len(self.rd)  # type: ignore[arg-type]

    def __eq__(self, other: Any) -> bool:
        return Label.__eq__(self, other) and self.rd == other.rd and Label.__eq__(self, other)

    def __ne__(self, other: Any) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        if self.path_info is PathInfo.NOPATH:
            addpath = b'no-pi'
        elif self.path_info is PathInfo.DISABLED:
            addpath = b'disabled'
        else:
            addpath = self.path_info.pack_path()
        return hash(addpath + self._pack_nlri_simple())

    @classmethod
    def has_rd(cls) -> bool:
        return True

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        assert self.labels is not None  # Always set in Label.__init__
        assert self.rd is not None  # Always set in IPVPN.__init__
        mask = bytes([len(self.labels) * 8 + len(self.rd) * 8 + self.cidr.mask])
        return mask + self.labels.pack_labels() + self.rd.pack_rd() + self.cidr.pack_ip()

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
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
        assert self.rd is not None  # Always set in IPVPN.__init__
        mask = bytes([len(self.rd) * 8 + self.cidr.mask])
        return Family.index(self) + addpath + mask + self.rd.pack_rd() + self.cidr.pack_ip()

    def _internal(self, announced: bool = True) -> list[str]:
        r = Label._internal(self, announced)
        if announced and self.rd:
            r.append(self.rd.json())
        return r

    # @classmethod
    # def _rd (cls, data, mask):
    # 	mask -= 8*8  # the 8 bytes of the route distinguisher
    # 	rd = data[:8]
    # 	data = data[8:]
    #
    # 	if mask < 0:
    # 		raise Notify(3,10,'invalid length in NLRI prefix')
    #
    # 	if not data and mask:
    # 		raise Notify(3,10,'not enough data for the mask provided to decode the NLRI')
    #
    # 	return RouteDistinguisher(rd), mask, data
    #
    # @classmethod
    # def unpack_mpls (cls, afi, safi, data, action, addpath):
    # 	pathinfo, data = cls._pathinfo(data,addpath)
    # 	mask, labels, data = cls._labels(data,action)
    # 	rd, mask, data = cls._rd(data,mask)
    # 	nlri, data = cls.unpack_cidr(afi,safi,mask,data,action)
    # 	nlri.path_info = pathinfo
    # 	nlri.labels = labels
    # 	nlri.rd = rd
    # 	return nlri,data
    #
    # @classmethod
    # def unpack_nlri (cls, afi, safi, data, addpath):
    # 	return cls.unpack_mpls(afi,safi,data,addpath)
