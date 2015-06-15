# encoding: utf-8
"""
generic/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import socket

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.ip import IP


def string (tokeniser):
	return tokeniser()


def boolean (tokeniser, default):
	value = tokeniser()
	status = value.lower()
	if status in ('true','enable','enabled'):
		value = True
	elif status in ('false','disable','disabled'):
		value = False
	elif status in ('unset',):
		value = None
	else:
		tokeniser.rewind(value)
		return default
	return value


def port (tokeniser):
	value = tokeniser()
	try:
		return int(value)
	except ValueError:
		raise ValueError('"%s" is an invalid port' % value)
	if value < 0:
		raise ValueError('the port must positive')
	if value >= pow(2,16):
		raise ValueError('the port must be smaller than %d' % pow(2,16))
	return value


def asn (tokeniser, value=None):
	value = tokeniser() if value is None else value
	try:
		if value.count('.'):
			high,low = value.split('.',1)
			as_number = (int(high) << 16) + int(low)
		else:
			as_number = int(value)
		return ASN(as_number)
	except ValueError:
		raise ValueError('"%s" is an invalid ASN' % value)


def ip (tokeniser):
	value = tokeniser()
	try:
		return IP.create(value)
	except (IndexError,ValueError,socket.error):
		raise ValueError('"%s" is an invalid IP address' % value)
