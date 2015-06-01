# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.communities import Communities

from exabgp.bgp.message.notification import Notify


# ===================================================== ExtendedCommunities (16)
# http://www.iana.org/assignments/bgp-extended-communities

@Attribute.register()
class ExtendedCommunities (Communities):
	ID = Attribute.CODE.EXTENDED_COMMUNITY

	@staticmethod
	def unpack (data, negotiated):
		communities = ExtendedCommunities()
		while data:
			if data and len(data) < 8:
				raise Notify(3,1,'could not decode extended community %s' % str([hex(ord(_)) for _ in data]))
			communities.add(ExtendedCommunity.unpack(data[:8],negotiated))
			data = data[8:]
		return communities
