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
	status = tokeniser().lower()
	if not status:
		return default
	if status in ('true','enable','enabled'):
		return True
	if status in ('false','disable','disabled'):
		return False
	if status in ('unset',):
		return None
	raise ValueError('invalid value for a boolean')


def port (tokeniser):
	if not tokeniser.tokens:
		raise ValueError('a port number is required')

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
	if value is None:
		if not tokeniser.tokens:
			raise ValueError('an asn is required')

	value = tokeniser()
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
	if not tokeniser.tokens:
		raise ValueError('an ip address is required')

	value = tokeniser()
	try:
		return IP.create(value)
	except (IndexError,ValueError,socket.error):
		raise ValueError('"%s" is an invalid IP address' % value)
