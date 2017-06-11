# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.enum import Enum

# ===================================================================== Protocol
# http://www.iana.org/assignments/protocol-numbers/

class Protocol (Enum):
	ICMP  = 0x01
	IGMP  = 0x02
	TCP   = 0x06
	EGP   = 0x08
	UDP   = 0x11
	RSVP  = 0x2E
	GRE   = 0x2F
	ESP   = 0x32
	AH    = 0x33
	OSPF  = 0x59
	IPIP  = 0x5E
	PIM   = 0x67
	SCTP  = 0x84

	def pack (self):
			return chr(self)


Protocol.UNKNOWN = "unknown protocol %s"

Protocol.NAME = {
	Protocol(Protocol.ICMP):  'ICMP',
	Protocol(Protocol.IGMP):  'IGMP',
	Protocol(Protocol.TCP):   'TCP',
	Protocol(Protocol.EGP):   'EGP',
	Protocol(Protocol.UDP):   'UDP',
	Protocol(Protocol.RSVP):  'RSVP',
	Protocol(Protocol.GRE):   'GRE',
	Protocol(Protocol.ESP):   'ESP',
	Protocol(Protocol.AH):    'AH',
	Protocol(Protocol.OSPF):  'OSPF',
	Protocol(Protocol.IPIP):  'IPIP',
	Protocol(Protocol.PIM):   'PIM',
	Protocol(Protocol.SCTP):  'SCTP',
}

Protocol.VALUE = {
	'ICMP':  Protocol(Protocol.ICMP),
	'IGMP':  Protocol(Protocol.IGMP),
	'TCP':   Protocol(Protocol.TCP),
	'EGP':   Protocol(Protocol.EGP),
	'UDP':   Protocol(Protocol.UDP),
	'RSVP':  Protocol(Protocol.RSVP),
	'GRE':   Protocol(Protocol.GRE),
	'ESP':   Protocol(Protocol.ESP),
	'AH':    Protocol(Protocol.AH),
	'OSPF':  Protocol(Protocol.OSPF),
	'IPIP':  Protocol(Protocol.IPIP),
	'PIM':   Protocol(Protocol.PIM),
	'SCTP':  Protocol(Protocol.SCTP),
}
