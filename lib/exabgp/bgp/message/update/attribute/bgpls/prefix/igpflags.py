# encoding: utf-8
"""
igpflags.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2016 Exa Networks. All rights reserved.
"""
import binascii
import itertools

from exabgp.dep.bitstring import BitArray

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |D|N|L|P| Resvd.|
#     +-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.3.1
#
#           +----------+---------------------------+-----------+
#           |   Bit    | Description               | Reference |
#           +----------+---------------------------+-----------+
#           |   'D'    | IS-IS Up/Down Bit         | [RFC5305] |
#           |   'N'    | OSPF "no unicast" Bit     | [RFC5340] |
#           |   'L'    | OSPF "local address" Bit  | [RFC5340] |
#           |   'P'    | OSPF "propagate NSSA" Bit | [RFC5340] |
#           | Reserved | Reserved for future use.  |           |
#           +----------+---------------------------+-----------+




@LINKSTATE.register()
class IgpFlags(object):
	TLV = 1152

	def __init__ (self, igpflags):
		self.igpflags = igpflags

	def __repr__ (self):
		return "IGP flags: %s" % (self.igpflags)

	@classmethod
	def unpack (cls,data,length):
		igpflags = ['D', 'N', 'L', 'P']
		if length > 1:
			raise Notify(3,5, "IGP Flags TLV length too large")
		else:
			flag_array = binascii.b2a_hex(data[0])
			hex_rep = hex(int(flag_array, 16))
			bit_array = BitArray(hex_rep)
			valid_flags = [''.join(item)+'0000' for item in itertools.product('01', repeat=4)]
 			valid_flags.append('0000')
 			if bit_array.bin in valid_flags:
				flags = dict(zip(igpflags, bit_array.bin))
				return cls(igpflags=flags)
			else:
    				raise Notify(3,5, "Invalid IGP flags mask")

	def json (self,compact=None):
		return '{ "igp-flags" : %s }' % (str(self.igpflags))
