# encoding: utf-8
"""
tcpflags.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

# http://www.iana.org/assignments/tcp-header-flags
class TCPFlags (int):
	FIN    = 0x1
	SYN    = 0x2
	RST  = 0x4
	PUSH   = 0x8
	ACK    = 0x10
	URGENT = 0x20

	def __str__ (self):
		if self == self.FIN:    return 'fin'
		if self == self.SYN:    return 'syn'
		if self == self.RST:    return 'rst'
		if self == self.PUSH:   return 'push'
		if self == self.ACK:    return 'ack'
		if self == self.URGENT: return 'urgent'
		return 'invalid tcp flag %d' % int.__str__(self)

	def __repr__ (self):
		return str(self)

def NamedTCPFlags (name):
	flag = name.lower()
	if flag == 'fin':    return TCPFlags(TCPFlags.FIN)
	if flag == 'syn':    return TCPFlags(TCPFlags.SYN)
	if flag == 'rst':    return TCPFlags(TCPFlags.RST)
	if flag == 'push':   return TCPFlags(TCPFlags.PUSH)
	if flag == 'ack':    return TCPFlags(TCPFlags.ACK)
	if flag == 'urgent': return TCPFlags(TCPFlags.URGENT)
	raise ValueError('invalid flag name %s' % flag)
