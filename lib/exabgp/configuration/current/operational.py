# encoding: utf-8
"""
parse_operational.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.util.ip import isipv4

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.operational import MAX_ADVISORY
from exabgp.bgp.message.operational import Advisory
from exabgp.bgp.message.operational import Query
from exabgp.bgp.message.operational import Response

from exabgp.configuration.current.format import formated

from exabgp.configuration.current.basic import Basic


class ParseOperational (Basic):
	syntax = \
		'syntax:\n' \
		''

	def __init__ (self, error):
		self.error = error

		self._dispatch = {
			'asm':  self._asm,
			'adm':  self._adm,
			'rpcq': self._rpcq,
			'rpcq': self._rpcq,
			'apcq': self._apcq,
			'apcp': self._apcp,
			'lpcq': self._lpcq,
			'lpcp': self._lpcp,
		}

	def clear (self):
		pass

	def asm (self, scope, command,tokens):
		operational = self._operational(Advisory.ASM,['afi','safi','advisory'],' '.join(tokens))

		if not operational:
			return self.error.set('could not make operational message')

		if 'operational-message' not in scope[-1]:
			scope[-1]['operational-message'] = []

		# iterate on each family for the peer if multiprotocol is set.
		scope[-1]['operational-message'].append(operational)
		return True

	def operational (self,what,tokens):
		return self._dispatch.get(what,lambda _: False)(tokens)

	def _asm (self, tokens):
		return self._operational(Advisory.ASM,['afi','safi','advisory'],tokens)

	def _adm (self, tokens):
		return self._operational(Advisory.ADM,['afi','safi','advisory'],tokens)

	def _rpcq (self, tokens):
		return self._operational(Query.RPCQ,['afi','safi','sequence'],tokens)

	def _rpcp (self, tokens):
		return self._operational(Response.RPCP,['afi','safi','sequence','counter'],tokens)

	def _apcq (self, tokens):
		return self._operational(Query.APCQ,['afi','safi','sequence'],tokens)

	def _apcp (self, tokens):
		return self._operational(Response.APCP,['afi','safi','sequence','counter'],tokens)

	def _lpcq (self, tokens):
		return self._operational(Query.LPCQ,['afi','safi','sequence'],tokens)

	def _lpcp (self, tokens):
		return self._operational(Response.LPCP,['afi','safi','sequence','counter'],tokens)

	def _operational (self, klass, parameters, tokens):
		def utf8 (string): return string.encode('utf-8')[1:-1]

		convert = {
			'afi': AFI.value,
			'safi': SAFI.value,
			'sequence': int,
			'counter': long,
			'advisory': utf8
		}

		def valid (_):
			return True

		def u32 (_):
			return int(_) <= 0xFFFFFFFF

		def u64 (_):
			return long(_) <= 0xFFFFFFFFFFFFFFFF

		def advisory (_):
			return len(_.encode('utf-8')) <= MAX_ADVISORY + 2  # the two quotes

		validate = {
			'afi': AFI.value,
			'safi': SAFI.value,
			'sequence': u32,
			'counter': u64,
		}

		number = len(parameters)*2
		tokens = formated(tokens).split(' ',number-1)
		if len(tokens) != number:
			return self.error.set('invalid operational syntax, wrong number of arguments')

		data = {}

		while tokens and parameters:
			command = tokens.pop(0).lower()
			value = tokens.pop(0)

			if command == 'router-id':
				if isipv4(value):
					data['routerid'] = RouterID(value)
				else:
					self.error.set('invalid operational value for %s' % command)
					return None
				continue

			expected = parameters.pop(0)

			if command != expected:
				self.error.set('invalid operational syntax, unknown argument %s' % command)
				return None
			if not validate.get(command,valid)(value):
				self.error.set('invalid operational value for %s' % command)
				return None

			data[command] = convert[command](value)

		if tokens or parameters:
			self.error.set('invalid advisory syntax, missing argument(s) %s' % ', '.join(parameters))
			return None

		if 'routerid' not in data:
			data['routerid'] = None

		return klass(**data)
