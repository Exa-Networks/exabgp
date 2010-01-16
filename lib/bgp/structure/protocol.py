#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from struct import pack

# =================================================================== Protocol

# http://www.iana.org/assignments/protocol-numbers/
class Protcol (int):
	ICMP  = 0x01
	TCP   = 0x06
	UDP   = 0x11
	SCTP  = 0x84
	
	def __str__ (self):
		if self == 0x01: return "ICMP"
		if self == 0x06: return "TCP"
		if self == 0x11: return "UDP"
		if self == 0x84: return "SCTP"
		return "unknown protocol"

	def pack (self):
		return chr(self)
