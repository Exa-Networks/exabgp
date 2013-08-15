# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

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

	def __str__ (self):
		if self == Protocol.ICMP:    return 'ICMP'
		if self == Protocol.IGMP:    return 'IGMP'
		if self == Protocol.TCP:     return 'TCP'
		if self == Protocol.EGP:     return 'EGP'
		if self == Protocol.UDP:     return 'UDP'
		if self == Protocol.RSVP:    return 'RSVP'
		if self == Protocol.GRE:     return 'GRE'
		if self == Protocol.ESP:     return 'ESP'
		if self == Protocol.AH:      return 'AH'
		if self == Protocol.OSPF:    return 'OSPF'
		if self == Protocol.IPIP:    return 'IPIP'
		if self == Protocol.PIM:     return 'PIM'
		if self == Protocol.SCTP:    return 'SCTP'
		return "unknown protocol %d" % int(self)

	def pack (self):
		return chr(self)

def NamedProtocol (protocol):
	name = protocol.upper()
	if   name == 'ICMP':  return Protocol(Protocol.ICMP)
	elif name == 'IGMP':  return Protocol(Protocol.IGMP)
	elif name == 'TCP':   return Protocol(Protocol.TCP)
	elif name == 'EGP':   return Protocol(Protocol.EGP)
	elif name == 'UDP':   return Protocol(Protocol.UDP)
	elif name == 'RSVP':  return Protocol(Protocol.RSVP)
	elif name == 'GRE':   return Protocol(Protocol.GRE)
	elif name == 'ESP':   return Protocol(Protocol.ESP)
	elif name == 'AH':    return Protocol(Protocol.AH)
	elif name == 'OSPF':  return Protocol(Protocol.OSPF)
	elif name == 'IPIP':  return Protocol(Protocol.IPIP)
	elif name == 'PIM':   return Protocol(Protocol.PIM)
	elif name == 'SCTP':  return Protocol(Protocol.SCTP)
	else: raise ValueError('unknown protocol %s' % name)
