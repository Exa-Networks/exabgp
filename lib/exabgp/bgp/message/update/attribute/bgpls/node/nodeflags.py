# encoding: utf-8
"""
nodename.py

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
#     |O|T|E|B|R|V| Rsvd|
#     +-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752 Sec 3.3.1.1.  Node Flag Bits TLV

#        +-----------------+-------------------------+------------+
#        |       Bit       | Description             | Reference  |
#        +-----------------+-------------------------+------------+
#        |       'O'       | Overload Bit            | [ISO10589] |
#        |       'T'       | Attached Bit            | [ISO10589] |
#        |       'E'       | External Bit            | [RFC2328]  |
#        |       'B'       | ABR Bit                 | [RFC2328]  |
#        |       'R'       | Router Bit              | [RFC5340]  |
#        |       'V'       | V6 Bit                  | [RFC5340]  |
#        | Reserved (Rsvd) | Reserved for future use |            |
#        +-----------------+-------------------------+------------+
# 		https://tools.ietf.org/html/rfc7752 sec 3.3.1.1 Node Flag Bits Definitions



@LINKSTATE.register()
class NodeFlags(object):
	TLV = 1024
	def __init__ (self, nodeflags):
		self.nodeflags = nodeflags

	def __repr__ (self):
		return "nodeflags: %s" % (self.nodeflags)

	@classmethod
	def unpack (cls,data,length):
		node_flags = ['O', 'T', 'E', 'B', 'R', 'V', 'RSV', 'RSV']
		if length > 1:
			raise Notify(3,5, "Node Flags TLV length too large")
		else:
			flag_array = binascii.b2a_hex(data[0])
			hex_rep = hex(int(flag_array, 16))
			bit_array = BitArray(hex_rep)
			valid_flags = [''.join(item)+'00' for item in itertools.product('01', repeat=6)]
 			valid_flags.append('0000')
 			if bit_array.bin in valid_flags:
				flags = dict(zip(node_flags, bit_array.bin))
		return cls(nodeflags=flags)

	def json (self,compact=None):
		return '{ "node-flags" : %s }' % (str(self.nodeflags))
