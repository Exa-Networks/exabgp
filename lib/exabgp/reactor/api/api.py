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
		'announce flow',
		'announce eor',
		'announce attribute',
		'announce operational',
	],reverse=True)

	def __init__ (self,reactor):
		self.reactor = reactor
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
				# XXX: should we not test the return value ?
				self.callback['text'][registered](self,reactor,service,command)
				return True
		self.logger.reactor("Command from process not understood : %s" % command,'warning')
		return False

	def change_to_peers (self, change, peers):
		neighbors = self.reactor.configuration.neighbors
		result = True
		for neighbor in neighbors:
			if neighbor in peers:
				if change.nlri.family() in neighbors[neighbor].families():
					neighbors[neighbor].rib.outgoing.insert_announced(change)
				else:
					self.logger.configuration('the route family is not configured on neighbor','error')
					result = False
		return result

	def eor_to_peers (self, family, peers):
		neighbors = self.reactor.configuration.neighbors
		result = False
		for neighbor in neighbors:
			if neighbor in peers:
				result = True
				neighbors[neighbor].eor.append(family)
		return result

	def operational_to_peers (self, operational, peers):
		neighbors = self.reactor.configuration.neighbors
		result = True
		for neighbor in neighbors:
			if neighbor in peers:
				if operational.family() in neighbors[neighbor].families():
					if operational.name == 'ASM':
						neighbors[neighbor].asm[operational.family()] = operational
					neighbors[neighbor].messages.append(operational)
				else:
					self.logger.configuration('the route family is not configured on neighbor','error')
					result = False
		return result

	def refresh_to_peers (self, refresh, peers):
		neighbors = self.reactor.configuration.neighbors
		result = True
		for neighbor in neighbors:
			if neighbor in peers:
				family = (refresh.afi,refresh.safi)
				if family in neighbors[neighbor].families():
					neighbors[neighbor].refresh.append(refresh.__class__(refresh.afi,refresh.safi))
				else:
					result = False
		return result

	def shutdown (self):
		self.reactor.api_shutdown()
		return True

	def reload (self):
		self.reactor.api_reload()
		return True

	def restart (self):
		self.reactor.api_restart()
		return True
