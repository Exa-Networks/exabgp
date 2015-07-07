# encoding: utf-8
"""
inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


def label (tokeniser):
	labels = []
	value = tokeniser()

	if value == '[':
		while True:
			value = tokeniser()
			if label == ']':
				break
			labels.append(int(value))
	else:
		labels.append(int(value))

	return Labels(labels)


def route_distinguisher (tokeniser):
	data = tokeniser()

	separator = data.find(':')
	if separator > 0:
		prefix = data[:separator]
		suffix = int(data[separator+1:])

	if '.' in prefix:
		data = [chr(0),chr(1)]
		data.extend([chr(int(_)) for _ in prefix.split('.')])
		data.extend([chr(suffix >> 8),chr(suffix & 0xFF)])
		rtd = ''.join(data)
	else:
		number = int(prefix)
		if number < pow(2,16) and suffix < pow(2,32):
			rtd = chr(0) + chr(0) + pack('!H',number) + pack('!L',suffix)
		elif number < pow(2,32) and suffix < pow(2,16):
			rtd = chr(0) + chr(2) + pack('!L',number) + pack('!H',suffix)
		else:
			raise ValueError('invalid route-distinguisher %s' % data)

	return RouteDistinguisher(rtd)
