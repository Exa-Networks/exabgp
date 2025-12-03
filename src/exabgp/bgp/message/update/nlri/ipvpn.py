"""ipvpn.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
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
    def __init__(
        self,
        packed: bytes,
        afi: AFI,
        safi: SAFI,
        action: Action = Action.UNSET,
        path_info: PathInfo = PathInfo.DISABLED,
    ) -> None:
        """Create an IPVPN NLRI from packed CIDR bytes.

        Args:
            packed: CIDR wire format bytes [mask_byte][truncated_ip...]
            afi: Address Family Identifier
            safi: Subsequent Address Family Identifier
            action: Route action (ANNOUNCE/WITHDRAW)
            path_info: AddPath path identifier
        """
        Label.__init__(self, packed, afi, safi, action, path_info)
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
        return cls(cidr.pack_nlri(), afi, safi, action, path_info)

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
        cidr = CIDR(packed, mask)
        instance = cls(cidr.pack_nlri(), afi, safi, action, path_info)
        instance.labels = labels
        instance.rd = rd
        instance.nexthop = IP.create(nexthop) if nexthop else IP.NoNextHop
        return instance

    # Backward compatibility alias
    new = make_vpn_route

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
