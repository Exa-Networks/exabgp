# encoding: utf-8
"""
current.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import sys

from exabgp.logger import Logger

from exabgp.configuration.current.core import Error
from exabgp.configuration.current.core import Scope
from exabgp.configuration.current.core import Tokeniser
from exabgp.configuration.current.core import Section
from exabgp.configuration.current.core import SectionError

from exabgp.configuration.current.process import ParseProcess
from exabgp.configuration.current.template import ParseTemplate
from exabgp.configuration.current.neighbor import ParseNeighbor
from exabgp.configuration.current.neighbor.api import ParseAPI
from exabgp.configuration.current.neighbor.api import ParseSend
from exabgp.configuration.current.neighbor.api import ParseReceive
from exabgp.configuration.current.family import ParseFamily
from exabgp.configuration.current.capability import ParseCapability
from exabgp.configuration.current.static import ParseStatic
from exabgp.configuration.current.static import ParseStaticRoute
from exabgp.configuration.current.flow import ParseFlow
from exabgp.configuration.current.flow import ParseFlowRoute
from exabgp.configuration.current.flow import ParseFlowThen
from exabgp.configuration.current.flow import ParseFlowMatch
from exabgp.configuration.current.l2vpn import ParseL2VPN
from exabgp.configuration.current.l2vpn import ParseVPLS
from exabgp.configuration.current.operational import ParseOperational

from exabgp.bgp.message import Message
from exabgp.configuration.environment import environment


class Configuration (object):

	def __init__ (self, configurations):
		self.api_encoder = environment.settings().api.encoder

		self._configurations = configurations

		self.error  = Error  ()
		self.logger = Logger ()
		self.scope  = Scope  (self.error)

		self.tokeniser = Tokeniser(self.scope,self.error,self.logger)

		generic           = Section          (self.tokeniser,self.scope,self.error,self.logger)
		self.process      = ParseProcess     (self.tokeniser,self.scope,self.error,self.logger)
		self.template     = ParseTemplate    (self.tokeniser,self.scope,self.error,self.logger)
		self.neighbor     = ParseNeighbor    (self.tokeniser,self.scope,self.error,self.logger)
		self.family       = ParseFamily      (self.tokeniser,self.scope,self.error,self.logger)
		self.capability   = ParseCapability  (self.tokeniser,self.scope,self.error,self.logger)
		self.api          = ParseAPI         (self.tokeniser,self.scope,self.error,self.logger)
		self.api_send     = ParseSend        (self.tokeniser,self.scope,self.error,self.logger)
		self.api_receive  = ParseReceive     (self.tokeniser,self.scope,self.error,self.logger)
		self.static       = ParseStatic      (self.tokeniser,self.scope,self.error,self.logger)
		self.static_route = ParseStaticRoute (self.tokeniser,self.scope,self.error,self.logger)
		self.flow         = ParseFlow        (self.tokeniser,self.scope,self.error,self.logger)
		self.flow_route   = ParseFlowRoute   (self.tokeniser,self.scope,self.error,self.logger)
		self.flow_match   = ParseFlowMatch   (self.tokeniser,self.scope,self.error,self.logger)
		self.flow_then    = ParseFlowThen    (self.tokeniser,self.scope,self.error,self.logger)
		self.l2vpn        = ParseL2VPN       (self.tokeniser,self.scope,self.error,self.logger)
		self.vpls         = ParseVPLS        (self.tokeniser,self.scope,self.error,self.logger)
		self.operational  = ParseOperational (self.tokeniser,self.scope,self.error,self.logger)

		# We should check if name are unique when running Section.__init__

		self._structure = {
			'root': {
				'class':    generic,
				'commands': [],
				'sections': {
					'process': self.process.name,
					'neighbor': self.neighbor.name,
					'template': self.template.name,
				},
			},
			self.process.name: {
				'class':    self.process,
				'commands': self.process.known.keys(),
				'sections': {},
			},
			self.template.name: {
				'class':    self.template,
				'commands': self.template.known.keys(),
				'sections': {
					'family':      self.family.name,
					'capability':  self.capability.name,
					'api':         self.api.name,
					'static':      self.static.name,
					'flow':        self.flow.name,
					'l2vpn':       self.l2vpn.name,
					'operational': self.operational.name,
				},
			},
			self.neighbor.name: {
				'class':    self.neighbor,
				'commands': self.neighbor.known.keys(),
				'sections': {
					'family':      self.family.name,
					'capability':  self.capability.name,
					'api':         self.api.name,
					'static':      self.static.name,
					'flow':        self.flow.name,
					'l2vpn':       self.l2vpn.name,
					'operational': self.operational.name,
				},
			},
			self.family.name: {
				'class':    self.family,
				'commands': self.family.known.keys(),
				'sections': {
				},
			},
			self.capability.name: {
				'class':    self.capability,
				'commands': self.capability.known.keys(),
				'sections': {
				},
			},
			self.api.name: {
				'class':    self.api,
				'commands': self.api.known.keys(),
				'sections': {
					'send':    self.api_send.name,
					'receive': self.api_receive.name,
				},
			},
			self.api_send.name: {
				'class':    self.api_send,
				'commands': self.api_send.known.keys(),
				'sections': {
				},
			},
			self.api_receive.name: {
				'class':    self.api_receive,
				'commands': self.api_receive.known.keys(),
				'sections': {
				},
			},
			self.static.name: {
				'class':    self.static,
				'commands': 'route',
				'sections': {
					'route': self.static_route.name,
				},
			},
			self.static_route.name: {
				'class':    self.static_route,
				'commands': self.static_route.known.keys(),
				'sections': {
				},
			},
			self.flow.name: {
				'class':    self.flow,
				'commands': [],
				'sections': {
					'route': self.flow_route.name,
				},
			},
			self.flow_route.name: {
				'class':    self.flow_route,
				'commands': self.flow_route.known.keys(),
				'sections': {
					'match': self.flow_match.name,
					'then':  self.flow_then.name,
				},
			},
			self.flow_match.name: {
				'class':    self.flow_match,
				'commands': self.flow_match.known.keys(),
				'sections': {
				},
			},
			self.flow_then.name: {
				'class':    self.flow_then,
				'commands': self.flow_then.known.keys(),
				'sections': {
				},
			},
			self.l2vpn.name: {
				'class':    self.l2vpn,
				'commands': self.l2vpn.known.keys(),
				'sections': {
					'vpls': self.vpls.name,
				},
			},
			self.vpls.name: {
				'class':    self.vpls,
				'commands': self.l2vpn.known.keys(),
				'sections': {
				},
			},
			self.operational.name: {
				'class':    self.operational,
				'commands': self.operational.known.keys(),
				'sections': {
				}
			},
		}

		self.processes = {}
		self.neighbors = {}
		self._neighbors = {}
		self._previous_neighbors = {}

		self._clear()

	# remove the parse data
	def _clear (self):
		self.processes = {}
		self.neighbors = {}
		self.neighbors = {}
		self._neighbors = {}
		self._previous_neighbors = {}

	# clear the parser data (ie: free memory)
	def _cleanup (self):
		self.error.clear()
		self.tokeniser.clear()
		self.scope.clear()

		self.process.clear()
		self.template.clear()
		self.neighbor.clear()
		self.family.clear()
		self.capability.clear()
		self.api.clear()
		self.api_send.clear()
		self.api_receive.clear()
		self.static.clear()
		self.static_route.clear()
		self.flow.clear()
		self.flow_route.clear()
		self.flow_match.clear()
		self.flow_then.clear()
		self.l2vpn.clear()
		self.vpls.clear()
		self.operational.clear()

	def _rollback_reload (self):
		self.neighbors = self._previous_neighbors
		self._neighbors = {}
		self._previous_neighbors = {}

	def _commit_reload (self):
		self.neighbors = self.neighbor.neighbors
		# XXX: Yes, we do not detect changes in processes and restart anything ..
		# XXX: This is a bug ..
		self.processes = self.process.processes
		self._neighbors = {}

		# installing in the neighbor the API routes
		for neighbor in self.neighbors:
			if neighbor in self._previous_neighbors:
				self.neighbors[neighbor].changes = self._previous_neighbors[neighbor].changes

		self._previous_neighbors = {}
		self._cleanup()

	def reload (self):
		try:
			return self._reload()
		except KeyboardInterrupt:
			return self.error.set('configuration reload aborted by ^C or SIGINT')
		except SectionError, exc:
			return self.error.set(
				'problem parsing configuration file line %d\n'
				'error message: %s' % (self.tokeniser.index_line, exc)
			)
		except Exception, exc:
			if environment.settings().debug.configuration:
				raise
			return self.error.set(
				'problem parsing configuration file line %d\n'
				'error message: %s' % (self.tokeniser.index_line, exc)
			)

	def _reload (self):
		# taking the first configuration available (FIFO buffer)
		fname = self._configurations.pop(0)
		self._configurations.append(fname)

		# clearing the current configuration to be able to re-parse it
		self._clear()

		if not self.tokeniser.set_file(fname):
			return False

		if self.section('root') is not True:
			# XXX: Should it be in neighbor ?
			self._rollback_reload()

			return self.error.set(
				"\n"
				"syntax error in section %s\n"
				"line %d: %s\n"
				"\n%s" % (
					self.scope.location(),
					self.tokeniser.number,
					' '.join(self.tokeniser.line),
					str(self.error)
				)
			)

		self._commit_reload()
		self._link()
		self.debug_check_route()
		self.debug_self_check()
		return True

	def _link (self):
		for neighbor in self.neighbors.itervalues():
			api = neighbor.api
			for process in api.get('processes',[]):
				self.processes.setdefault(process,{})['neighbor-changes'] = api['neighbor-changes']
				for way in ('send','receive'):
					for name in ('parsed','packets','consolidate'):
						key = "%s-%s" % (way,name)
						if api[key]:
							self.processes[process].setdefault(key,[]).append(neighbor.router_id)
					for name in ('open', 'update', 'notification', 'keepalive', 'refresh', 'operational'):
						key = "%s-%d" % (way,Message.code(name))
						if api[key]:
							self.processes[process].setdefault(key,[]).append(neighbor.router_id)

	def partial (self, section, text):
		self._cleanup()  # this perform a big cleanup (may be able to be smarter)
		self._clear()
		self.tokeniser.set_api(text if text.endswith(';') else text + ' ;')

		if self.section(section) is not True:
			self._rollback_reload()
			self.logger.configuration(
				"\n"
				"syntax error in api command %s\n"
				"line %d: %s\n"
				"\n%s" % (
					self.scope.location(),
					self.tokeniser.number,
					' '.join(self.tokeniser.line),
					str(self.error)
				)
			)
			return False
		return True

	def dispatch (self,name):
		if False:
			# self.flow.clear()
			pass

		while True:
			self.tokeniser()

			if self.tokeniser.end == ';':
				command = self.tokeniser.iterate()
				self.logger.configuration(". %-16s | %s" % (command,self.tokeniser.params()))

				if not self.run(name,command):
					return False
				continue

			if self.tokeniser.end == '{':
				location = self.tokeniser.iterate()
				self.logger.configuration("> %-16s | %s" % (location,self.tokeniser.params()))

				if location not in self._structure[name]['sections']:
					return self.error.set('section %s is invalid in %s, %s' % (location,name,self.scope.location()))

				self.scope.enter(location)
				if not self.section(self._structure[name]['sections'][location]):
					return False
				continue

			if self.tokeniser.end == '}':
				left = self.scope.leave()
				self.logger.configuration("< %-16s | %s" % (left,self.tokeniser.params()))

				if not left:
					return self.error.set('closing too many parenthesis')
				return True

			if not self.tokeniser.end:  # finished
				return True

			return self.error.set('invalid syntax line %d' % self.tokeniser.index_line)
		return False

	def section (self, name):
		if name not in self._structure:
			return self.error.set('option %s is not allowed here' % name)

		instance = self._structure[name].get('class',None)

		if not instance:
			raise RuntimeError('This should not be happening, debug time !')

		return instance.pre() \
			and self.dispatch(name) \
			and instance.post()

	def run (self, name, command):
		if command not in self._structure[name]['commands']:
			return self.error.set('invalid keyword "%s"' % command)

		return self._structure[name]['class'].parse(name,command)

	def debug_check_route (self):
		# we are not really running the program, just want to ....
		if environment.settings().debug.route:
			from exabgp.configuration.current.check import check_message
			if check_message(self.neighbors,environment.settings().debug.route):
				sys.exit(0)
			sys.exit(1)

	def debug_self_check (self):
		# we are not really running the program, just want check the configuration validity
		if environment.settings().debug.selfcheck:
			from exabgp.configuration.current.check import check_neighbor
			if check_neighbor(self.neighbors):
				sys.exit(0)
			sys.exit(1)
