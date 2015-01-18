# encoding: utf-8
"""
tcpflags.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


# ====================================================================== TCPFlag
# http://www.iana.org/assignments/tcp-header-flags

class TCPFlag (int):
	FIN    = 0x01
	SYN    = 0x02
	RST    = 0x04
	PUSH   = 0x08
	ACK    = 0x10
	URGENT = 0x20

	def __str__ (self):
		if self == self.FIN:
			return 'fin'
		if self == self.SYN:
			return 'syn'
		if self == self.RST:
			return 'rst'
		if self == self.PUSH:
			return 'push'
		if self == self.ACK:
			return 'ack'
		if self == self.URGENT:
			return 'urgent'
		return 'unknown tcp flag %d' % int(self)


def NamedTCPFlag (name):
	flag = name.lower()
	if flag == 'fin':
		return TCPFlag(TCPFlag.FIN)
	if flag == 'syn':
		return TCPFlag(TCPFlag.SYN)
	if flag == 'rst':
		return TCPFlag(TCPFlag.RST)
	if flag == 'push':
		return TCPFlag(TCPFlag.PUSH)
	if flag == 'ack':
		return TCPFlag(TCPFlag.ACK)
	if flag == 'urgent':
		return TCPFlag(TCPFlag.URGENT)
	raise ValueError('unknown tcp flag %s' % flag)
