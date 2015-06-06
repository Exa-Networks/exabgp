# encoding: utf-8
"""
current.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import sys
import pdb
import time
import socket

from exabgp.util.ip import isipv4

from exabgp.configuration.environment import environment
from exabgp.configuration.current.format import formated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.protocol.ip import IP

from exabgp.bgp.message import OUT
from exabgp.bgp.message import Message

from exabgp.bgp.message.open.routerid import RouterID

from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import MPLS
from exabgp.bgp.message.update.nlri import VPLS
# from exabgp.bgp.message.update.nlri import EVPN
# from exabgp.bgp.message.update.nlri.flow import NLRI
from exabgp.bgp.message.update.nlri.flow import Flow

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities

from exabgp.bgp.message.operational import MAX_ADVISORY
from exabgp.bgp.message.operational import Advisory

from exabgp.rib.change import Change

from exabgp.logger import Logger

from exabgp.configuration.current.error import Error
from exabgp.configuration.current.tokeniser import Tokeniser
from exabgp.configuration.current.neighbor import ParseNeighbor
from exabgp.configuration.current.family import ParseFamily
from exabgp.configuration.current.route import ParseRoute
from exabgp.configuration.current.flow import ParseFlow
from exabgp.configuration.current.l2vpn import ParseL2VPN
from exabgp.configuration.current.process import ParseProcess


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi, integer, mask):
	return ''.join([chr((integer >> (offset * 8)) & 0xff) for offset in range(IP.length(afi)-1,-1,-1)])


def false (*args):
	return False

def true (*args):
	return True

# self._tree = {
# 	'neighbor': {
# 		'section':    ['static','flow','l2vpn','process','family','capability','operational'],
# 		'command':    'neighbor',
# 		'parameter':  self._parameter_neighbor,
# 		'validation': self._make_neighbor,
# 	},
# 	'group': {
# 		'section':    ['neighbor','static','flow','l2vpn','process','family','capability','operational'],
# 		'command':    '',
# 		'parameter':  true,
# 		'validation': true,
# 	},
# 	'static': {
# 		'section':     ['static-route'],
# 		'command':     'static',
# 		'parameter':   true,
# 		'validation':  true,
# 	},
# 	'static-route': {
# 		'section':     [],
# 		'command':     'static',
# 		'parameter':   true,
# 		'validation':  self.route.check_static_route,
# 	},
# 	'flow': {
# 		'route':       (self._multi_flow_route,self._check_flow_route),
# 	},
# 	'l2vpn': {
# 		'vpls':       (self._multi_l2vpn_vpls,self._check_l2vpn_vpls),
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


class Configuration (object):
	def __init__ (self, configurations, text=False):
		self.api_encoder = environment.settings().api.encoder

		self.logger = Logger()
		self._configurations = configurations

		self.error = Error()
		self.tokens = Tokeniser(self.error,self.logger)
		self.neighbor = ParseNeighbor(self.error,self.logger)
		self.family = ParseFamily(self.error)
		self.route = ParseRoute(self.error)
		self.flow = ParseFlow(self.error,self.logger)
		self.l2vpn = ParseL2VPN(self.error)
		self.process = ParseProcess(self.error)

		self._tree = {
			'configuration': {
				'neighbor':    (self._multi_neighbor,self.neighbor.make),
				'group':       (self._multi_group,true),
			},
			'group': {
				'neighbor':    (self._multi_neighbor,self.neighbor.make),
				'static':      (self._multi_static,true),
				'flow':        (self._multi_flow,true),
				'l2vpn':       (self._multi_l2vpn,true),
				'process':     (self._multi_process,true),
				'family':      (self._multi_family,true),
				'capability':  (self._multi_capability,true),
				'operational': (self._multi_operational,true),
			},
			'neighbor': {
				'static':      (self._multi_static,true),
				'flow':        (self._multi_flow,true),
				'l2vpn':       (self._multi_l2vpn,true),
				'process':     (self._multi_process,true),
				'family':      (self._multi_family,true),
				'capability':  (self._multi_capability,true),
				'operational': (self._multi_operational,true),
			},
			'static': {
				'route':       (self._multi_static_route,self.route.check_static_route),
			},
			'flow': {
				'route':       (self._multi_flow_route,self.flow.check_flow),
			},
			'l2vpn': {
				'vpls':       (self._multi_l2vpn_vpls,self.l2vpn.check_vpls),
			},
			'flow-route': {
				'match':       (self._multi_match,true),
				'then':        (self._multi_then,true),
			},
			'process': {
				'send':    (self._multi_api,true),
				'receive': (self._multi_api,true),
			}
		}

		self._command = {
			'group': {
				'description':   self.neighbor.description,
				'router-id':     self.neighbor.router_id,
				'host-name':     self.neighbor.hostname,
				'domain-name':   self.neighbor.domainname,
				'local-address': self.neighbor.ip,
				'local-as':      self.neighbor.asn,
				'peer-as':       self.neighbor.asn,
				'passive':       self.neighbor.passive,
				'listen':        self.neighbor.listen,
				'hold-time':     self.neighbor.holdtime,
				'md5':           self.neighbor.md5,
				'ttl-security':  self.neighbor.ttl,
				'group-updates': self.neighbor.groupupdate,
				'adj-rib-out':   self.neighbor.adjribout,
				'auto-flush':    self.neighbor.autoflush,
			},
			'neighbor': {
				'description':   self.neighbor.description,
				'router-id':     self.neighbor.router_id,
				'host-name':     self.neighbor.hostname,
				'domain-name':   self.neighbor.domainname,
				'local-address': self.neighbor.ip,
				'local-as':      self.neighbor.asn,
				'peer-as':       self.neighbor.asn,
				'passive':       self.neighbor.passive,
				'listen':        self.neighbor.listen,
				'hold-time':     self.neighbor.holdtime,
				'md5':           self.neighbor.md5,
				'ttl-security':  self.neighbor.ttl,
				'group-updates': self.neighbor.groupupdate,
				'adj-rib-out':   self.neighbor.adjribout,
				'auto-flush':    self.neighbor.autoflush,
			},
			'capability': {
				'route-refresh':    self.neighbor.capability.refresh,
				'graceful-restart': self.neighbor.capability.gracefulrestart,
				'multi-session':    self.neighbor.capability.multisession,
				'add-path':         self.neighbor.capability.addpath,
				'aigp':             self.neighbor.capability.aigp,
				'operational':      self.neighbor.capability.operational,
				'add-path':         self.neighbor.capability.addpath,
				'asn4':             self.neighbor.capability.asn4,
			},
			'family': {
				'ipv4':    self.family.ipv4,
				'ipv6':    self.family.ipv6,
				'l2vpn':   self.family.l2vpn,
				'minimal': self.family.minimal,
				'all':     self.family.all,
			},
			'static-route': {
				'origin':              self.route.origin,
				'as-path':             self.route.aspath,
				# For legacy with version 2.0.x
				'as-sequence':         self.route.aspath,
				'med':                 self.route.med,
				'aigp':                self.route.aigp,
				'next-hop':            self.route.next_hop,
				'local-preference':    self.route.local_preference,
				'atomic-aggregate':    self.route.atomic_aggregate,
				'aggregator':          self.route.aggregator,
				'path-information':    self.route.path_information,
				'originator-id':       self.route.originator_id,
				'cluster-list':        self.route.cluster_list,
				'split':               self.route.split,
				'label':               self.route.label,
				'rd':                  self.route.rd,
				'route-distinguisher': self.route.rd,
				'watchdog':            self.route.watchdog,
				# withdrawn is here to not break legacy code
				'withdraw':            self.route.withdraw,
				'withdrawn':           self.route.withdraw,
				'name':                self.route.name,
				'community':           self.route.community,
				'extended-community':  self.route.extended_community,
				'attribute':           self.route.generic_attribute,
			},
			'l2vpn-vpls': {
				'endpoint':            self.l2vpn.vpls_endpoint,
				'offset':              self.l2vpn.vpls_offset,
				'size':                self.l2vpn.vpls_size,
				'base':                self.l2vpn.vpls_base,
				'origin':              self.route.origin,
				'as-path':             self.route.aspath,
				'med':                 self.route.med,
				'next-hop':            self.route.next_hop,
				'local-preference':    self.route.local_preference,
				'originator-id':       self.route.originator_id,
				'cluster-list':        self.route.cluster_list,
				'rd':                  self.route.rd,
				'route-distinguisher': self.route.rd,
				'withdraw':            self.route.withdraw,
				'withdrawn':           self.route.withdraw,
				'name':                self.route.name,
				'community':           self.route.community,
				'extended-community':  self.route.extended_community,
			},
			'flow-route': {
				'rd':                  self.route.rd,
				'route-distinguisher': self.route.rd,
				'next-hop':            self.flow.next_hop,
			},
			'flow-match': {
				'source':              self.flow.source,
				'source-ipv4':         self.flow.source,
				'destination':         self.flow.destination,
				'destination-ipv4':    self.flow.destination,
				'port':                self.flow.anyport,
				'source-port':         self.flow.source_port,
				'destination-port':    self.flow.destination_port,
				'protocol':            self.flow.protocol,
				'next-header':         self.flow.next_header,
				'tcp-flags':           self.flow.tcp_flags,
				'icmp-type':           self.flow.icmp_type,
				'icmp-code':           self.flow.icmp_code,
				'fragment':            self.flow.fragment,
				'dscp':                self.flow.dscp,
				'traffic-class':       self.flow.traffic_class,
				'packet-length':       self.flow.packet_length,
				'flow-label':          self.flow.flow_label,
			},
			'flow-then': {
				'accept':              self.flow.accept,
				'discard':             self.flow.discard,
				'rate-limit':          self.flow.rate_limit,
				'redirect':            self.flow.redirect,
				'redirect-to-nexthop': self.flow.redirect_next_hop,
				'copy':                self.flow.copy,
				'mark':                self.flow.mark,
				'action':              self.flow.action,
				'community':           self.route.community,
				'extended-community':  self.route.extended_community,
			},
		}

		self._clear()

	def _clear (self):
		self.processes = {}
		self.neighbors = {}
		self._neighbors = {}

		self.error.clear()

		self._scope = []
		self._location = ['root']

		self.tokens.clear()
		self.error.clear()
		self.neighbor.clear()
		self.family.clear()
		self.route.clear()
		self.flow.clear()
		self.l2vpn.clear()
		self.process.clear()

	# Public Interface

	def reload (self):
		try:
			return self._reload()
		except KeyboardInterrupt:
			return self.error.set('configuration reload aborted by ^C or SIGINT')
		except Exception:
			# unhandled configuration parsing issue
			raise

	def _reload (self):
		# taking the first configuration available (FIFO buffer)
		fname = self._configurations.pop(0)
		self.process.configuration(fname)
		self._configurations.append(fname)

		# storing the routes associated with each peer so we can find what changed
		backup_changes = {}
		for neighbor in self._neighbors:
			backup_changes[neighbor] = self._neighbors[neighbor].changes

		# clearing the current configuration to be able to re-parse it
		self._clear()

		if not self.tokens.set_file(fname):
			return False

		# parsing the configurtion
		r = False
		while not self.tokens.finished:
			r = self._dispatch(
				self._scope,'configuration',
				['group','neighbor'],
				[]
			)
			if r is False:
				break

		# handling possible parsing errors
		if r not in [True,None]:
			return self.error.set(
				"\n"
				"syntax error in section %s\n"
				"line %d: %s\n"
				"\n%s" % (
					self._location[-1],
					self.tokens.number,
					' '.join(self.tokens.line),
					str(self.error)
				)
			)

		# parsing was sucessful, assigning the result
		self.neighbors = self._neighbors

		# installing in the neighbor what was its previous routes so we can
		# add/withdraw what need to be
		for neighbor in self.neighbors:
			self.neighbors[neighbor].backup_changes = backup_changes.get(neighbor,[])

		# we are not really running the program, just want to ....
		if environment.settings().debug.route:
			from exabgp.configuration.check import check_message
			if check_message(self.neighbors,environment.settings().debug.route):
				sys.exit(0)
			sys.exit(1)

		# we are not really running the program, just want check the configuration validity
		if environment.settings().debug.selfcheck:
			from exabgp.configuration.current.check import check_neighbor
			if check_neighbor(self.neighbors):
				sys.exit(0)
			sys.exit(1)

		return True

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def change_to_peers (self, change, peers):
		result = True
		for neighbor in self.neighbors:
			if neighbor in peers:
				if change.nlri.family() in self.neighbors[neighbor].families():
					self.neighbors[neighbor].rib.outgoing.insert_announced(change)
				else:
					self.logger.configuration('the route family is not configured on neighbor','error')
					result = False
		return result

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def eor_to_peers (self, family, peers):
		result = False
		for neighbor in self.neighbors:
			if neighbor in peers:
				result = True
				self.neighbors[neighbor].eor.append(family)
		return result

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def operational_to_peers (self, operational, peers):
		result = True
		for neighbor in self.neighbors:
			if neighbor in peers:
				if operational.family() in self.neighbors[neighbor].families():
					if operational.name == 'ASM':
						self.neighbors[neighbor].asm[operational.family()] = operational
					self.neighbors[neighbor].messages.append(operational)
				else:
					self.logger.configuration('the route family is not configured on neighbor','error')
					result = False
		return result

	# XXX: FIXME: move this from here to the reactor (or whatever will manage command from user later)
	def refresh_to_peers (self, refresh, peers):
		result = True
		for neighbor in self.neighbors:
			if neighbor in peers:
				family = (refresh.afi,refresh.safi)
				if family in self.neighbors[neighbor].families():
					self.neighbors[neighbor].refresh.append(refresh.__class__(refresh.afi,refresh.safi))
				else:
					result = False
		return result

	# Tokenisation

	def number (self):
		return self._number

	# name is not used yet but will come really handy if we have name collision :D
	def _dispatch (self, scope, command, multi, single, location=None):
		if location:
			self._location = location
			self.flow.clear()
		try:
			tokens = self.tokens.next()
		except IndexError:
			return self.error.set('configuration file incomplete (most likely missing })')
		self.logger.configuration("parsing | %-13s | '%s'" % (command,"' '".join(tokens)))
		end = tokens[-1]
		if multi and end == '{':
			self._location.append(tokens[0])
			result = self._multi_line(scope,command,tokens[:-1],multi)
			if self.error.debug and result is False:
				pdb.set_trace()
			return result
		if single and end == ';':
			result = self._single_line(scope,command,tokens[:-1],single)
			if self.error.debug and result is False:
				pdb.set_trace()
			return result
		if end == '}':
			if len(self._location) == 1:
				return self.error.set('closing too many parenthesis')
			self._location.pop(-1)
			return None
		return False

	def _multi (self, tree, scope, name, tokens, valid):
		command = tokens[0]

		if valid and command not in valid:
			return self.error.set('option %s in not valid here' % command)

		if name not in tree:
			return False
		run, validate = tree[name].get(command,(false,false))
		if not run(scope,command,tokens[1:]):
			if self.error.debug:
				pdb.set_trace()
			return False
		if not validate(scope,self):
			if self.error.debug:
				pdb.set_trace()
			return False
		return True

	def _multi_line (self, scope, name, tokens, valid):
		return self._multi(self._tree,scope,name,tokens,valid)

	def _single_line (self, scope, name, tokens, valid):
		command = tokens[0]
		if valid and command not in valid:
			return self.error.set('invalid keyword "%s"' % command)

		family = {
			'static-route': {
				'rd': SAFI.mpls_vpn,
				'route-distinguisher': SAFI.mpls_vpn,
			},
			'l2vpn-vpls': {
				'rd': SAFI.vpls,
				'route-distinguisher': SAFI.vpls,
			},
			'flow-route': {
				'rd': SAFI.flow_vpn,
				'route-distinguisher': SAFI.flow_vpn,
			}
		}

		if name in self._command:
			if command in self._command[name]:
				if command in family.get(name,{}):
					return self._command[name][command](scope,command,tokens[1:],family[name][command])
				return self._command[name][command](scope,command,tokens[1:])

		elif name == 'operational':
			if command == 'asm':
				return self._single_operational_asm(scope,name,tokens[1])
			# it does not make sense to have adm

		elif name == 'process':
			if command == 'run':
				return self.process.run(scope,'process-run',tokens[1:])
			if command == 'encoder':
				return self.process.encoder(scope,'encoder',tokens[1:])

			if command == 'neighbor-changes':
				return self.process.command(scope,'neighbor-changes',tokens[1:])

		elif name in ['send','receive']:  # process / send

			if command in ['packets','parsed','consolidate']:
				return self.process.command(scope,'%s-%s' % (name,command),tokens[1:])

			for message in Message.CODE.MESSAGES:
				if command == message.SHORT:
					return self.process.command(scope,'%s-%d' % (name,message),tokens[1:])

		elif name == 'static':
			if command == 'route':
				return self._single_static_route(scope,name,tokens[1:])

		elif name == 'l2vpn':
			if command == 'vpls':
				return self._single_l2vpn_vpls(scope,name,tokens[1:])

		return False

	# Programs used to control exabgp

	def _multi_process (self, scope, command, tokens):
		while True:
			r = self._dispatch(
				scope,'process',
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
		self.processes.setdefault(name,{})['neighbor'] = scope[-1]['peer-address'] if 'peer-address' in scope[-1] else '*'

		for key in ['neighbor-changes',]:
			self.processes[name][key] = scope[-1].pop(key,False)

		for direction in ['send','receive']:
			for action in ['packets','parsed','consolidate']:
				key = '%s-%s' % (direction,action)
				self.processes[name][key] = scope[-1].pop(key,False)

			for message in Message.CODE.MESSAGES:
				key = '%s-%d' % (direction,message)
				self.processes[name][key] = scope[-1].pop(key,False)

		run = scope[-1].pop('process-run','')
		if run:
			if len(tokens) != 1:
				return self.error.set(self.process.syntax)

			self.processes[name]['encoder'] = scope[-1].get('encoder','') or self.api_encoder
			self.processes[name]['run'] = run
			return True
		elif len(tokens):
			return self.error.set(self.process.syntax)

	# Limit the AFI/SAFI pair announced to peers

	def _multi_family (self, scope, command, tokens):
		# we know all the families we should use
		scope[-1]['families'] = []
		while True:
			r = self._dispatch(
				scope,'family',
				[],
				self._command['family'].keys()
			)
			if r is False:
				return False
			if r is None:
				break
		self.family.clear()
		return True

	# capacity

	def _multi_capability (self, scope, command, tokens):
		# we know all the families we should use
		while True:
			r = self._dispatch(
				scope,'capability',
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

	def _multi_group (self, scope, command, address):
		# if len(tokens) != 2:
		# 	return self.error.set('syntax: group <name> { <options> }')

		scope.append({})
		while True:
			r = self._dispatch(
				scope,'group',
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
				scope.pop(-1)
				return True

	def _multi_neighbor (self, scope, command, tokens):
		if len(tokens) != 1:
			return self.error.set('syntax: neighbor <ip> { <options> }')

		address = tokens[0]
		scope.append({})
		try:
			scope[-1]['peer-address'] = IP.create(address)
		except (IndexError,ValueError,socket.error):
			return self.error.set('"%s" is not a valid IP address' % address)

		while True:
			r = self._dispatch(
				scope,'neighbor',
				[
					'static','flow','l2vpn',
					'process','family','capability','operational'
				],
				[
					'description','router-id','local-address','local-as','peer-as',
					'host-name','domain-name',
					'passive','listen','hold-time','add-path','graceful-restart','md5',
					'ttl-security','multi-session','group-updates','asn4','aigp',
					'auto-flush','adj-rib-out'
				]
			)
			# XXX: THIS SHOULD ALLOW CAPABILITY AND NOT THE INDIVIDUAL SUB KEYS
			if r is False:
				return False
			if r is None:
				return True

	#  Group Static ................

	def _multi_static (self, scope, command, tokens):
		if len(tokens) != 0:
			return self.error.set('syntax: static { route; route; ... }')

		while True:
			r = self._dispatch(
				scope,'static',
				['route',],
				['route',]
			)
			if r is False:
				return False
			if r is None:
				return True

	# Group Route  ........

	def _split_last_route (self, scope):
		# if the route does not need to be broken in smaller routes, return
		change = scope[-1]['announce'][-1]
		if Attribute.CODE.INTERNAL_SPLIT not in change.attributes:
			return True

		# ignore if the request is for an aggregate, or the same size
		mask = change.nlri.mask
		split = change.attributes[Attribute.CODE.INTERNAL_SPLIT]
		if mask >= split:
			return True

		# get a local copy of the route
		change = scope[-1]['announce'].pop(-1)

		# calculate the number of IP in the /<size> of the new route
		increment = pow(2,(len(change.nlri.packed)*8) - split)
		# how many new routes are we going to create from the initial one
		number = pow(2,split - change.nlri.mask)

		# convert the IP into a integer/long
		ip = 0
		for c in change.nlri.packed:
			ip <<= 8
			ip += ord(c)

		afi = change.nlri.afi
		safi = change.nlri.safi

		# Really ugly
		klass = change.nlri.__class__
		if klass is INET:
			path_info = change.nlri.path_info
		elif klass is MPLS:
			path_info = None
			labels = change.nlri.labels
			rd = change.nlri.rd
		# packed and not pack() but does not matter atm, it is an IP not a NextHop
		nexthop = change.nlri.nexthop.packed

		change.nlri.mask = split
		change.nlri = None
		# generate the new routes
		for _ in range(number):
			# update ip to the next route, this recalculate the "ip" field of the Inet class
			nlri = klass(afi,safi,pack_int(afi,ip,split),split,nexthop,OUT.ANNOUNCE,path_info)
			if klass is MPLS:
				nlri.labels = labels
				nlri.rd = rd
			# next ip
			ip += increment
			# save route
			scope[-1]['announce'].append(Change(nlri,change.attributes))

		return True

	def _multi_static_route (self, scope, command, tokens):
		if len(tokens) != 1:
			return self.error.set(self.route.syntax)

		if not self.route.insert_static_route(scope,command,tokens):
			return False

		while True:
			r = self._dispatch(
				scope,'static-route',
				self._command['static-route'].keys(),
				self._command['static-route'].keys()
			)
			if r is False:
				return False
			if r is None:
				return self._split_last_route(scope)

	def _single_static_route (self, scope, command, tokens):
		if len(tokens) < 3:
			return False

		if not self.route.insert_static_route(scope,command,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)

			if command in ('withdraw','withdrawn'):
				if self.route.withdraw(scope,command,tokens):
					continue
				return False

			if len(tokens) < 1:
				return False

			if command in self._command['static-route']:
				if command in ('rd','route-distinguisher'):
					if self._command['static-route'][command](scope,command,tokens,SAFI.nlri_mpls):
						continue
				else:
					if self._command['static-route'][command](scope,command,tokens):
						continue
			else:
				return False
			return False

		if not self.route.check_static_route(scope,self):
			return False

		return self._split_last_route(scope)

	def _single_l2vpn_vpls (self, scope, command, tokens):
		# TODO: actual length?(like rd+lb+bo+ve+bs+rd; 14 or so)
		if len(tokens) < 10:
			return False

		if not self._insert_l2vpn_vpls(scope,command,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)
			if len(tokens) < 1:
				return False
			if command in self._command['l2vpn-vpls']:
				if command in ('rd','route-distinguisher'):
					if self._command['l2vpn-vpls'][command](scope,command,tokens,SAFI.vpls):
						continue
				else:
					if self._command['l2vpn-vpls'][command](scope,command,tokens):
						continue
			else:
				return False
			return False

		if not self.l2vpn.check_vpls(scope,self):
			return False
		return True

	# VPLS

	def _multi_l2vpn (self, scope, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.l2vpn.syntax)

		while True:
			r = self._dispatch(
				scope,'l2vpn',
				['vpls',],
				['vpls',]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _multi_l2vpn_vpls (self, scope, command, tokens):
		if len(tokens) > 1:
			return self.error.set(self.l2vpn.syntax)

		if not self._insert_l2vpn_vpls(scope,command,tokens):
			return False

		while True:
			r = self._dispatch(
				scope,'l2vpn-vpls',
				self._command['l2vpn-vpls'].keys(),
				self._command['l2vpn-vpls'].keys()
			)
			if r is False:
				return False
			if r is None:
				break

		return True

	def _insert_l2vpn_vpls (self, scope, command, tokens=None):
		try:
			attributes = Attributes()
			change = Change(VPLS(None,None,None,None,None),attributes)
		except ValueError:
			return self.error.set(self.l2vpn.syntax)

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(change)
		return True


	# Group Flow  ........

	def _multi_flow (self, scope, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.flow.syntax)

		while True:
			r = self._dispatch(
				scope,'flow',
				['route',],
				[]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	def _insert_flow_route (self, scope, command, tokens=None):
		if self.flow.state != 'out':
			return self.error.set(self.flow.syntax)

		self.flow.state = 'match'

		try:
			attributes = Attributes()
			attributes[Attribute.CODE.EXTENDED_COMMUNITY] = ExtendedCommunities()
			flow = Change(Flow(),attributes)
		except ValueError:
			return self.error.set(self.flow.syntax)

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(flow)
		return True

	def _multi_flow_route (self, scope, command, tokens):
		if len(tokens) > 1:
			return self.error.set(self.flow.syntax)

		if not self._insert_flow_route(scope,command):
			return False

		while True:
			r = self._dispatch(
				scope,'flow-route',
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

	def _multi_match (self, scope, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.flow.syntax)

		if self.flow.state != 'match':
			return self.error.set(self.flow.syntax)

		self.flow.state = 'then'

		while True:
			r = self._dispatch(
				scope,'flow-match',
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

	def _multi_then (self, scope, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.flow.syntax)

		if self.flow.state != 'then':
			return self.error.set(self.flow.syntax)

		self.flow.state = 'out'

		while True:
			r = self._dispatch(
				scope,'flow-then',
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

	def _multi_api (self, scope, command, tokens):
		if len(tokens) != 0:
			return self.error.set(self.flow.syntax)

		while True:
			r = self._dispatch(
				scope,command,
				[],
				[
					'packets','parsed','consolidate',
					'notification','open','keepalive',
					'update','refresh','operational'
				]
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	#  Group Operational ................

	def _multi_operational (self, scope, command, tokens):
		if len(tokens) != 0:
			return self.error.set('syntax: operational { command; command; ... }')

		while True:
			r = self._dispatch(
				scope,'operational',
				[],
				['asm',]
			)
			if r is False:
				return False
			if r is None:
				return True

	def _single_operational_asm (self, scope, command, value):
		return self._single_operational(Advisory.ASM,scope,['afi','safi','advisory'],value)

	def _single_operational (self, klass, scope, parameters, value):
		def utf8 (string): return string.encode('utf-8')[1:-1]

		convert = {
			'afi': AFI.value,
			'safi': SAFI.value,
			'sequence': int,
			'counter': long,
			'advisory': utf8
		}

		def valid (_):
			return True

		def u32 (_):
			return int(_) <= 0xFFFFFFFF

		def u64 (_):
			return long(_) <= 0xFFFFFFFFFFFFFFFF

		def advisory (_):
			return len(_.encode('utf-8')) <= MAX_ADVISORY + 2  # the two quotes

		validate = {
			'afi': AFI.value,
			'safi': SAFI.value,
			'sequence': u32,
			'counter': u64,
		}

		number = len(parameters)*2
		tokens = formated(value).split(' ',number-1)
		if len(tokens) != number:
			return self.error.set('invalid operational syntax, wrong number of arguments')
			return False

		data = {}

		while tokens and parameters:
			command = tokens.pop(0).lower()
			value = tokens.pop(0)

			if command == 'router-id':
				if isipv4(value):
					data['routerid'] = RouterID(value)
				else:
					return self.error.set('invalid operational value for %s' % command)
					return False
				continue

			expected = parameters.pop(0)

			if command != expected:
				return self.error.set('invalid operational syntax, unknown argument %s' % command)
				return False
			if not validate.get(command,valid)(value):
				return self.error.set('invalid operational value for %s' % command)
				return False

			data[command] = convert[command](value)

		if tokens or parameters:
			return self.error.set('invalid advisory syntax, missing argument(s) %s' % ', '.join(parameters))
			return False

		if 'routerid' not in data:
			data['routerid'] = None

		if 'operational-message' not in scope[-1]:
			scope[-1]['operational-message'] = []

		# iterate on each family for the peer if multiprotocol is set.
		scope[-1]['operationa-messagel'].append(klass(**data))
		return True
