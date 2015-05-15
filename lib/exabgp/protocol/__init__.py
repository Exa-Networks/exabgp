# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


# ===================================================================== Protocol
# http://www.iana.org/assignments/protocol-numbers/

class Protocol (int):
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
	#
	_str = {
		ICMP: 'ICMP',
		IGMP: 'IGMP',
		TCP:  'TCP',
		EGP:  'EGP',
		UDP:  'UDP',
		RSVP: 'RSVP',
		GRE:  'GRE',
		ESP:  'ESP',
		AH:   'AH',
		OSPF: 'OSPF',
		IPIP: 'IPIP',
		PIM:  'PIP',
		SCTP: 'SCTP',
	}

	_value = dict([(r,l) for (l,r) in _str.items()])

	def __str__ (self):
		return self._str.get(self,'unknown protocol %d' % int(self))

	def pack (self):
		return chr(self)

	@staticmethod
	def named (protocol):
		name = protocol.upper()
		if name in Protocol._value:
			return Protocol(Protocol._value[name])
		raise ValueError('unknown protocol %s' % protocol)
