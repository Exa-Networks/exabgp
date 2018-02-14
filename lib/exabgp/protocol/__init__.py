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

	def __init__(self, value):
		Enum.__init__(self, value)
		if self < 0 or self > 255:
			raise ValueError("Protocol must be between 0 and 255")

	def pack (self):
		return chr(self)


Protocol.UNKNOWN = "unknown protocol %s"

Protocol.NAME = {
	Protocol(Protocol.ICMP):  'icmp',
	Protocol(Protocol.IGMP):  'igmp',
	Protocol(Protocol.TCP):   'tcp',
	Protocol(Protocol.EGP):   'egp',
	Protocol(Protocol.UDP):   'udp',
	Protocol(Protocol.RSVP):  'rsvp',
	Protocol(Protocol.GRE):   'gre',
	Protocol(Protocol.ESP):   'esp',
	Protocol(Protocol.AH):    'ah',
	Protocol(Protocol.OSPF):  'ospf',
	Protocol(Protocol.IPIP):  'ipip',
	Protocol(Protocol.PIM):   'pim',
	Protocol(Protocol.SCTP):  'sctp',
}

Protocol.VALUE = {
	'icmp':  Protocol(Protocol.ICMP),
	'igmp':  Protocol(Protocol.IGMP),
	'tcp':   Protocol(Protocol.TCP),
	'egp':   Protocol(Protocol.EGP),
	'udp':   Protocol(Protocol.UDP),
	'rsvp':  Protocol(Protocol.RSVP),
	'gre':   Protocol(Protocol.GRE),
	'esp':   Protocol(Protocol.ESP),
	'ah':    Protocol(Protocol.AH),
	'ospf':  Protocol(Protocol.OSPF),
	'ipip':  Protocol(Protocol.IPIP),
	'pim':   Protocol(Protocol.PIM),
	'sctp':  Protocol(Protocol.SCTP),
}
