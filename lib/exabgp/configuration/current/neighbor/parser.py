# encoding: utf-8
"""
neighbor/parser.py

Created by Thomas Mangin on 2014-07-01.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import socket
import string

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.holdtime import HoldTime

from exabgp.configuration.current.generic.parser import string
from exabgp.configuration.current.generic.parser import port


def hostname (tokeniser):
	value = string(tokeniser)
	if not value[0].isalnum() or value[0].isdigit():
		raise ValueError('bad host-name (alphanumeric)')
	if not value[-1].isalnum() or value[-1].isdigit():
		raise ValueError('bad host-name (alphanumeric)')
	if '..' in value:
		raise ValueError('bad host-name (double colon)')
	if not all(True if c in string.ascii_letters + string.digits + '.-' else False for c in value):
		raise ValueError('bad host-name (charset)')
	if len(value) > 255:
		raise ValueError('bad host-name (length)')

	return value


def domainname (tokeniser):
	value = string(tokeniser)
	if not value:
		raise ValueError('bad domain-name')
	if not value[0].isalnum() or value[0].isdigit():
		raise ValueError('bad domain-name')
	if not value[-1].isalnum() or value[-1].isdigit():
		raise ValueError('bad domain-name')
	if '..' in value:
		raise ValueError('bad domain-name')
	if not all(True if c in string.ascii_letters + string.digits + '.-' else False for c in value):
		raise ValueError('bad domain-name')
	if len(name) > 255:
		raise ValueError('bad domain-name (length)')
	return value


def description (tokeniser):
	try:
		return string(tokeniser)
	except:
		raise ValueError('bad neighbor description')


def md5 (tokeniser):
	value = tokeniser()
	if len(value) > 80:
		raise ValueError('MD5 password must be no larger than 80 characters')
	if not value:
		raise ValueError('value requires the value password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.')
	return value


def ttl (tokeniser):
	value = tokeniser()
	try:
		attl = int(value)
	except ValueError:
		if value in ('false','disable','disabled'):
			return None
		raise ValueError('invalid ttl-security "%s"' % value)
	if attl < 0:
		raise ValueError('ttl-security can not be negative')
	if attl >= 255:
		raise ValueError('ttl must be smaller than 256')
	return attl


def router_id (tokeniser):
	value = tokeniser()
	try:
		return RouterID(value)
	except ValueError:
		raise ValueError ('"%s" is an invalid router-id' % value)


def hold_time (tokeniser):
	value = tokeniser()
	try:
		hold_time = HoldTime(value)
	except ValueError:
		raise ValueError ('"%s" is an invalid hold-time' % value)
	if hold_time < 3 and hold_time != 0:
		raise ValueError('holdtime must be zero or at least three seconds')
	# XXX: FIXME: add HoldTime.MAX and reference it ( pow -1 )
	if hold_time >= pow(2,16):
		raise ValueError('holdtime must be smaller than %d' % pow(2,16))
	return hold_time
