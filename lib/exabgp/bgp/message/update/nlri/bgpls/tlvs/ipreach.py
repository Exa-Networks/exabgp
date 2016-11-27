# encoding: utf-8
"""
node.py

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2016 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.protocol.ip import IP
from exabgp.bgp.message.notification import Notify


#   The IP Reachability Information TLV is a mandatory TLV that contains
#   one IP address prefix (IPv4 or IPv6) originally advertised in the IGP
#   topology.  Its purpose is to glue a particular BGP service NLRI by
#   virtue of its BGP next hop to a given node in the LSDB.  A router
#   SHOULD advertise an IP Prefix NLRI for each of its BGP next hops.
#   The format of the IP Reachability Information TLV is shown in the
#   following figure:
#
#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     | Prefix Length | IP Prefix (variable)                         //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# ================================================================== IP REACHABILITY INFORMATION


class IpReach(object):

	def __init__ (self, prefix, packed=None):
		self.prefix = prefix
		self._packed = packed

	@classmethod
	def unpack (cls, data):
		plenght = unpack('!B',data[0])[0]
		psize = plenght / 8
		prefix = IP.unpack(data[1:psize])
		# prefix = unpack("!%dB" % psize ,data[1:psize])[0]
		return cls(prefix=prefix)

	def json (self, compact=None):
		return '"ip-reachability-tlv": %s' % self.prefix

	def __eq__ (self, other):
    		return self.prefix == other.prefix

	def __neq__ (self, other):
		return self.prefix != other.prefix

	def __lt__ (self, other):
		raise RuntimeError('Not implemented')

	def __le__ (self, other):
		raise RuntimeError('Not implemented')

	def __gt__ (self, other):
		raise RuntimeError('Not implemented')

	def __ge__ (self, other):
		raise RuntimeError('Not implemented')

	def __str__ (self):
		return ':'.join('%02X' % ord(_) for _ in self._packed)

	def __repr__ (self):
		return self.__str__()

	def __len__ (self):
		return len(self._packed)

	def __hash__ (self):
		return hash(str(self))

	def pack (self):
		return self._packed


