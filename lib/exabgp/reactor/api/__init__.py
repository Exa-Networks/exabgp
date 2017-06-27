# encoding: utf-8
"""
decoder/__init__.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.logger import Logger
from exabgp.reactor.api.command import Command

# ======================================================================= Parser
#


class API (Command):
	def __init__ (self, reactor, configuration):
		self.reactor = reactor
		self.logger = Logger()
		self.configuration = configuration

	def log_message (self, message, level='info'):
		self.logger.reactor(message,level)

	def log_failure (self, message, level='error'):
		error = str(self.configuration.tokeniser.error)
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
