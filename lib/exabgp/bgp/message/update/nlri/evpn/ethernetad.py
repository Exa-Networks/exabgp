"""
ethernetad.py

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


# ===================================================================== EVPNNLRI

# +---------------------------------------+
# |      RD   (8 octets)                  |
# +---------------------------------------+
# |Ethernet Segment Identifier (10 octets)|
# +---------------------------------------+
# |  Ethernet Tag ID (4 octets)           |
# +---------------------------------------+
# |  MPLS Label (3 octets)                |
# +---------------------------------------+

class EthernetAD (EVPN):
	CODE = 1
	NAME = "Ethernet Auto-Discovery (A-D)"
	SHORT_NAME = "EthernetAD"

	def __init__ (self, **args):
		raise Exception('unimplemented')
