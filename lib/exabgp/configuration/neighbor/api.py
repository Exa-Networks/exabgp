# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import time
from collections import defaultdict

from exabgp.configuration.core import Section
from exabgp.configuration.parser import boolean
from exabgp.configuration.neighbor.parser import processes

from exabgp.bgp.message import Message


class _ParseDirection (Section):
	action = {
		'parsed':       'set-command',
		'packets':      'set-command',
		'consolidate':  'set-command',
		'open':         'set-command',
		'update':       'set-command',
		'notification': 'set-command',
		'keepalive':    'set-command',
		'refresh':      'set-command',
		'operational':  'set-command',
	}

	known = {
		'parsed':       boolean,
		'packets':      boolean,
		'consolidate':  boolean,
		'open':         boolean,
		'update':       boolean,
		'notification': boolean,
		'keepalive':    boolean,
		'refresh':      boolean,
		'operational':  boolean,
	}

	default = {
		'parsed':       True,
		'packets':      True,
		'consolidate':  True,
		'open':         True,
		'update':       True,
		'notification': True,
		'keepalive':    True,
		'refresh':      True,
		'operational':  True,
	}

	syntax = '{\n  %s;\n}' % ';\n  '.join(default.keys())

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		pass

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		return True


class ParseSend (_ParseDirection):
	syntax = \
		'send %s' % _ParseDirection.syntax

	name = 'api/send'


class ParseReceive (_ParseDirection):
	syntax = \
		'receive %s' % _ParseDirection.syntax

	name = 'api/receive'


class ParseAPI (Section):
	syntax = \
		'process {\n' \
		'  processes [ name-of-processes ];\n' \
		'  neighbor-changes;\n' \
		'  %s\n' \
		'  %s\n' \
		'}' % (
			'\n  '.join(ParseSend.syntax.split('\n')),
			'\n  '.join(ParseReceive.syntax.split('\n'))
		)

	known = {
		'processes':        processes,
		'neighbor-changes': boolean,
	}

	action = {
		'processes':        'set-command',
		'neighbor-changes': 'set-command',
	}

	default = {
		'neighbor-changes': True,
	}

	DEFAULT_API = {
		'neighbor-changes': []
	}

	name = 'api'

	_built = defaultdict(list)

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)
		self.named = ''

	@classmethod
	def extract (cls):
		if cls._built:
			parsed = cls._built
			cls._built = defaultdict(list)
			return parsed
		return cls.DEFAULT_API

	def clear (self):
		type(self)._built = defaultdict(list)

	def pre (self):
		self.scope.to_context()
		named = self.tokeniser.iterate()
		self.named = named if named else 'auto-named-%d' % int(time.time()*1000000)
		self.check_name(self.named)
		self.scope.to_context()
		return True

	def post (self):
		self.scope.to_context(self.name)
		api = self.scope.pop()
		procs = api.get('processes',[])

		type(self)._built['processes'].extend(procs)

		for command in ('neighbor-changes',):
			type(self)._built[command].extend(procs if api.get(command,False) else [])

		for direction in ('send','receive'):
			data = api.get(direction,{})
			for action in ('parsed','packets','consolidate','open', 'update', 'notification', 'keepalive', 'refresh', 'operational'):
				type(self)._built["%s-%s" % (direction,action)].extend(procs if data.get(action,False) else [])

		return True


for way in ('send','receive'):
	for name in ('parsed','packets','consolidate','open', 'update', 'notification', 'keepalive', 'refresh', 'operational'):
		ParseAPI.DEFAULT_API["%s-%s" % (way,name)] = []

	# we want to have a socket for the cli
	# if self.fifo:
	# 	_cli_name = 'CLI'
	# 	configuration.processes[_cli_name] = {
	# 		'neighbor': '*',
	# 		'encoder': 'json',
	# 		'run': [sys.executable, sys.argv[0]],
	#
	# 		'neighbor-changes': False,
	#
	# 		'receive-consolidate': False,
	# 		'receive-packets': False,
	# 		'receive-parsed': False,
	#
	# 		'send-consolidate': False,
	# 		'send-packets': False,
	# 		'send-parsed': False,
	# 	}
	#
	# 	for receive in ['send','receive']:
	# 		for message in [
	# 			Message.CODE.NOTIFICATION.SHORT,
	# 			Message.CODE.OPEN.SHORT,
	# 			Message.CODE.KEEPALIVE.SHORT,
	# 			Message.CODE.UPDATE.SHORT,
	# 			Message.CODE.ROUTE_REFRESH.SHORT,
	# 			Message.CODE.OPERATIONAL.SHORT,
	# 		]:
	# 			configuration.processes[_cli_name]['%s-%s' % (receive,message)] = False

	# XXX: check that if we have any message, we have parsed/packets
	# XXX: and vice-versa
