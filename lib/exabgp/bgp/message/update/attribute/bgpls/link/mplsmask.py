# encoding: utf-8
"""
mplsmask.py

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
#     |L|R|  Reserved |
#     +-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.2  MPLS Protocol Mask

#   +------------+------------------------------------------+-----------+
#   |    Bit     | Description                              | Reference |
#   +------------+------------------------------------------+-----------+
#   |    'L'     | Label Distribution Protocol (LDP)        | [RFC5036] |
#   |    'R'     | Extension to RSVP for LSP Tunnels        | [RFC3209] |
#   |            | (RSVP-TE)                                |           |
#   | 'Reserved' | Reserved for future use                  |           |
#   +------------+------------------------------------------+-----------+



@LINKSTATE.register()
class MplsMask(object):
	TLV = 1094

	def __init__ (self, mplsflags):
		self.mplsflags = mplsflags

	def __repr__ (self):
		return "MPLS Protocol mask: %s" % (self.mplsflags)

	@classmethod
	def unpack (cls,data,length):
		mpls_mask = ['LDP', 'RSVP-TE', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
		if length > 1:
			raise Notify(3,5, "LINK TLV length too large")
		else:
			flag_array = binascii.b2a_hex(data[0])
			hex_rep = hex(int(flag_array, 16))
			bit_array = BitArray(hex_rep)
			valid_flags = [''.join(item)+'000000' for item in itertools.product('01', repeat=2)]
 			valid_flags.append('0000')
 			if bit_array.bin in valid_flags:
				flags = dict(zip(mpls_mask, bit_array.bin))
				return cls(mplsflags=flags)
			else:
				raise Notify(3,5, "Invalid MPLS flags mask")

	def json (self,compact=None):
		return '{ "mpls-mask" : %s }' % (str(self.mplsflags))
