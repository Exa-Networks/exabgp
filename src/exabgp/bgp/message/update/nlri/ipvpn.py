"""ipvpn.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo, RouteDistinguisher
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP, NoNextHop

# ====================================================== IPVPN
# RFC 4364


@NLRI.register(AFI.ipv4, SAFI.mpls_vpn)
@NLRI.register(AFI.ipv6, SAFI.mpls_vpn)
class IPVPN(Label):
    def __init__(self, afi: AFI, safi: SAFI, action: Action = Action.UNSET) -> None:
        Label.__init__(self, afi, safi, action)
        self.rd = RouteDistinguisher.NORD

    def feedback(self, action: Action) -> str:
        if self.nexthop is None and action == Action.ANNOUNCE:
            return 'ip-vpn nlri next-hop missing'
        return ''

    @classmethod
    def new(
        cls,
        afi: AFI,
        safi: SAFI,
        packed: bytes,
        mask: int,
        labels: Labels,
        rd: RouteDistinguisher,
        nexthop: str | None = None,
        action: Action = Action.UNSET,
    ) -> IPVPN:
        instance = cls(afi, safi, action)
        instance.cidr = CIDR(packed, mask)
        instance.labels = labels
        instance.rd = rd
        instance.nexthop = IP.create(nexthop) if nexthop else NoNextHop
        instance.action = action
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
        addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack_path()  # type: ignore[union-attr]
        return hash(addpath + self._pack_nlri_simple())

    @classmethod
    def has_rd(cls) -> bool:
        return True

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        mask = bytes([len(self.labels) * 8 + len(self.rd) * 8 + self.cidr.mask])  # type: ignore[union-attr,arg-type]
        return mask + self.labels.pack_labels() + self.rd.pack_rd() + self.cidr.pack_ip()  # type: ignore[no-any-return,union-attr]

    def pack_nlri(self, negotiated: Negotiated) -> bytes:  # type: ignore[assignment]
        addpath = self.path_info.pack_path() if negotiated.addpath.send(self.afi, self.safi) else b''  # type: ignore[union-attr]
        return addpath + self._pack_nlri_simple()

    def index(self) -> bytes:  # type: ignore[assignment]
        addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack_path()  # type: ignore[union-attr]
        mask = bytes([len(self.rd) * 8 + self.cidr.mask])  # type: ignore[union-attr,arg-type]
        return Family.index(self) + addpath + mask + self.rd.pack_rd() + self.cidr.pack_ip()  # type: ignore[no-any-return,union-attr]

    def _internal(self, announced: bool = True) -> List[str]:
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
