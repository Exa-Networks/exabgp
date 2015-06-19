# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.current.core import Section

from exabgp.configuration.current.process.parser import encoder
from exabgp.configuration.current.process.parser import run


class ParseProcess (Section):
	syntax = \
		'syntax:\n' \
		'process name-of-process {\n' \
		'   run /path/to/command with its args;\n' \
		'   encoder text|json;\n' \
		'}\n\n' \


	known = {
		'encoder': encoder,
		'run':     run,
	}

	action = {
		'encoder': ['set'],
		'run':     ['set'],
	}

	name = 'process'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)
		self._processes = []

	def clear (self):
		self._processes = []

	def pre (self):
		name = self.tokeniser.line[1]
		if name in self._processes:
			return self.error.set('a process section called "%s" already exists' % name)
		self.scope.to_context(name)
		return True

	def post (self):
		difference = set(self.known.keys()).difference(self.scope.last().keys())
		if difference:
			return self.error.set('unset process sections: %s' % ', '.join(difference))
		return True

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
	# 	for direction in ['send','receive']:
	# 		for message in [
	# 			Message.CODE.NOTIFICATION,
	# 			Message.CODE.OPEN,
	# 			Message.CODE.KEEPALIVE,
	# 			Message.CODE.UPDATE,
	# 			Message.CODE.ROUTE_REFRESH,
	# 			Message.CODE.OPERATIONAL
	# 		]:
	# 			configuration.processes[_cli_name]['%s-%d' % (direction,message)] = False
	#
	# for name in configuration.processes.keys():
	# 	process = configuration.processes[name]
	#
	# 	neighbor.api.set('neighbor-changes',process.get('neighbor-changes',False))
	#
	# 	for direction in ['send','receive']:
	# 		for option in ['packets','consolidate','parsed']:
	# 			neighbor.api.set_value(direction,option,process.get('%s-%s' % (direction,option),False))
	#
	# 		for message in [
	# 			Message.CODE.NOTIFICATION,
	# 			Message.CODE.OPEN,
	# 			Message.CODE.KEEPALIVE,
	# 			Message.CODE.UPDATE,
	# 			Message.CODE.ROUTE_REFRESH,
	# 			Message.CODE.OPERATIONAL
	# 		]:
	# 			neighbor.api.set_message(direction,message,process.get('%s-%d' % (direction,message),False))

	# XXX: check that if we have any message, we have parsed/packets
	# XXX: and vice-versa
