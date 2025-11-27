"""labelled.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, List

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import NoNextHop

# ====================================================== MPLS
# RFC 3107


@NLRI.register(AFI.ipv4, SAFI.nlri_mpls)
@NLRI.register(AFI.ipv6, SAFI.nlri_mpls)
class Label(INET):
    def __init__(self, afi: AFI, safi: SAFI, action: Action) -> None:
        INET.__init__(self, afi, safi, action)
        self.labels = Labels.NOLABEL

    def feedback(self, action: Action) -> str:  # type: ignore[override]
        if self.nexthop is None and action == Action.ANNOUNCE:
            return 'labelled nlri next-hop missing'
        return ''

    def extensive(self) -> str:
        return '{}{}'.format(self.prefix(), '' if self.nexthop is NoNextHop else ' next-hop {}'.format(self.nexthop))

    def __str__(self) -> str:
        return self.extensive()

    def __repr__(self) -> str:
        return self.extensive()

    def __len__(self) -> int:
        return INET.__len__(self) + len(self.labels)  # type: ignore[arg-type]

    def __eq__(self, other: Any) -> bool:
        return self.labels == other.labels and INET.__eq__(self, other)

    def __hash__(self) -> int:
        addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack_path()
        return hash(addpath + self._pack_nlri_simple())

    def prefix(self) -> str:
        return '{}{}'.format(INET.prefix(self), self.labels)

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath)."""
        assert self.labels is not None  # Always set in Label.__init__
        mask = bytes([len(self.labels) * 8 + self.cidr.mask])
        return mask + self.labels.pack_labels() + self.cidr.pack_ip()

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        addpath = self.path_info.pack_path() if negotiated.addpath.send(self.afi, self.safi) else b''
        return addpath + self._pack_nlri_simple()

    def index(self) -> bytes:
        addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack_path()
        mask = bytes([self.cidr.mask])
        return Family.index(self) + addpath + mask + self.cidr.pack_ip()

    def _internal(self, announced: bool = True) -> List[str]:
        r = INET._internal(self, announced)
        if announced and self.labels:
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
