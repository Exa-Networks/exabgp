# encoding: utf-8
"""
decoder/__init__.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.reactor.api.parser import Parser
from exabgp.reactor.api.command import Command
from exabgp.logger import Logger


# ======================================================================= Parser
#

class Handler (object):
	callback = {
		'text': {},
		'json': {},
	}

	# need to sort and reverse, in order for the shorter command to not used by error
	# "show neighbor" should not match "show neighbors"
	functions = sorted([
		'withdraw watchdog',
		'withdraw vpls',
		'withdraw route',
		'withdraw flow',
		'withdraw attribute',
		'version',
		'teardown',
		'shutdown',
		'show routes extensive',
		'show routes',
		'show neighbors',
		'show neighbor',
		'restart',
		'reload',
		'flush route',
		'announce watchdog',
		'announce vpls',
		'announce route-refresh',
		'announce route',
		'announce operational',
		'announce flow',
		'announce eor',
		'announce attribute'
	],reverse=True)

	def __init__ (self):
		self.logger = Logger()
		self.parser = Parser.Text()

		try:
			for name in self.functions:
				self.callback['text'][name] = Command.Text.callback[name]
		except KeyError:
			raise RuntimeError('The code does not have an implementation for "%s", please code it !' % name)

	def text (self, reactor, service, command):
		for registered in self.functions:
			if registered in command:
				self.logger.reactor("callback | handling '%s' with %s" % (command,self.callback['text'][registered].func_name),'warning')
				self.callback['text'][registered](self,reactor,service,command)
				return True
		self.logger.reactor("Command from process not understood : %s" % command,'warning')
		return False
