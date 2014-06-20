# encoding: utf-8
"""
community.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute import Flag

# from exabgp.bgp.message.update.attribute.community.extended.community import *
# from exabgp.bgp.message.update.attribute.community.extended.encapsulation import *
# from exabgp.bgp.message.update.attribute.community.extended.rt import *

class ECommunity (object):
	ID = AttributeID.EXTENDED_COMMUNITY
	FLAG = Flag.TRANSITIVE|Flag.OPTIONAL
	MULTIPLE = False

	# size of value for data (boolean: is extended)
	length_value = {False:7, True:6}
	name = {False: 'regular', True: 'extended'}

	def __init__ (self,community):
		# Two top bits are iana and transitive bits
		self.community = community

	def iana (self):
		return not not (self.community[0] & 0x80)

	def transitive (self):
		return not not (self.community[0] & 0x40)

	def pack (self,asn4=None):
		return self.community

	def json (self):
		return '[ %s, %s, %s, %s, %s, %s, %s, %s ]' % unpack('!BBBBBBBB',self.community)

	def __str__ (self):
		# 30/02/12 Quagga communities for soo and rt are not transitive when 4360 says they must be, hence the & 0x0F
		community_type = ord(self.community[0]) & 0x0F
		community_stype = ord(self.community[1])
		# Target
		if community_stype == 0x02:
			#return repr(RouteTarget.unpack(self.community))
			if community_type in (0x00,0x02):
				asn = unpack('!H',self.community[2:4])[0]
				ip = ip = '%s.%s.%s.%s' % unpack('!BBBB',self.community[4:])
				return "target:%d:%s" % (asn,ip)
			if community_type == 0x01:
				ip = '%s.%s.%s.%s' % unpack('!BBBB',self.community[2:6])
				asn = unpack('!H',self.community[6:])[0]
				return "target:%s:%d" % (ip,asn)
		# Origin
		if community_stype == 0x03:
			if community_type in (0x00,0x02):
				asn = unpack('!H',self.community[2:4])[0]
				ip = unpack('!L',self.community[4:])[0]
				return "origin:%d:%s" % (asn,ip)
			if community_type == 0x01:
				ip = '%s.%s.%s.%s' % unpack('!BBBB',self.community[2:6])
				asn = unpack('!H',self.community[6:])[0]
				return "origin:%s:%d" % (ip,asn)

		# # Encapsulation
		# if community_stype == 0x0c:
		# 	return repr(Encapsulation.unpack(self.community))

		# Layer2 Info Extended Community
		if community_stype == 0x0A:
			if community_type == 0x00:
				encaps = unpack('!B',self.community[2:3])[0]
				control = unpack('!B',self.community[3:4])[0]
				mtu = unpack('!H',self.community[4:6])[0]
				#juniper uses reserved(rfc4761) as a site preference
				reserved = unpack('!H',self.community[6:8])[0]
				return "L2info:%s:%s:%s:%s"%(encaps,control,mtu,reserved)

		# Traffic rate
		if self.community.startswith('\x80\x06'):
			speed = unpack('!f',self.community[4:])[0]
			if speed == 0.0:
				return 'discard'
			return 'rate-limit %d' % speed
		# redirect
		elif self.community.startswith('\x80\x07'):
			actions = []
			value = ord(self.community[-1])
			if value & 0x2:
				actions.append('sample')
			if value & 0x1:
				actions.append('terminal')
			return 'action %s' % '-'.join(actions)
		elif self.community.startswith('\x80\x08'):
			return 'redirect %d:%d' % (unpack('!H',self.community[2:4])[0],unpack('!L',self.community[4:])[0])
		elif self.community.startswith('\x80\x09'):
			return 'mark %d' % ord(self.community[-1])
		elif self.community.startswith('\x80\x00'):
			if self.community[-1] == '\x00':
				return 'redirect-to-nexthop'
			return 'copy-to-nexthop'
		else:
			h = 0x00
			for byte in self.community:
				h <<= 8
				h += ord(byte)
			return "0x%016X" % h

	def __len__ (self):
		return 8

	def __cmp__ (self,other):
		return cmp(self.pack(),other.pack())

	# @staticmethod
	# def unpack (data):
	# 	community_stype = ord(data[1])
	# 	if community_stype == 0x02:
	# 		return RouteTarget.unpack(data)
	# 	elif community_stype == 0x0c:
	# 		return Encapsulation.unpack(data)
	# 	else:
	# 		return ECommunity(data)
