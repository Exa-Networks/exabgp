# encoding: utf-8
"""
protection.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2016 Exa Networks. All rights reserved.
"""

import binascii
import itertools
from exabgp.dep.bitstring import BitArray

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LINKSTATE


#       0                   1
#       0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#      |Protection Cap |    Reserved   |
#      +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#		https://tools.ietf.org/html/rfc5307 Sec 1.2
#      0x01  Extra Traffic
#      0x02  Unprotected
#      0x04  Shared
#      0x08  Dedicated 1:1
#      0x10  Dedicated 1+1
#      0x20  Enhanced
#      0x40  Reserved
#      0x80  Reserved


@LINKSTATE.register()
class LinkProtectionType(object):
	TLV = 1093
	def __init__ (self, protectionflags):
		self.protectionflags = protectionflags

	def __repr__ (self):
		return "Link protection mask: %s" % (self.protectionflags)

	@classmethod
	def unpack (cls,data,length):
		protection_mask = ['ExtraTrafic', 'Unprotected', 'Shared', 'Dedicated 1:1',
							'Dedicated 1+1', 'Enhanced', 'RSV', 'RSV']
		if length != 2:
			raise Notify(3,5, "Wrong size for protection type TLV")
		else:
			# We only care about the first octect
			flag_array = binascii.b2a_hex(data[0])
			hex_rep = hex(int(flag_array, 16))
			bit_array = BitArray(hex_rep)
			valid_flags = [''.join(item)+'00' for item in itertools.product('01', repeat=6)]
 			valid_flags.append('0000')
 			if bit_array.bin in valid_flags:
				flags = dict(zip(protection_mask, bit_array.bin))
		return cls(protectionflags=flags)

	def json (self,compact=None):
		return { "link-protection-flags" : str(self.protectionflags) }
