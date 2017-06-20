# encoding: utf-8
"""
communities.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import ordinal
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.initial.communities import Communities

from exabgp.bgp.message.notification import Notify


# ===================================================== ExtendedCommunities (16)
# https://www.iana.org/assignments/bgp-extended-communities

@Attribute.register()
class ExtendedCommunities (Communities):
	ID = Attribute.CODE.EXTENDED_COMMUNITY

	@staticmethod
	def unpack (data, negotiated):
		communities = ExtendedCommunities()
		while data:
			if data and len(data) < 8:
				raise Notify(3,1,'could not decode extended community %s' % str([hex(ordinal(_)) for _ in data]))
			communities.add(ExtendedCommunity.unpack(data[:8],negotiated))
			data = data[8:]
		return communities
