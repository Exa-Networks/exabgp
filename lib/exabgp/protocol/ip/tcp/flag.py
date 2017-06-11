# encoding: utf-8
"""
tcpflags.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.enum import Enum

# ====================================================================== TCPFlag
# http://www.iana.org/assignments/tcp-header-flags

class TCPFlag (Enum):
	FIN    = 0x01
	SYN    = 0x02
	RST    = 0x04
	PUSH   = 0x08
	ACK    = 0x10
	URGENT = 0x20

TCPFlag.UNKNOWN = 'unknown tcp flag %s'

TCPFlag.VALUE = {
	'fin':    TCPFlag(TCPFlag.FIN),
	'syn':    TCPFlag(TCPFlag.SYN),
	'rst':    TCPFlag(TCPFlag.RST),
	'push':   TCPFlag(TCPFlag.PUSH),
	'ack':    TCPFlag(TCPFlag.ACK),
	'urgent': TCPFlag(TCPFlag.URGENT),
}

TCPFlag.NAME = {
	TCPFlag(TCPFlag.FIN):    'fin',
	TCPFlag(TCPFlag.SYN):    'syn',
	TCPFlag(TCPFlag.RST):    'rst',
	TCPFlag(TCPFlag.PUSH):   'push',
	TCPFlag(TCPFlag.ACK):    'ack',
	TCPFlag(TCPFlag.URGENT): 'urgent',
}
