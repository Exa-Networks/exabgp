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

	_value = {
		'FIN':    FIN,
		'SYN':    SYN,
		'RST':    RST,
		'PUSH':   PUSH,
		'ACK':    ACK,
		'URGENT': URGENT,
	}

	_str = dict([(r,l) for (l,r) in _value.items()])

	def __str__ (self):
		return self._str.get(self,'unknown tcp flag %d' % int(self))

	@staticmethod
	def named (flag):
		name = flag.upper()
		if name in TCPFlag._value:
			return TCPFlag(TCPFlag._value[name])
		raise ValueError('unknown tcp flag %s' % flag)
