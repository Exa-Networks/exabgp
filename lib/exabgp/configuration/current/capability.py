# encoding: utf-8
"""
parse_capability.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.basic import Basic


class ParseCapability (Basic):
	TTL_SECURITY = 255

	syntax = \
		'syntax:\n' \
		'capability {\n' \
		'   graceful-restart <time in second>;\n' \
		'   asn4 enable|disable;\n' \
		'   add-path disable|send|receive|send/receive;\n' \
		'   multi-session enable|disable;\n' \
		'   operational enable|disable;\n' \
		'}\n'

	def __init__ (self, scope, error, logger):
		self.scope = scope
		self.error = error
		self.logger = logger

	def clear (self):
		pass

	def gracefulrestart (self, name, command, tokens):
		if not len(tokens):
			self.scope.content[-1][command] = None
			return True

		if tokens and tokens[0] in ('disable','disabled'):
			return True

		try:
			# README: Should it be a subclass of int ?
			grace = int(tokens[0])
		except ValueError:
			return self.error.set('"%s" is an invalid graceful-restart time' % ' '.join(tokens))

		if grace < 0:
			return self.error.set('graceful-restart can not be negative')
		if grace >= pow(2,16):
			return self.error.set('graceful-restart must be smaller than %d' % pow(2,16))

		self.scope.content[-1][command] = grace
		return True

	def addpath (self, name, command, tokens):
		try:
			ap = tokens[0].lower()
			apv = 0
			if ap.endswith('receive'):
				apv += 1
			if ap.startswith('send'):
				apv += 2
			if not apv and ap not in ('disable','disabled'):
				return self.error.set('invalid add-path')
			self.scope.content[-1][command] = apv
			return True
		except (ValueError,IndexError):
			return self.error.set('"%s" is an invalid add-path' % ' '.join(tokens) + '\n' + self.syntax)

	def asn4 (self, name, command, tokens):
		if not tokens:
			self.scope.content[-1][command] = True
			return True

		asn4 = tokens[0].lower()

		if asn4 in ('disable','disabled'):
			self.scope.content[-1][command] = False
			return True
		if asn4 in ('enable','enabled'):
			self.scope.content[-1][command] = True
			return True

		return self.error.set('"%s" is an invalid asn4 parameter options are enable (default) and disable)' % ' '.join(tokens))

	refresh = Basic.boolean
	multisession = Basic.boolean
	operational = Basic.boolean
	aigp = Basic.boolean
