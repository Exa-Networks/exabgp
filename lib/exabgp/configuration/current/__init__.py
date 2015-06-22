# encoding: utf-8
"""
current.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import sys
import time

from exabgp.configuration.environment import environment

from exabgp.bgp.message import Message

from exabgp.bgp.message.update.nlri.flow import Flow

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities

from exabgp.rib.change import Change

from exabgp.logger import Logger

from exabgp.configuration.current.core import Error
from exabgp.configuration.current.core import Scope
from exabgp.configuration.current.core import Tokeniser
from exabgp.configuration.current.core import Section

from exabgp.configuration.current.process import ParseProcess
from exabgp.configuration.current.template import ParseTemplate
from exabgp.configuration.current.neighbor import ParseNeighbor
from exabgp.configuration.current.neighbor.api import ParseAPI
from exabgp.configuration.current.neighbor.api import ParseSend
from exabgp.configuration.current.neighbor.api import ParseReceive
from exabgp.configuration.current.family import ParseFamily
from exabgp.configuration.current.capability import ParseCapability
from exabgp.configuration.current.static import ParseStatic
from exabgp.configuration.current.static import ParseRoute
from exabgp.configuration.current.flow import ParseFlow
from exabgp.configuration.current.flow import ParseFlowThen
from exabgp.configuration.current.flow import ParseFlowMatch
from exabgp.configuration.current.l2vpn import ParseL2VPN
from exabgp.configuration.current.l2vpn import ParseVPLS
# from exabgp.configuration.current.flow import ParseFlow
# from exabgp.configuration.current.operational import ParseOperational

from exabgp.configuration.environment import environment


class Configuration (object):

	def __init__ (self, configurations):
		self.api_encoder = environment.settings().api.encoder

		self._configurations = configurations

		self.error  = Error  ()
		self.logger = Logger ()
		self.scope  = Scope  (self.error)

		self.tokeniser = Tokeniser(self.scope,self.error,self.logger)

		generic          = Section          (self.tokeniser,self.scope,self.error,self.logger)
		self.process     = ParseProcess     (self.tokeniser,self.scope,self.error,self.logger)
		self.template    = ParseTemplate    (self.tokeniser,self.scope,self.error,self.logger)
		self.neighbor    = ParseNeighbor    (self.tokeniser,self.scope,self.error,self.logger)
		self.family      = ParseFamily      (self.tokeniser,self.scope,self.error,self.logger)
		self.capability  = ParseCapability  (self.tokeniser,self.scope,self.error,self.logger)
		self.api         = ParseAPI         (self.tokeniser,self.scope,self.error,self.logger)
		self.api_send    = ParseSend        (self.tokeniser,self.scope,self.error,self.logger)
		self.api_receive = ParseReceive     (self.tokeniser,self.scope,self.error,self.logger)
		self.static      = ParseStatic      (self.tokeniser,self.scope,self.error,self.logger)
		self.route       = ParseRoute       (self.tokeniser,self.scope,self.error,self.logger)
		self.flow        = ParseFlow        (self.tokeniser,self.scope,self.error,self.logger)
		self.flow_match  = ParseFlowMatch   (self.tokeniser,self.scope,self.error,self.logger)
		self.flow_then   = ParseFlowThen    (self.tokeniser,self.scope,self.error,self.logger)
		self.l2vpn       = ParseL2VPN       (self.tokeniser,self.scope,self.error,self.logger)
		self.vpls        = ParseVPLS        (self.tokeniser,self.scope,self.error,self.logger)
		# self.flow        = ParseFlow        (self.tokeniser,self.scope,self.error,self.logger)
		# self.operational = ParseOperational (self.tokeniser,self.scope,self.error,self.logger)

		# Later on we will use name such as 'neighbor/static' for keys which will give us depth of scope
		# But for the momment a flat tree is easier

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
					'flow':        'flow',
					'l2vpn':       self.l2vpn.name,
					'operational': 'operational',
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
					'operational': 'operational',
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
					'route': self.route.name,
				},
			},
			self.route.name: {
				'class':    self.route,
				'commands': self.static.known.keys(),  # is it right ?
				'sections': {
				},
			},
			self.flow.name: {
				'class':    self.l2vpn,
				'commands': [],
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
				'commands': [self.vpls.name],
				'sections': {
					'vpls': self.vpls.name,
				},
			},
			self.vpls.name: {
				'class':    self.vpls,
				'commands': self.l2vpn.known.keys(),  # is it right ?
				'sections': {
				},
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
		self.static.clear()
		self.route.clear()
		self.l2vpn.clear()
		self.vpls.clear()
		# self.flow.clear()
		# self.operational.clear()

	def _rollback_reload (self):
		self.neighbors = self._previous_neighbors
		self._neighbors = {}
		self._previous_neighbors = {}

	def _commit_reload (self):
		self.neighbors = self.neighbor.neighbors
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
		self.debug_check_route()
		self.debug_self_check()
		return True

	def dispatch (self,name):
		if False:
			# self.flow.clear()
			pass

		while True:
			self.tokeniser()

			if self.tokeniser.end == ';':
				command = self.tokeniser.iterate()
				self.logger.configuration(". %-16s | '%s'" % (command,"' '".join(self.tokeniser.line)))

				if not self.run(name,command):
					return False
				continue

			if self.tokeniser.end == '{':
				location = self.tokeniser.iterate()
				self.logger.configuration("> %-16s | '%s'" % (location,"' '".join(self.tokeniser.line)))

				if location not in self._structure[name]['sections']:
					return self.error.set('section %s is invalid in %s, %s' % (location,name,self.scope.location()))

				self.scope.enter(location)
				if not self.section(self._structure[name]['sections'][location]):
					return False
				continue

			if self.tokeniser.end == '}':
				left = self.scope.leave()
				self.logger.configuration("< %-16s | '%s'" % (left,"' '".join(self.tokeniser.line)))

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
			if check_message(self.neighbor.neighbors,environment.settings().debug.route):
				sys.exit(0)
			sys.exit(1)

	def debug_self_check (self):
		# we are not really running the program, just want check the configuration validity
		if environment.settings().debug.selfcheck:
			from exabgp.configuration.current.check import check_neighbor
			if check_neighbor(self.neighbor.neighbors):
				sys.exit(0)
			sys.exit(1)


	def _multi_flow (self, name, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.flow.syntax)

		while True:
			r = self._dispatch(
				name,'flow',
				['route',],
				[]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _insert_flow_route (self, name, command, tokens=None):
		if self.flow.state != 'out':
			return self.error.set(self.flow.syntax)

		self.flow.state = 'match'

		try:
			attributes = Attributes()
			attributes[Attribute.CODE.EXTENDED_COMMUNITY] = ExtendedCommunities()
			flow = Change(Flow(),attributes)
		except ValueError:
			return self.error.set(self.flow.syntax)

		if 'announce' not in self.scope.content[-1]:
			self.scope.content[-1]['announce'] = []

		self.scope.content[-1]['announce'].append(flow)
		return True

	def _multi_flow_route (self, name, command, tokens):
		if len(tokens) > 1:
			return self.error.set(self.flow.syntax)

		if not self._insert_flow_route(name,command):
			return False

		while True:
			r = self._dispatch(
				name,'flow-route',
				['match','then'],
				['rd','route-distinguisher','next-hop']
			)
			if r is False:
				return False
			if r is None:
				break

		if self.flow.state != 'out':
			return self.error.set(self.flow.syntax)

		return True

	# ..........................................

	def _multi_match (self, name, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.flow.syntax)

		if self.flow.state != 'match':
			return self.error.set(self.flow.syntax)

		self.flow.state = 'then'

		while True:
			r = self._dispatch(
				name,'flow-match',
				[],
				[
					'source','destination',
					'source-ipv4','destination-ipv4',
					'port','source-port','destination-port',
					'protocol','next-header','tcp-flags','icmp-type','icmp-code',
					'fragment','dscp','traffic-class','packet-length','flow-label'
				]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _multi_then (self, name, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.flow.syntax)

		if self.flow.state != 'then':
			return self.error.set(self.flow.syntax)

		self.flow.state = 'out'

		while True:
			r = self._dispatch(
				name,'flow-then',
				[],
				[
					'accept','discard','rate-limit',
					'redirect','copy','redirect-to-nexthop',
					'mark','action',
					'community','extended-community'
				]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	# ..........................................

	def _multi_api (self, name, command, tokens):
		if len(tokens) != 0:
			return self.error.set('api issue')

		while True:
			r = self._dispatch(
				name,command,
				[],
				self._command[command].keys()
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	#  Group Operational ................

	def _multi_operational (self, name, command, tokens):
		if len(tokens) != 0:
			return self.error.set('syntax: operational { command; command; ... }')

		while True:
			r = self._dispatch(
				name,command,
				[],
				self._command[command].keys()
			)
			if r is False:
				return False
			if r is None:
				return True


		# 	'operational': {
		# 		'asm':     self.operational.asm,
		# 		# it makes no sense to have adm or others
		# 	},
		# 	'static-route': self.route.command,
		# 	# 'inet-route': {
		# 	# 'mpls-route': {
		# 	'l2vpn-vpls':   self.l2vpn.command,
		# 	'flow-route': {
		# 		'rd':                  self.route.rd,
		# 		'route-distinguisher': self.route.rd,
		# 		'next-hop':            self.flow.next_hop,
		# 	},
		# 	'flow-match': {
		# 		'source':              self.flow.source,
		# 		'source-ipv4':         self.flow.source,
		# 		'destination':         self.flow.destination,
		# 		'destination-ipv4':    self.flow.destination,
		# 		'port':                self.flow.anyport,
		# 		'source-port':         self.flow.source_port,
		# 		'destination-port':    self.flow.destination_port,
		# 		'protocol':            self.flow.protocol,
		# 		'next-header':         self.flow.next_header,
		# 		'tcp-flags':           self.flow.tcp_flags,
		# 		'icmp-type':           self.flow.icmp_type,
		# 		'icmp-code':           self.flow.icmp_code,
		# 		'fragment':            self.flow.fragment,
		# 		'dscp':                self.flow.dscp,
		# 		'traffic-class':       self.flow.traffic_class,
		# 		'packet-length':       self.flow.packet_length,
		# 		'flow-label':          self.flow.flow_label,
		# 	},
		# 	'flow-then': {
		# 		'accept':              self.flow.accept,
		# 		'discard':             self.flow.discard,
		# 		'rate-limit':          self.flow.rate_limit,
		# 		'redirect':            self.flow.redirect,
		# 		'redirect-to-nexthop': self.flow.redirect_next_hop,
		# 		'copy':                self.flow.copy,
		# 		'mark':                self.flow.mark,
		# 		'action':              self.flow.action,
		# 		'community':           self.route.community,
		# 		'extended-community':  self.route.extended_community,
		# 	},
		# 	'send': {
		# 		'parsed':              self.process.command,
		# 		'packets':             self.process.command,
		# 		'consolidate':         self.process.command,
		# 		'open':                self.process.command,
		# 		'update':              self.process.command,
		# 		'notification':        self.process.command,
		# 		'keepalive':           self.process.command,
		# 		'refresh':             self.process.command,
		# 		'operational':         self.process.command,
		# 	},
		# 	'receive': {
		# 		'parsed':              self.process.command,
		# 		'packets':             self.process.command,
		# 		'consolidate':         self.process.command,
		# 		'open':                self.process.command,
		# 		'update':              self.process.command,
		# 		'notification':        self.process.command,
		# 		'keepalive':           self.process.command,
		# 		'refresh':             self.process.command,
		# 		'operational':         self.process.command,
		# 	},
		# }
