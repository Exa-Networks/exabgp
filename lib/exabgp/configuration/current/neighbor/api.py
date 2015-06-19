# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section
from exabgp.configuration.current.parser import boolean
from exabgp.configuration.current.neighbor.parser import processes

from exabgp.bgp.message import Message


def _direction (tokeniser,way):
	name = ''
	if name not in ('open','update','notification','keepalive','refresh','operational'):
		raise ValueError('"%s" is an invalid option' % name)

	message = Message.from_string(name)
	if message == Message.CODE.NOP:
		raise ValueError('unknown process message')

	return '%s-%d' % (way,message)

class ParseAPI (Section):
	syntax = \
		'syntax:\n' \
		'process {\n' \
		'   processes [ name-of-processes ];\n' \
		'   neighbor-changes;\n' \
		'   send {\n' \
		'      parsed;\n' \
		'      packets;\n' \
		'      consolidate;\n' \
		'      open;\n' \
		'      update;\n' \
		'      notification;\n' \
		'      keepalive;\n' \
		'      refresh;\n' \
		'      operational;\n' \
		'   }\n' \
		'   receive {\n' \
		'      parsed;\n' \
		'      packets;\n' \
		'      consolidate;\n' \
		'      open;\n' \
		'      update;\n' \
		'      notification;\n' \
		'      keepalive;\n' \
		'      refresh;\n' \
		'      operational;\n' \
		'   }\n' \
		'}\n\n' \

	name = 'api'

	known = {
		'processes':        processes,
		'neighbor-changes': boolean,
	}

	action = {
		'processes':        ['set'],
		'neighbor-changes': ['set'],
	}

	default = {
		'neighbor-changes': True,
	}

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def clear (self):
		pass

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		return True



class _ParseDirection (Section):
	syntax = ParseAPI.syntax

	action = {
		'parsed':       ['set'],
		'packets':      ['set'],
		'consolidate':  ['set'],
		'open':         ['set'],
		'update':       ['set'],
		'notification': ['set'],
		'keepalive':    ['set'],
		'refresh':      ['set'],
		'operational':  ['set'],
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

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)

	def pre (self):
		self.scope.to_context()
		return True

	def post (self):
		import pdb; pdb.set_trace()
		return True


class ParseSend (_ParseDirection):
	name = 'send'


class ParseReceive (_ParseDirection):
	name = 'receive'


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
	# 			Message.CODE.NOTIFICATION,
	# 			Message.CODE.OPEN,
	# 			Message.CODE.KEEPALIVE,
	# 			Message.CODE.UPDATE,
	# 			Message.CODE.ROUTE_REFRESH,
	# 			Message.CODE.OPERATIONAL
	# 		]:
	# 			configuration.processes[_cli_name]['%s-%d' % (receive,message)] = False
	#
	# for name in configuration.processes.keys():
	# 	process = configuration.processes[name]
	#
	# 	neighbor.api.set('neighbor-changes',process.get('neighbor-changes',False))
	#
	# 	for receive in ['send','receive']:
	# 		for option in ['packets','consolidate','parsed']:
	# 			neighbor.api.set_value(receive,option,process.get('%s-%s' % (receive,option),False))
	#
	# 		for message in [
	# 			Message.CODE.NOTIFICATION,
	# 			Message.CODE.OPEN,
	# 			Message.CODE.KEEPALIVE,
	# 			Message.CODE.UPDATE,
	# 			Message.CODE.ROUTE_REFRESH,
	# 			Message.CODE.OPERATIONAL
	# 		]:
	# 			neighbor.api.set_message(receive,message,process.get('%s-%d' % (receive,message),False))

	# XXX: check that if we have any message, we have parsed/packets
	# XXX: and vice-versa
