# encoding: utf-8
"""
labelled.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.util import character
from exabgp.util import ordinal
from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.update.nlri.qualifier import Labels


# ====================================================== MPLS
# RFC 3107


@NLRI.register(AFI.ipv4, SAFI.nlri_mpls)
@NLRI.register(AFI.ipv6, SAFI.nlri_mpls)
class Label(INET):
    __slots__ = ['labels']

    def __init__(self, afi, safi, action):
        INET.__init__(self, afi, safi, action)
        self.labels = Labels.NOLABEL

    def feedback(self, action):
        if self.nexthop is None and action == OUT.ANNOUNCE:
            return 'labelled nlri next-hop missing'
        return ''

    def extensive(self):
        return "%s%s" % (self.prefix(), '' if self.nexthop is NoNextHop else ' next-hop %s' % self.nexthop)

    def __str__(self):
        return self.extensive()

    def __repr__(self):
        return self.extensive()

    def __len__(self):
        return INET.__len__(self) + len(self.labels)

    def __eq__(self, other):
        return self.labels == other.labels and INET.__eq__(self, other)

    def __hash__(self):
        return hash(self.pack())

    def prefix(self):
        return "%s%s" % (INET.prefix(self), self.labels)

    def pack(self, negotiated=None):
        addpath = self.path_info.pack() if negotiated and negotiated.addpath.send(self.afi, self.safi) else b''
        mask = character(len(self.labels) * 8 + self.cidr.mask)
        return addpath + mask + self.labels.pack() + self.cidr.pack_ip()

    def index(self, negotiated=None):
        addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack()
        mask = character(self.cidr.mask)
        return NLRI._index(self) + addpath + mask + self.cidr.pack_ip()

    def _internal(self, announced=True):
        r = INET._internal(self, announced)
        if announced and self.labels:
            r.append(self.labels.json())
        return r

    # @classmethod
    # def _labels (cls, data, action):
    # 	mask = ordinal(data[0])
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
    # 		if label == 0x800000 and action == IN.WITHDRAWN:
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
