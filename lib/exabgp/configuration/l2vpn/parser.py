# encoding: utf-8
"""
l2vpn/parser.py

Created by Thomas Mangin on 2014-06-17.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.attribute import NextHopSelf

from exabgp.bgp.message.update.nlri import VPLS
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.rib.change import Change


def vpls (tokeniser):
	return Change(
		VPLS(None,None,None,None,None),
		Attributes()
	)


def vpls_endpoint (tokeniser):
	number = int(tokeniser())
	if number < 0 or number > 0xFFFF:
		raise ValueError('invalid l2vpn vpls endpoint')
	return number
	# vpls.endpoint = number


def vpls_size (tokeniser):
	number = int(tokeniser())
	if number < 0 or number > 0xFFFF:
		raise ValueError('invalid l2vpn vpls block-size')
	return number
	# vpls.size = number


def vpls_offset (tokeniser):
	number = int(tokeniser())
	if number < 0 or number > 0xFFFF:
		raise ValueError('invalid l2vpn vpls block-offset')
	return number
	# vpls.offset = number


def vpls_base (tokeniser):
	number = int(tokeniser())
	if number < 0 or number > 0xFFFF:
		raise ValueError('invalid l2vpn vpls label')
	return number
	# vpls.base = number

def next_hop (tokeniser):
	value = tokeniser()

	if value.lower() == 'self':
		return NextHopSelf(AFI.ipv4)
	return IP.create(value)
