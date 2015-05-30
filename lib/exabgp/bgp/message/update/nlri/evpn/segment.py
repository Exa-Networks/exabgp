# encoding: utf-8
"""
segment.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

# from struct import pack
# from struct import unpack

# from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI
# from exabgp.bgp.message.update.nlri.qualifier.esi import ESI

# from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
# from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  IP Address Length (1 octet)          |
# +---------------------------------------+
# |   Originating Router's IP Addr        |
# |          (4 or 16 octets)             |
# +---------------------------------------+

# ===================================================================== EVPNNLRI


class EthernetSegment (EVPN):
	CODE = 1
	NAME = "Ethernet Segment"
	SHORT_NAME = "Segment"

	def __init__ (self, **args):
		raise Exception('unimplemented')
