# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

from exabgp.structure.address import AFI,SAFI
from exabgp.message import Message,prefix

from exabgp.message.update.attribute.mprnlri     import MPRNLRI
from exabgp.message.update.attribute.mpurnlri    import MPURNLRI

# =================================================================== Update

class Update (Message):
	TYPE = chr(0x02)

	# All the route must be of the same family and have the same next-hop
	def __init__ (self,routes):
		self.routes = routes
		self.afi = routes[0].nlri.afi
		self.safi = routes[0].nlri.safi

	# The routes MUST have the same attributes ...
	def announce (self,asn4,local_asn,remote_asn,with_path_info):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(with_path_info) for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPRNLRI(self.routes).pack(with_path_info)
		attr = self.routes[0].attributes.bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix('') + prefix(attr + mp) + nlri)

	def update (self,asn4,local_asn,remote_asn,with_path_info):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(with_path_info) for route in self.routes])
			mp = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack(with_path_info) + MPRNLRI(self.routes).pack()
		attr = self.routes[0].attributes.bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix(nlri) + prefix(attr + mp) + nlri)

	# XXX: Remove those default values ? - most likely good.
	def withdraw (self,asn4=False,local_asn=None,remote_asn=None,with_path_info=None):
		if self.afi == AFI.ipv4 and self.safi in [SAFI.unicast, SAFI.multicast]:
			nlri = ''.join([route.nlri.pack(with_path_info) for route in self.routes])
			mp = ''
			attr = ''
		else:
			nlri = ''
			mp = MPURNLRI(self.routes).pack(with_path_info)
			attr = self.routes[0].attributes.bgp_announce(asn4,local_asn,remote_asn)
		return self._message(prefix(nlri) + prefix(attr + mp))
