# encoding: utf-8
"""
parse_neighbor.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import string

from exabgp.protocol.ip import IP

from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID

from exabgp.configuration.current.basic import Basic
from exabgp.configuration.current.capability import ParseCapability


class ParseNeighbor (Basic):
	TTL_SECURITY = 255

	syntax = ''

	def __init__ (self, error):
		self.error = error
		self.capability = ParseCapability(error)

	def clear (self):
		pass

	def router_id (self, scope, command, tokens):
		try:
			ip = RouterID(tokens[0])
		except (IndexError,ValueError):
			return self.error.set('"%s" is an invalid IP address' % ' '.join(tokens))

		scope[-1][command] = ip
		return True

	def ip (self, scope, command, tokens):
		try:
			ip = IP.create(tokens[0])
		except (IndexError,ValueError):
			return self.error.set('"%s" is an invalid IP address' % ' '.join(tokens))

		scope[-1][command] = ip
		return True

	def description (self, scope, command, tokens):
		text = ' '.join(tokens)
		if len(text) < 2 or text[0] != '"' or text[-1] != '"' or text[1:-1].count('"'):
			return self.error.set('syntax: description "<description>"')

		scope[-1]['description'] = text[1:-1]
		return True

	def asn (self, scope, command, tokens):
		try:
			value = Basic.newASN(tokens[0])
		except ValueError:
			return self.error.set('"%s" is an invalid ASN' % ' '.join(tokens))
		except IndexError:
			return self.error.set('please provide an ASN')

		scope[-1][command] = value
		return True

	def passive (self, scope, command, tokens):
		if tokens:
			return self.error.set('"%s" is an invalid for passive' % ' '.join(tokens))

		scope[-1][command] = True
		return True

	def listen (self, scope, command, tokens):
		try:
			listen = int(tokens[0])
		except IndexError:
			return self.error.set('please provide a port to listen on')
		except ValueError:
			return self.error.set('"%s" is an invalid port to listen on' % ' '.join(tokens))

		if listen < 0:
			return self.error.set('the listenening port must positive')
		if listen >= pow(2,16):
			return self.error.set('the listening port must be smaller than %d' % pow(2,16))

		scope[-1][command] = listen
		return True

	def hostname (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('single host-name required')

		name = tokens[0]

		if not name:
			return self.error.set('bad host-name')
		if not name[0].isalnum() or name[0].isdigit():
			return self.error.set('bad host-name')
		if not name[-1].isalnum() or name[-1].isdigit():
			return self.error.set('bad host-name')
		if '..' in name:
			return self.error.set('bad host-name')
		if not all(True if c in string.ascii_letters + string.digits + '.-' else False for c in name):
			return self.error.set('bad host-name')
		if len(name) > 255:
			return self.error.set('bad host-name (length)')

		scope[-1][command] = name.encode('utf-8')
		return True

	def domainname (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('single domain-name required')

		name = tokens[0]

		if not name:
			return self.error.set('bad domain-name')
		if not name[0].isalnum() or name[0].isdigit():
			return self.error.set('bad domain-name')
		if not name[-1].isalnum() or name[-1].isdigit():
			return self.error.set('bad domain-name')
		if '..' in name:
			return self.error.set('bad domain-name')
		if not all(True if c in string.ascii_letters + string.digits + '.-' else False for c in name):
			return self.error.set('bad domain-name')
		if len(name) > 255:
			return self.error.set('bad domain-name (length)')

		scope[-1][command] = name.encode('utf-8')
		return True

	def holdtime (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('hold-time required')

		try:
			holdtime = HoldTime(tokens[0])
		except ValueError:
			return self.error.set('"%s" is an invalid hold-time' % ' '.join(tokens))

		if holdtime < 3 and holdtime != 0:
			return self.error.set('holdtime must be zero or at least three seconds')
		if holdtime >= pow(2,16):
			return self.error.set('holdtime must be smaller than %d' % pow(2,16))

		scope[-1][command] = holdtime
		return True

	def md5 (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('md5 required')

		md5 = tokens[0]
		if len(md5) > 2 and md5[0] == md5[-1] and md5[0] in ['"',"'"]:
			md5 = md5[1:-1]

		if len(md5) > 80:
			return self.error.set('md5 password must be no larger than 80 characters')
		if not md5:
			return self.error.set('md5 requires the md5 password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.')

		scope[-1][command] = md5
		return True

	def ttl (self, scope, command, tokens):
		if not len(tokens):
			scope[-1][command] = self.TTL_SECURITY
			return True

		try:
			# README: Should it be a subclass of int ?
			ttl = int(tokens[0])
		except ValueError:
			return self.error.set('"%s" is an invalid ttl-security (1-254)' % ' '.join(tokens))

		if ttl <= 0:
			return self.error.set('ttl-security must be a positive number (1-254)')
		if ttl >= 255:
			return self.error.set('ttl must be smaller than 255 (1-254)')

		scope[-1][command] = ttl
		return True

	groupupdate = Basic.boolean
	autoflush = Basic.boolean
	adjribout = Basic.boolean
