# encoding: utf-8
"""
id.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

class CapabilityID (object):
	RESERVED                 = 0x00  # [RFC5492]
	MULTIPROTOCOL_EXTENSIONS = 0x01  # [RFC2858]
	ROUTE_REFRESH            = 0x02  # [RFC2918]
	OUTBOUND_ROUTE_FILTERING = 0x03  # [RFC5291]
	MULTIPLE_ROUTES          = 0x04  # [RFC3107]
	EXTENDED_NEXT_HOP        = 0x05  # [RFC5549]
	#6-63      Unassigned
	GRACEFUL_RESTART         = 0x40  # [RFC4724]
	FOUR_BYTES_ASN           = 0x41  # [RFC4893]
	# 66 Deprecated
	DYNAMIC_CAPABILITY       = 0x43  # [Chen]
	MULTISESSION_BGP_RFC     = 0x44  # [draft-ietf-idr-bgp-multisession]
	ADD_PATH                 = 0x45  # [draft-ietf-idr-add-paths]
	ENHANCED_ROUTE_REFRESH   = 0x46  # [draft-ietf-idr-bgp-enhanced-route-refresh]
	OPERATIONAL              = 0x47  # ExaBGP only ...
	# 70-127    Unassigned
	CISCO_ROUTE_REFRESH      = 0x80  # I Can only find reference to this in the router logs
	# 128-255   Reserved for Private Use [RFC5492]
	MULTISESSION_BGP         = 0x83  # What Cisco really use for Multisession (yes this is a reserved range in prod !)

	EXTENDED_MESSAGE         = -1    # No yet defined by draft http://tools.ietf.org/html/draft-ietf-idr-extended-messages-02.txt

	unassigned = range(70,128)
	reserved = range(128,256)

from exabgp.util.enumeration import Enumeration
REFRESH = Enumeration ('absent','normal','enhanced')
