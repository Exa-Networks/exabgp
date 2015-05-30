# encoding: utf-8
"""
ms.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================= MultiSession
#


@Capability.register()
@Capability.register(Capability.CODE.MULTISESSION_CISCO)
class MultiSession (Capability,list):
	ID = Capability.CODE.MULTISESSION

	def set (self, data):
		self.extend(data)
		return self

	# XXX: FIXME: Looks like we could do with something in this Caoability
	def __str__ (self):
		info = ' (RFC)' if self.ID == Capability.CODE.MULTISESSION else ''
		return 'Multisession%s %s' % (info,' '.join([str(capa) for capa in self]))

	def json (self):
		variant = 'RFC' if self.ID == Capability.CODE.MULTISESSION else 'Cisco'
		return '{ "name": "multisession", "variant": "%s" ,"capabilities": [%s ] }' % (variant, ','.join(' %s' % str(capa) for capa in self))

	def extract (self):
		rs = [chr(0),]
		for v in self:
			rs.append(chr(v))
		return rs

	@staticmethod
	def unpack_capability (instance, data, capability=None):  # pylint: disable=W0613
		# XXX: FIXME: we should set that that instance was seen and raise if seen twice
		return instance
