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

class API (object):
	callback = {
		'text': {},
		'json': {},
	}

	# need to sort and reverse, in order for the shorter command to not used by error
	# "show neighbor" should not match "show neighbors"
	functions = sorted([
		'show neighbor',
		'show neighbors',
		'show routes',
		'show routes extensive',
		'announce operational',
		'announce attributes',
		'announce eor',
		'announce flow',
		'announce route',
		'announce route-refresh',
		'announce vpls',
		'announce watchdog',
		'withdraw attributes',
		'withdraw flow',
		'withdraw route',
		'withdraw vpls',
		'withdraw watchdog',
		'flush route',
		'teardown',
		'version',
		'restart',
		'reload',
		'shutdown',
		'#',
	],reverse=True)

	def __init__ (self,reactor):
		self.reactor = reactor
		self.logger = Logger()
		self.parser = Parser.Text(reactor)

		try:
			for name in self.functions:
				self.callback['text'][name] = Command.Text.callback[name]
		except KeyError:
			raise RuntimeError('The code does not have an implementation for "%s", please code it !' % name)

	def log_message (self, message, level='info'):
		self.logger.reactor(message,level)

	def log_failure (self, message, level='error'):
		error = str(self.parser.configuration.tokeniser.error)
		report = '%s\nreason: %s' % (message, error) if error else message
		self.logger.reactor(report,level)

	def text (self, reactor, service, command):
		for registered in self.functions:
			if registered in command:
				self.logger.reactor("callback | handling '%s' with %s" % (command,self.callback['text'][registered].func_name),'warning')
				# XXX: should we not test the return value ?
				self.callback['text'][registered](self,reactor,service,command)
				# reactor.plan(self.callback['text'][registered](self,reactor,service,command),registered)
				return True
		self.logger.reactor("Command from process not understood : %s" % command,'warning')
		return False

	def shutdown (self):
		self.reactor.api_shutdown()
		return True

	def reload (self):
		self.reactor.api_reload()
		return True

	def restart (self):
		self.reactor.api_restart()
		return True
