# encoding: utf-8
"""
flowspec_scope.py

Created by Stephane Litkowski on 2017-02-24.
"""

from struct import pack
from struct import unpack

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity


# ============================================================== InterfaceSet
# draft-ietf-idr-flowspsec-interfaceset 


@ExtendedCommunity.register
class InterfaceSet(ExtendedCommunity):
	COMMUNITY_TYPE = 0x07
	COMMUNITY_SUBTYPE = 0x02

	__slots__ = ['trans', 'asn','target','direction']

	def __init__ (self, trans, asn, target, direction, community=None):
		self.asn = asn
		self.target = target
		self.direction = direction	
		if (trans == 'transitive'):
			self.transitive = True
		else:
			self.transitive = False
		new_target =  (direction << 14) + target	
		ExtendedCommunity.__init__(
			self,
			community if community is not None else pack(
				"!2sLH",
				self._subtype(self.transitive),
				asn,new_target
			)
		)

	def __repr__ (self):
		if (self.direction == 1 ):
			str_direction = 'input'
		elif (self.direction == 2 ):
			str_direction = 'output'	
		elif (self.direction == 3):
			str_direction = 'input-output'
		else:
			str_direction = str(self.direction)	
		return "interface-set:%s:%s:%s" % (\
			str_direction,str(self.asn),str(self.target))

	@staticmethod
	def unpack (data):
		asn,target = unpack('!LH',data[2:8])
		direction = target >> 14
		target = target & 0x1FFF	
		return InterfaceSet(0,ASN(asn),target,direction,data[:8])
