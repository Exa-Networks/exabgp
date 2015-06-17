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

from exabgp.configuration.current.error import Error
from exabgp.configuration.current.scope import Scope
from exabgp.configuration.current.tokeniser import Tokeniser
from exabgp.configuration.current.generic import Generic
from exabgp.configuration.current.template import ParseTemplate
from exabgp.configuration.current.neighbor import ParseNeighbor
from exabgp.configuration.current.family import ParseFamily
from exabgp.configuration.current.capability import ParseCapability
from exabgp.configuration.current.static import ParseStatic
from exabgp.configuration.current.static import ParseRoute
from exabgp.configuration.current.l2vpn import ParseL2VPN
from exabgp.configuration.current.l2vpn import ParseVPLS
# from exabgp.configuration.current.process import ParseProcess
# from exabgp.configuration.current.flow import ParseFlow
# from exabgp.configuration.current.operational import ParseOperational

from exabgp.configuration.environment import environment


def false (*args):
	return False

def true (*args):
	return True


class Configuration (object):

	def __init__ (self, configurations, text=False):
		self.api_encoder = environment.settings().api.encoder

		self._configurations = configurations

		self.error  = Error  ()
		self.logger = Logger ()
		self.scope  = Scope  (self.error)

		self.tokeniser = Tokeniser(self.scope,self.error,self.logger)

		generic          = Generic          (self.tokeniser,self.scope,self.error,self.logger)
		self.template    = ParseTemplate    (self.tokeniser,self.scope,self.error,self.logger)
		self.neighbor    = ParseNeighbor    (self.tokeniser,self.scope,self.error,self.logger)
		self.family      = ParseFamily      (self.tokeniser,self.scope,self.error,self.logger)
		self.capability  = ParseCapability  (self.tokeniser,self.scope,self.error,self.logger)
		# self.process     = ParseProcess     (self.tokeniser,self.scope,self.error,self.logger)
		self.static      = ParseStatic      (self.tokeniser,self.scope,self.error,self.logger)
		self.route       = ParseRoute       (self.tokeniser,self.scope,self.error,self.logger)
		# self.flow        = ParseFlow        (self.tokeniser,self.scope,self.error,self.logger)
		self.l2vpn       = ParseL2VPN       (self.tokeniser,self.scope,self.error,self.logger)
		self.vpls        = ParseVPLS        (self.tokeniser,self.scope,self.error,self.logger)
		# self.operational = ParseOperational (self.tokeniser,self.scope,self.error,self.logger)

		# Later on we will use name such as 'neighbor/static' for keys which will give us depth of scope
		# But for the momment a flat tree is easier

		self._structure = {
			'root': {
				'class':    generic,
				'commands': [],
				'sections': [self.neighbor.name, self.template.name],
			},
			self.template.name: {
				'class':    self.template,
				'commands': self.template.known.keys(),
				'sections': [self.family.name, 'capability', self.static.name, 'flow', self.l2vpn.name, 'operational'],
			},
			self.neighbor.name: {
				'class':    self.neighbor,
				'commands': self.neighbor.known.keys(),
				'sections': [self.family.name, 'capability', self.static.name, 'flow', self.l2vpn.name, 'operational'],
			},
			self.family.name: {
				'class':    self.family,
				'commands': self.family.known.keys(),
				'sections': [],
			},
			self.capability.name: {
				'class':    self.capability,
				'commands': self.capability.known.keys(),
				'sections': [],
			},
			self.static.name: {
				'class':    self.static,
				'commands': [self.route.name],
				'sections': [self.route.name],
			},
			self.route.name: {
				'class':    self.route,
				'commands': self.static.known.keys(),  # is it right ?
				'sections': [],
			},
			self.l2vpn.name: {
				'class':    self.l2vpn,
				'commands': [self.vpls.name],
				'sections': [self.vpls.name],
			},
			self.vpls.name: {
				'class':    self.vpls,
				'commands': self.l2vpn.known.keys(),  # is it right ?
				'sections': [],
			},
		}

		self._clear()

		self.processes = {}

	def _clear (self):
		self.processes = {}

		self.error.clear()
		self.tokeniser.clear()
		self.scope.clear()
		self.neighbor.clear()
		self.family.clear()
		# self.process.clear()
		self.route.clear()
		# self.flow.clear()
		self.l2vpn.clear()
		self.vpls.clear()
		# self.operational.clear()

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
					'error message: %s' % (self.tokeniser.x, exc)
			)

	def _reload (self):
		# taking the first configuration available (FIFO buffer)
		fname = self._configurations.pop(0)
		# self.process.configuration(fname)
		self._configurations.append(fname)

		# clearing the current configuration to be able to re-parse it
		self._clear()

		if not self.tokeniser.set_file(fname):
			return False

		if self.section('root') is not True:
			# XXX: Should it be in neighbor ?
			self.neighbor.cancel()

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

		self.neighbor.complete()
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
				# Simplifying with a flat user space ( will need to become nested when more complex )
				if not self.section(location):
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

			return self.error.set('invalid syntax')
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





	# Programs used to control exabgp

	def _multi_process (self, name, command, tokens):
		while True:
			r = self._dispatch(
				name,'process',
				['send','receive'],
				[
					'run','encoder',
					'neighbor-changes',
				]
			)
			if r is False:
				return False
			if r is None:
				break

		name = tokens[0] if len(tokens) >= 1 else 'conf-only-%s' % str(time.time())[-6:]
		self.processes.setdefault(name,{})['neighbor'] = self.scope.content[-1]['peer-address'] if 'peer-address' in self.scope.content[-1] else '*'

		for key in ['neighbor-changes',]:
			self.processes[name][key] = self.scope.content[-1].pop(key,False)

		for direction in ['send','receive']:
			for action in ['packets','parsed','consolidate']:
				key = '%s-%s' % (direction,action)
				self.processes[name][key] = self.scope.content[-1].pop(key,False)

			for message in Message.CODE.MESSAGES:
				key = '%s-%d' % (direction,message)
				self.processes[name][key] = self.scope.content[-1].pop(key,False)

		run = self.scope.content[-1].pop('run','')
		if run:
			if len(tokens) != 1:
				return self.error.set(self.process.syntax)

			self.processes[name]['encoder'] = self.scope.content[-1].get('encoder','') or self.api_encoder
			self.processes[name]['run'] = run
			return True
		elif len(tokens):
			return self.error.set(self.process.syntax)

	# capacity

	def _multi_capability (self, name, command, tokens):
		# we know all the families we should use
		while True:
			r = self._dispatch(
				name,'capability',
				[],
				self._command['capability'].keys()
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	# route grouping with watchdog

	# Group Neighbor

	def _multi_group (self, name, command, address):
		# if len(tokens) != 2:
		# 	return self.error.set('syntax: group <name> { <options> }')

		self.scope.content.append({})
		while True:
			r = self._dispatch(
				name,'group',
				[
					'static','flow','l2vpn',
					'neighbor','process','family',
					'capability','operational'
				],
				self._command['neighbor'].keys()
			)
			if r is False:
				return False
			if r is None:
				self.scope.content.pop(-1)
				return True

	# def _multi_neighbor (self, name, command, tokens):
	# 	if len(tokens) != 1:
	# 		return self.error.set('syntax: neighbor <ip> { <options> }')
	#
	# 	address = tokens[0]
	# 	self.scope.content.append({})
	# 	try:
	# 		self.scope.content[-1]['peer-address'] = IP.create(address)
	# 	except (IndexError,ValueError,socket.error):
	# 		return self.error.set('"%s" is not a valid IP address' % address)
	#
	# 	while True:
	# 		r = self._dispatch(
	# 			name,'neighbor',
	# 			[
	# 				'static','flow','l2vpn',
	# 				'process','family','capability','operational'
	# 			],
	# 			self._command['neighbor']
	# 		)
	# 		# XXX: THIS SHOULD ALLOW CAPABILITY AND NOT THE INDIVIDUAL SUB KEYS
	# 		if r is False:
	# 			return False
	# 		if r is None:
	# 			return True

	#  Group Static ................

	def _multi_static (self, name, command, tokens):
		if len(tokens) != 0:
			return self.error.set('syntax: static { route; route; ... }')

		while True:
			r = self._dispatch(
				name,'static',
				['route',],
				['route',]
			)
			if r is False:
				return False
			if r is None:
				return True

	# Group Route  ........

	def _multi_static_route (self, name, command, tokens):
		if len(tokens) != 1:
			return self.error.set(self.route.syntax)

		if not self.route.insert_static_route(name,command,tokens):
			return False

		while True:
			r = self._dispatch(
				name,'static-route',
				self._command['static-route'].keys(),
				self._command['static-route'].keys()
			)
			if r is False:
				return False
			if r is None:
				return self.route.make_split()

	def _multi_l2vpn (self, name, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.l2vpn.syntax)

		while True:
			r = self._dispatch(
				name,'l2vpn',
				['vpls',],
				['vpls',]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _multi_l2vpn_vpls (self, name, command, tokens):
		if len(tokens) > 1:
			return self.error.set(self.l2vpn.syntax)

		if not self.l2vpn.insert_vpls(name,command,tokens):
			return False

		while True:
			r = self._dispatch(
				name,'l2vpn-vpls',
				self._command['l2vpn-vpls'].keys(),
				self._command['l2vpn-vpls'].keys()
			)
			if r is False:
				return False
			if r is None:
				break

		return True


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



		# self._tree = {
		# 	'configuration': {
		# 		'neighbor':    self.neighbor
		# 		'group':       (self._multi_group,true),
		# 	},
		# 	'group': {
		# 		'neighbor':    (self._multi_neighbor,self.neighbor.make),
		# 		'static':      (self._multi_static,true),
		# 		'flow':        (self._multi_flow,true),
		# 		'l2vpn':       (self._multi_l2vpn,true),
		# 		'process':     (self._multi_process,true),
		# 		'family':      (self._multi_family,true),
		# 		'capability':  (self._multi_capability,true),
		# 		'operational': (self._multi_operational,true),
		# 	},
		# 	'neighbor': {
		# 		'static':      (self._multi_static,true),
		# 		'flow':        (self._multi_flow,true),
		# 		'l2vpn':       (self._multi_l2vpn,true),
		# 		'process':     (self._multi_process,true),
		# 		'family':      (self._multi_family,true),
		# 		'capability':  (self._multi_capability,true),
		# 		'operational': (self._multi_operational,true),
		# 	},
		# 	'static': {
		# 		'route':       (self._multi_static_route,self.route.check_static_route),
		# 	},
		# 	'flow': {
		# 		'route':       (self._multi_flow_route,self.flow.check_flow),
		# 	},
		# 	'l2vpn': {
		# 		'vpls':       (self._multi_l2vpn_vpls,self.l2vpn.check_vpls),
		# 	},
		# 	'flow-route': {
		# 		'match':       (self._multi_match,true),
		# 		'then':        (self._multi_then,true),
		# 	},
		# 	'process': {
		# 		'send':    (self._multi_api,true),
		# 		'receive': (self._multi_api,true),
		# 	}
		# }
		#
		# self._command = {
		# 	'group': {
		# 		'description':   self.neighbor.description,
		# 		'router-id':     self.neighbor.router_id,
		# 		'host-name':     self.neighbor.hostname,
		# 		'domain-name':   self.neighbor.domainname,
		# 		'local-address': self.neighbor.ip,
		# 		'local-as':      self.neighbor.asn,
		# 		'peer-as':       self.neighbor.asn,
		# 		'passive':       self.neighbor.passive,
		# 		'listen':        self.neighbor.listen,
		# 		'hold-time':     self.neighbor.holdtime,
		# 		'md5':           self.neighbor.md5,
		# 		'ttl-security':  self.neighbor.ttl,
		# 		'group-updates': self.neighbor.groupupdate,
		# 		'adj-rib-out':   self.neighbor.adjribout,
		# 		'auto-flush':    self.neighbor.autoflush,
		# 	},
		# 	'neighbor': {
		# 		'description':   self.neighbor.description,
		# 		'router-id':     self.neighbor.router_id,
		# 		'host-name':     self.neighbor.hostname,
		# 		'domain-name':   self.neighbor.domainname,
		# 		'local-address': self.neighbor.ip,
		# 		'local-as':      self.neighbor.asn,
		# 		'peer-as':       self.neighbor.asn,
		# 		'passive':       self.neighbor.passive,
		# 		'listen':        self.neighbor.listen,
		# 		'hold-time':     self.neighbor.holdtime,
		# 		'md5':           self.neighbor.md5,
		# 		'ttl-security':  self.neighbor.ttl,
		# 		'group-updates': self.neighbor.groupupdate,
		# 		'adj-rib-out':   self.neighbor.adjribout,
		# 		'auto-flush':    self.neighbor.autoflush,
		# 	},
		# 	'capability': {
		# 		'route-refresh':    self.neighbor.capability.refresh,
		# 		'graceful-restart': self.neighbor.capability.gracefulrestart,
		# 		'multi-session':    self.neighbor.capability.multisession,
		# 		'add-path':         self.neighbor.capability.addpath,
		# 		'aigp':             self.neighbor.capability.aigp,
		# 		'operational':      self.neighbor.capability.operational,
		# 		'add-path':         self.neighbor.capability.addpath,
		# 		'asn4':             self.neighbor.capability.asn4,
		# 	},
		# 	'process': {
		# 		'run':              self.process.run,
		# 		'encoder':          self.process.encoder,
		# 		'neighbor-changes': self.process.command,
		# 	},
		# 	'family': {
		# 		'ipv4':    self.family.ipv4,
		# 		'ipv6':    self.family.ipv6,
		# 		'l2vpn':   self.family.l2vpn,
		# 		'minimal': self.family.minimal,
		# 		'all':     self.family.all,
		# 	},
		# 	'static': {
		# 		'route':   self.route.static,
		# 	},
		# 	'l2vpn': {
		# 		'vpls':    self.l2vpn.vpls,
		# 	},
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
