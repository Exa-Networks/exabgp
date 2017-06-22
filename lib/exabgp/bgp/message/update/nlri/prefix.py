# encoding: utf-8
"""
path.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoIP
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo


class Prefix (CIDR,NLRI):
	__slots__ = ['path_info','nexthop','action']

	def __init__ (self, afi, safi, packed, mask, nexthop, action,path=None):
		self.path_info = PathInfo.NOPATH if path is None else path
		self.nexthop = IP.unpack(nexthop) if nexthop else NoIP
		NLRI.__init__(self,afi,safi)
		CIDR.__init__(self,packed,mask)
		self.action = action

	def prefix (self):
		return "%s/%s%s" % (CIDR.getip(self),self.mask,str(self.path_info) if self.path_info is not PathInfo.NOPATH else '')

	def extensive (self):
		return "%s/%s%s next-hop %s" % (self.ip,self.mask,str(self.path_info) if self.path_info is not PathInfo.NOPATH else '',self.nexthop)

	def pack (self, addpath):
		if addpath or True:
			return self.path_info.pack() + CIDR.pack(self) if addpath else CIDR.pack(self)
		return CIDR.pack(self) if addpath else CIDR.pack(self)

	def json (self):
		return '"%s/%s": { %s }' % (CIDR.getip(self),self.mask,self.path_info.json())

	def index (self):
		return self.pack(True)

	def __len__ (self):
		return CIDR.__len__(self) + len(self.path_info)

	def __str__ (self):
		nexthop = ' next-hop %s' % self.nexthop if self.nexthop else ''
		return "%s%s" % (self.prefix(),nexthop)

	def __hash__ (self):
		return hash(self.pack())

	@classmethod
	def unpack (cls, afi, safi, data, addpath, nexthop, action):
		labels,rd,path_identifier,mask,size,prefix,left = NLRI._nlri(afi,safi,data,action,addpath)
		nlri = cls(afi,safi,prefix,mask,nexthop,action)
		if path_identifier:
			nlri.path_info = PathInfo(None,None,path_identifier)
		return len(data) - len(left),nlri
