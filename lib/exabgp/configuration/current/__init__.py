# encoding: utf-8
"""
current.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import stat
import time
import socket
import shlex

from copy import deepcopy

from exabgp.util.ip import isipv4

from exabgp.configuration.environment import environment
from exabgp.configuration.format import formated

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.neighbor import Neighbor

from exabgp.protocol.ip import IP

from exabgp.bgp.message import OUT
from exabgp.bgp.message import Message

from exabgp.bgp.message.open.routerid import RouterID

from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import MPLS
from exabgp.bgp.message.update.nlri import VPLS
# from exabgp.bgp.message.update.nlri import EVPN
from exabgp.bgp.message.update.nlri.flow import NLRI
from exabgp.bgp.message.update.nlri.flow import Flow

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities

from exabgp.bgp.message.operational import MAX_ADVISORY
from exabgp.bgp.message.operational import Advisory

from exabgp.rib.change import Change

from exabgp.logger import Logger

from exabgp.configuration.current.error import Error
from exabgp.configuration.current.neighbor import ParseNeighbor
from exabgp.configuration.current.family import ParseFamily
from exabgp.configuration.current.route import ParseRoute
from exabgp.configuration.current.flow import ParseFlow

# Duck class, faking part of the Attribute interface
# We add this to routes when when need o split a route in smaller route
# The value stored is the longer netmask we want to use
# As this is not a real BGP attribute this stays in the configuration file


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi, integer, mask):
	return ''.join([chr((integer >> (offset * 8)) & 0xff) for offset in range(IP.length(afi)-1,-1,-1)])


def hostname ():
	value = socket.gethostname()
	if not value:
		return 'localhost'
	return value.split('.')[0]


def domainname ():
	value = socket.gethostname()
	if not value:
		return 'localdomain'
	return ''.join(value.split('.')[1:])


class Configuration (object):
	_str_bad_flow = "you tried to filter a flow using an invalid port for a component .."
	_str_vpls_error = \
		'syntax:\n' \
		'vpls site_name {\n' \
		'   endpoint <vpls endpoint id; integer>\n' \
		'   base <label base; integer>\n' \
		'   offset <block offet; interger>\n' \
		'   size <block size; integer>\n' \
		'   route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535\n' \
		'   next-hop 192.0.1.254;\n' \
		'   origin IGP|EGP|INCOMPLETE;\n' \
		'   as-path [ as as as as] ;\n' \
		'   med 100;\n' \
		'   local-preference 100;\n' \
		'   community [ 65000 65001 65002 ];\n' \
		'   extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 l2info:19:0:1500:111 ]\n' \
		'   originator-id 10.0.0.10;\n' \
		'   cluster-list [ 10.10.0.1 10.10.0.2 ];\n' \
		'   withdraw\n' \
		'   name what-you-want-to-remember-about-the-route\n' \
		'}\n'


	_str_process_error = \
		'syntax:\n' \
		'process name-of-process {\n' \
		'   run /path/to/command with its args;\n' \
		'   encoder text|json;\n' \
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

	_str_vpls_bad_size = "you tried to configure an invalid l2vpn vpls block-size"
	_str_vpls_bad_offset = "you tried to configure an invalid l2vpn vpls block-offset"
	_str_vpls_bad_label = "you tried to configure an invalid l2vpn vpls label"
	_str_vpls_bad_enpoint = "you tried to configure an invalid l2vpn vpls endpoint"

	def __init__ (self, configurations, text=False):
		self.api_encoder = environment.settings().api.encoder
		self.fifo = environment.settings().api.file

		self.logger = Logger()
		self._text = text
		self._configurations = configurations

		self.error = Error()
		self.neighbor = ParseNeighbor(self.error)
		self.family = ParseFamily(self.error)
		self.route = ParseRoute(self.error)
		self.flow = ParseFlow(self.error,self.logger)

		self._dispatch_neighbor = {
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
		}

		self._dispatch_family = {
			'ipv4':    self.family.ipv4,
			'ipv6':    self.family.ipv6,
			'l2vpn':   self.family.l2vpn,
			'minimal': self.family.minimal,
			'all':     self.family.all,
		}

		self._dispatch_capability = {
			# deprecated
			'route-refresh':    self.neighbor.capability.refresh,
			'graceful-restart': self.neighbor.capability.gracefulrestart,
			'multi-session':    self.neighbor.capability.multisession,
			'add-path':         self.neighbor.capability.addpath,
			'aigp':             self.neighbor.capability.aigp,
			'operational':      self.neighbor.capability.operational,
			'add-path':         self.neighbor.capability.addpath,
			'asn4':             self.neighbor.capability.asn4,
		}

		self._dispatch_route = {
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
		}

		self._dispatch_flow = {
			'rd':                  self.route.rd,
			'route-distinguisher': self.route.rd,
			'next-hop':            self.flow.next_hop,
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
		}

		self._dispatch_vpls = {
			'endpoint': self._l2vpn_vpls_endpoint,
			'offset': self._l2vpn_vpls_offset,
			'size': self._l2vpn_vpls_size,
			'base': self._l2vpn_vpls_base,
			'origin': self.route.origin,
			'as-path': self.route.aspath,
			'med': self.route.med,
			'next-hop': self.route.next_hop,
			'local-preference': self.route.local_preference,
			'originator-id': self.route.originator_id,
			'cluster-list': self.route.cluster_list,
			'rd': self.route.rd,
			'route-distinguisher': self.route.rd,
			'withdraw': self.route.withdraw,
			'withdrawn': self.route.withdraw,
			'name': self.route.name,
			'community': self.route.community,
			'extended-community': self.route.extended_community,
		}

		self._clear()

		self.debug = True  # delete me
		self._error = ''

	def _clear (self):
		self.processes = {}
		self.neighbors = {}
		self._neighbors = {}

		self.error.clear()
		self._error = ''  # delete me

		self._scope = []
		self._location = ['root']
		self._line = []
		self._number = 1

		self.error.clear()
		self.neighbor.clear()
		self.family.clear()
		self.route.clear()
		self.flow.clear()

	# Public Interface

	def reload (self):
		try:
			return self._reload()
		except KeyboardInterrupt:
			self.error = 'configuration reload aborted by ^C or SIGINT'
			if self.debug: raise  # noqa
			return False
		except Exception:
			self.error = 'configuration parsing issue'
			if self.debug: raise  # noqa
			return False

	def _reload (self):
		# taking the first configuration available (FIFO buffer)
		self._fname = self._configurations.pop(0)
		self._configurations.append(self._fname)

		# creating the tokeniser for the configuration
		if self._text:
			self._tokens = self._tokenise(self._fname.split('\n'))
		else:
			try:
				f = open(self._fname,'r')
				self._tokens = self._tokenise(f)
				f.close()
			except IOError,exc:
				error = str(exc)
				if error.count(']'):
					self.error = error.split(']')[1].strip()
				else:
					self.error = error
				if self.debug: raise Exception()  # noqa
				return False

		# storing the routes associated with each peer so we can find what changed
		backup_changes = {}
		for neighbor in self._neighbors:
			backup_changes[neighbor] = self._neighbors[neighbor].changes

		# clearing the current configuration to be able to re-parse it
		self._clear()

		# parsing the configurtion
		r = False
		while not self.finished():
			r = self._dispatch(
				self._scope,'configuration',
				['group','neighbor'],
				[]
			)
			if r is False:
				break

		# handling possible parsing errors
		if r not in [True,None]:
			self.error = "\nsyntax error in section %s\nline %d: %s\n\n%s" % (self._location[-1],self.number(),self.line(),self._error)
			return False

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
			from exabgp.configuration.check import check_neighbor
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

	def _tokenise (self, text):
		r = []
		config = ''
		for line in text:
			self.logger.configuration('loading | %s' % line.rstrip())
			replaced = formated(line)
			config += line
			if not replaced:
				continue
			if replaced.startswith('#'):
				continue
			command = replaced[:3]
			if command in ('md5','asm'):
				string = line.strip()[3:].strip()
				if string[-1] == ';':
					string = string[:-1]
				r.append([command,string,';'])
			elif replaced[:3] == 'run':
				r.append([t for t in replaced[:-1].split(' ',1) if t] + [replaced[-1]])
			else:
				r.append([t.lower() for t in replaced[:-1].split(' ') if t] + [replaced[-1]])
		self.logger.config(config)
		return r

	def tokens (self):
		self._number += 1
		self._line = self._tokens.pop(0)
		return self._line

	def number (self):
		return self._number

	def line (self):
		return ' '.join(self._line)

	def finished (self):
		return len(self._tokens) == 0

	# Flow control ......................

	# name is not used yet but will come really handy if we have name collision :D
	def _dispatch (self, scope, name, multi, single, location=None):
		if location:
			self._location = location
			self.flow.clear()
		try:
			tokens = self.tokens()
		except IndexError:
			self._error = 'configuration file incomplete (most likely missing })'
			if self.debug: raise Exception()  # noqa
			return False
		self.logger.configuration("parsing | %-13s | '%s'" % (name,"' '".join(tokens)))
		end = tokens[-1]
		if multi and end == '{':
			self._location.append(tokens[0])
			return self._multi_line(scope,name,tokens[:-1],multi)
		if single and end == ';':
			return self._single_line(scope,name,tokens[:-1],single)
		if end == '}':
			if len(self._location) == 1:
				self._error = 'closing too many parenthesis'
				if self.debug: raise Exception()  # noqa
				return False
			self._location.pop(-1)
			return None
		return False

	def _multi_line (self, scope, name, tokens, valid):
		command = tokens[0]

		if valid and command not in valid:
			self._error = 'option %s in not valid here' % command
			if self.debug: raise Exception()  # noqa
			return False

		if name == 'configuration':
			if command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if command == 'group':
				if len(tokens) != 2:
					self._error = 'syntax: group <name> { <options> }'
					if self.debug: raise Exception()  # noqa
					return False
				return self._multi_group(scope,tokens[1])

		if name == 'group':
			if command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if command == 'static':
				return self._multi_static(scope,tokens[1:])
			if command == 'flow':
				return self._multi_flow(scope,tokens[1:])
			if command == 'l2vpn':
				return self._multi_l2vpn(scope,tokens[1:])
			if command == 'process':
				return self._multi_process(scope,tokens[1:])
			if command == 'family':
				return self._multi_family(scope,tokens[1:])
			if command == 'capability':
				return self._multi_capability(scope,tokens[1:])
			if command == 'operational':
				return self._multi_operational(scope,tokens[1:])

		if name == 'neighbor':
			if command == 'static':
				return self._multi_static(scope,tokens[1:])
			if command == 'flow':
				return self._multi_flow(scope,tokens[1:])
			if command == 'l2vpn':
				return self._multi_l2vpn(scope,tokens[1:])
			if command == 'process':
				return self._multi_process(scope,tokens[1:])
			if command == 'family':
				return self._multi_family(scope,tokens[1:])
			if command == 'capability':
				return self._multi_capability(scope,tokens[1:])
			if command == 'operational':
				return self._multi_operational(scope,tokens[1:])

		if name == 'static':
			if command == 'route':
				if self._multi_static_route(scope,tokens[1:]):
					return self.route.check_static_route(scope)
				return False

		if name == 'flow':
			if command == 'route':
				if self._multi_flow_route(scope,tokens[1:]):
					return self._check_flow_route(scope)
				return False

		if name == 'l2vpn':
			if command == 'vpls':
				if self._multi_l2vpn_vpls(scope,tokens[1:]):
					return self._check_l2vpn_vpls(scope)
				return False

		if name == 'flow-route':
			if command == 'match':
				if self._multi_match(scope,tokens[1:]):
					return True
				return False
			if command == 'then':
				if self._multi_then(scope,tokens[1:]):
					return True
				return False

		if name == 'process':
			if command in ['send','receive']:
				if self._multi_api(scope,command,tokens[1:]):
					return True
				return False

		return False

	def _single_line (self, scope, name, tokens, valid):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'invalid keyword "%s"' % command
			if self.debug: raise Exception()  # noqa
			return False

		elif name == 'route':
			if command in self._dispatch_route:
				if command in ('rd','route-distinguisher'):
					return self._dispatch_route[command](scope,tokens[1:],SAFI.mpls_vpn)
				else:
					return self._dispatch_route[command](scope,tokens[1:])

		elif name == 'l2vpn':
			if command in self._dispatch_vpls:
				if command in ('rd','route-distinguisher'):
					return self._dispatch_vpls[command](scope,tokens[1:],SAFI.vpls)
				else:
					return self._dispatch_vpls[command](scope,tokens[1:])

		elif name == 'flow-route':
			if command in self._dispatch_flow:
				if command in ('rd','route-distinguisher'):
					return self._dispatch_flow[command](scope,tokens[1:],SAFI.flow_vpn)
				else:
					return self._dispatch_flow[command](scope,tokens[1:])

		elif name == 'flow-match':
			if command in self._dispatch_flow:
				return self._dispatch_flow[command](scope,tokens[1:])

		elif name == 'flow-then':
			if command in self._dispatch_flow:
				return self._dispatch_flow[command](scope,tokens[1:])

		if name in ('neighbor','group'):
			if command in self._dispatch_neighbor:
				return self._dispatch_neighbor[command](scope,command,tokens[1:])

		elif name == 'family':
			if command in self._dispatch_family:
				return self._dispatch_family[command](scope,tokens[1:])

		elif name == 'capability':
			if command in self._dispatch_capability:
				return self._dispatch_capability[command](scope,command,tokens[1:])

		elif name == 'process':
			if command == 'run':
				return self._set_process_run(scope,'process-run',tokens[1:])
			if command == 'encoder':
				return self._set_process_encoder(scope,'encoder',tokens[1:])

			# legacy ...

			if command == 'parse-routes':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'neighbor-changes',tokens[1:])
				self._set_process_command(scope,'receive-updates',tokens[1:])
				return True

			if command == 'peer-updates':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'neighbor-changes',tokens[1:])
				self._set_process_command(scope,'receive-updates',tokens[1:])
				return True

			if command == 'send-packets':
				return self._set_process_command(scope,'send-packets',tokens[1:])

			if command == 'neighbor-changes':
				return self._set_process_command(scope,'neighbor-changes',tokens[1:])

			if command == 'receive-packets':
				return self._set_process_command(scope,'receive-packets',tokens[1:])

			if command == 'receive-parsed':
				return self._set_process_command(scope,'receive-parsed',tokens[1:])

			if command == 'receive-routes':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'receive-updates',tokens[1:])
				self._set_process_command(scope,'receive-refresh',tokens[1:])
				return True

			if command == 'receive-operational':
				self._set_process_command(scope,'receive-parsed',tokens[1:])
				self._set_process_command(scope,'receive-operational',tokens[1:])
				return True

		elif name in ['send','receive']:  # process / send

			if command in ['packets','parsed','consolidate']:
				return self._set_process_command(scope,'%s-%s' % (name,command),tokens[1:])

			for message in Message.CODE.MESSAGES:
				if command == message.SHORT:
					return self._set_process_command(scope,'%s-%d' % (name,message),tokens[1:])

			# Legacy
			if command == 'neighbor-changes':
				return self._set_process_command(scope,'neighbor-changes',tokens[1:])

		elif name == 'static':
			if command == 'route':
				return self._single_static_route(scope,tokens[1:])

		elif name == 'l2vpn':
			if command == 'vpls':
				return self._single_l2vpn_vpls(scope,tokens[1:])

		elif name == 'operational':
			if command == 'asm':
				return self._single_operational_asm(scope,tokens[1])
			# it does not make sense to have adm

		return False

	# Programs used to control exabgp

	def _multi_process (self, scope, tokens):
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
				self._error = self._str_process_error
				if self.debug: raise Exception()  # noqa
				return False
			self.processes[name]['encoder'] = scope[-1].get('encoder','') or self.api_encoder
			self.processes[name]['run'] = run
			return True
		elif len(tokens):
			self._error = self._str_process_error
			if self.debug: raise Exception()  # noqa
			return False

	def _set_process_command (self, scope, command, value):
		scope[-1][command] = True
		return True

	def _set_process_encoder (self, scope, command, value):
		if value and value[0] in ('text','json'):
			scope[-1][command] = value[0]
			return True

		self._error = self._str_process_error
		if self.debug: raise Exception()  # noqa
		return False

	def _set_process_run (self, scope, command, value):
		line = ' '.join(value).strip()
		if len(line) > 2 and line[0] == line[-1] and line[0] in ['"',"'"]:
			line = line[1:-1]
		if ' ' in line:
			args = shlex.split(line,' ')
			prg,args = args[0],args[1:]
		else:
			prg = line
			args = ''

		if not prg:
			self._error = 'prg requires the program to prg as an argument (quoted or unquoted)'
			if self.debug: raise Exception()  # noqa
			return False

		if prg[0] != '/':
			if prg.startswith('etc/exabgp'):
				parts = prg.split('/')

				env = os.environ.get('ETC','')
				if env:
					options = [
						os.path.join(env.rstrip('/'),*os.path.join(parts[2:])),
						'/etc/exabgp'
					]
				else:
					options = []
					options.append('/etc/exabgp')
					pwd = os.environ.get('PWD','').split('/')
					if pwd:
						# without abspath the path is not / prefixed !
						if pwd[-1] in ('etc','sbin'):
							options.append(os.path.abspath(os.path.join(os.path.join(*pwd[:-1]),os.path.join(*parts))))
						if 'etc' not in pwd:
							options.append(os.path.abspath(os.path.join(os.path.join(*pwd),os.path.join(*parts))))
			else:
				options = [
					os.path.abspath(os.path.join(os.path.dirname(self._fname),prg)),
					'/etc/exabgp'
				]
			for option in options:
				if os.path.exists(option):
					prg = option

		if not os.path.exists(prg):
			self._error = 'can not locate the the program "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		# race conditions are possible, those are sanity checks not security ones ...
		s = os.stat(prg)

		if stat.S_ISDIR(s.st_mode):
			self._error = 'can not execute directories "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		if s.st_mode & stat.S_ISUID:
			self._error = 'refusing to run setuid programs "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		check = stat.S_IXOTH
		if s.st_uid == os.getuid():
			check |= stat.S_IXUSR
		if s.st_gid == os.getgid():
			check |= stat.S_IXGRP

		if not check & s.st_mode:
			self._error = 'exabgp will not be able to run this program "%s"' % prg
			if self.debug: raise Exception()  # noqa
			return False

		if args:
			scope[-1][command] = [prg] + args
		else:
			scope[-1][command] = [prg,]
		return True

	# Limit the AFI/SAFI pair announced to peers

	def _multi_family (self, scope, tokens):
		# we know all the families we should use
		scope[-1]['families'] = []
		while True:
			r = self._dispatch(
				scope,'family',
				[],
				self._dispatch_family.keys()
			)
			if r is False:
				return False
			if r is None:
				break
		self.family.clear()
		return True

	# capacity

	def _multi_capability (self, scope, tokens):
		# we know all the families we should use
		while True:
			r = self._dispatch(
				scope,'capability',
				[],
				self._dispatch_capability.keys()
			)
			if r is False:
				return False
			if r is None:
				break
		return True

	# route grouping with watchdog

	# Group Neighbor

	def _multi_group (self, scope, address):
		scope.append({})
		while True:
			r = self._dispatch(
				scope,'group',
				[
					'static','flow','l2vpn',
					'neighbor','process','family',
					'capability','operational'
				],
				self._dispatch_neighbor.keys()
			)
			if r is False:
				return False
			if r is None:
				scope.pop(-1)
				return True

	def _make_neighbor (self, scope):
		# we have local_scope[-2] as the group template and local_scope[-1] as the peer specific
		if len(scope) > 1:
			for key,content in scope[-2].iteritems():
				if key not in scope[-1]:
					scope[-1][key] = deepcopy(content)
				elif key == 'announce':
					scope[-1][key].extend(scope[-2][key])

		neighbor = Neighbor()
		for local_scope in scope:
			value = local_scope.get('router-id','')
			if value:
				neighbor.router_id = value
			value = local_scope.get('peer-address','')
			if value:
				neighbor.peer_address = value
			value = local_scope.get('local-address','')
			if value:
				neighbor.local_address = value
			value = local_scope.get('local-as','')
			if value:
				neighbor.local_as = value
			value = local_scope.get('peer-as','')
			if value:
				neighbor.peer_as = value
			value = local_scope.get('passive',False)
			if value:
				neighbor.passive = value
			value = local_scope.get('listen',0)
			if value:
				neighbor.listen = value
			value = local_scope.get('hold-time','')
			if value:
				neighbor.hold_time = value

			neighbor.host_name = local_scope.get('host-name',hostname())
			neighbor.domain_name = local_scope.get('domain-name',domainname())

			neighbor.changes = local_scope.get('announce',[])
			messages = local_scope.get('operational-message',[])

		# we want to have a socket for the cli
		if self.fifo:
			_cli_name = 'CLI'
			self.processes[_cli_name] = {
				'neighbor': '*',
				'encoder': 'json',
				'run': [sys.executable, sys.argv[0]],

				'neighbor-changes': False,

				'receive-consolidate': False,
				'receive-packets': False,
				'receive-parsed': False,

				'send-consolidate': False,
				'send-packets': False,
				'send-parsed': False,
			}

			for direction in ['send','receive']:
				for message in [
					Message.CODE.NOTIFICATION,
					Message.CODE.OPEN,
					Message.CODE.KEEPALIVE,
					Message.CODE.UPDATE,
					Message.CODE.ROUTE_REFRESH,
					Message.CODE.OPERATIONAL
				]:
					self.processes[_cli_name]['%s-%d' % (direction,message)] = False

		for name in self.processes.keys():
			process = self.processes[name]

			neighbor.api.set('neighbor-changes',process.get('neighbor-changes',False))

			for direction in ['send','receive']:
				for option in ['packets','consolidate','parsed']:
					neighbor.api.set_value(direction,option,process.get('%s-%s' % (direction,option),False))

				for message in [
					Message.CODE.NOTIFICATION,
					Message.CODE.OPEN,
					Message.CODE.KEEPALIVE,
					Message.CODE.UPDATE,
					Message.CODE.ROUTE_REFRESH,
					Message.CODE.OPERATIONAL
				]:
					neighbor.api.set_message(direction,message,process.get('%s-%d' % (direction,message),False))

		if not neighbor.router_id:
			neighbor.router_id = neighbor.local_address

		local_scope = scope[-1]
		neighbor.description = local_scope.get('description','')

		neighbor.md5 = local_scope.get('md5',None)
		neighbor.ttl = local_scope.get('ttl-security',None)
		neighbor.group_updates = local_scope.get('group-updates',None)

		neighbor.route_refresh = local_scope.get('route-refresh',0)
		neighbor.graceful_restart = local_scope.get('graceful-restart',0)
		if neighbor.graceful_restart is None:
			# README: Should it be a subclass of int ?
			neighbor.graceful_restart = int(neighbor.hold_time)
		neighbor.multisession = local_scope.get('multi-session',False)
		neighbor.operational = local_scope.get('capa-operational',False)
		neighbor.add_path = local_scope.get('add-path',0)
		neighbor.flush = local_scope.get('auto-flush',True)
		neighbor.adjribout = local_scope.get('adj-rib-out',True)
		neighbor.asn4 = local_scope.get('asn4',True)
		neighbor.aigp = local_scope.get('aigp',None)

		if neighbor.route_refresh and not neighbor.adjribout:
			self._error = 'incomplete option route-refresh and no adj-rib-out'
			if self.debug: raise Exception()  # noqa
			return False

		# XXX: check that if we have any message, we have parsed/packets
		# XXX: and vice-versa

		missing = neighbor.missing()
		if missing:
			self._error = 'incomplete neighbor, missing %s' % missing
			if self.debug: raise Exception()  # noqa(self._error)
			return False
		if neighbor.local_address.afi != neighbor.peer_address.afi:
			self._error = 'local-address and peer-address must be of the same family'
			if self.debug: raise Exception()  # noqa(self._error)
			return False
		if neighbor.peer_address.ip in self._neighbors:
			self._error = 'duplicate peer definition %s' % neighbor.peer_address.ip
			if self.debug: raise Exception()  # noqa(self._error)
			return False

		openfamilies = local_scope.get('families','everything')
		# announce every family we known
		if neighbor.multisession and openfamilies == 'everything':
			# announce what is needed, and no more, no need to have lots of TCP session doing nothing
			_families = set()
			for change in neighbor.changes:
				_families.add((change.nlri.afi,change.nlri.safi))
			families = list(_families)
		elif openfamilies in ('all','everything'):
			families = NLRI.known_families()
		# only announce what you have as routes
		elif openfamilies == 'minimal':
			_families = set()
			for change in neighbor.changes:
				_families.add((change.nlri.afi,change.nlri.safi))
			families = list(_families)
		else:
			families = openfamilies

		# check we are not trying to announce routes without the right MP announcement
		for family in neighbor.families():
			if family not in families:
				afi,safi = family
				self._error = 'Trying to announce a route of type %s,%s when we are not announcing the family to our peer' % (afi,safi)
				if self.debug: raise Exception()  # noqa
				return False

		# add the families to the list of families known
		initial_families = list(neighbor.families())
		for family in families:
			if family not in initial_families	:
				# we are modifying the data used by .families() here
				neighbor.add_family(family)

		if neighbor.group_updates is None:
			neighbor.group_updates = True

		def _init_neighbor (neighbor):
			families = neighbor.families()
			for change in neighbor.changes:
				if change.nlri.family() in families:
					# This add the family to neighbor.families()
					neighbor.rib.outgoing.insert_announced_watchdog(change)
			for message in messages:
				if message.family() in families:
					if message.name == 'ASM':
						neighbor.asm[message.family()] = message
					else:
						neighbor.messages.append(message)
			self._neighbors[neighbor.name()] = neighbor

		# create one neighbor object per family for multisession
		if neighbor.multisession and len(neighbor.families()) > 1:
			for family in neighbor.families():
				# XXX: FIXME: Ok, it works but it takes LOTS of memory ..
				m_neighbor = deepcopy(neighbor)
				m_neighbor.make_rib()
				m_neighbor.rib.outgoing.families = [family]
				_init_neighbor(m_neighbor)
		else:
			neighbor.make_rib()
			_init_neighbor(neighbor)

		# display configuration
		for line in str(neighbor).split('\n'):
			self.logger.configuration(line)
		self.logger.configuration("\n")

		# ...
		scope.pop(-1)
		return True

	def _multi_neighbor (self, scope, tokens):
		if len(tokens) != 1:
			self._error = 'syntax: neighbor <ip> { <options> }'
			if self.debug: raise Exception()  # noqa
			return False

		address = tokens[0]
		scope.append({})
		try:
			scope[-1]['peer-address'] = IP.create(address)
		except (IndexError,ValueError,socket.error):
			self._error = '"%s" is not a valid IP address' % address
			if self.debug: raise Exception()  # noqa
			return False
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
			if r is False:
				return False
			if r is None:
				return True

	#  Group Static ................

	def _multi_static (self, scope, tokens):
		if len(tokens) != 0:
			self._error = 'syntax: static { route; route; ... }'
			if self.debug: raise Exception()  # noqa
			return False
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

	def _multi_static_route (self, scope, tokens):
		if len(tokens) != 1:
			self._error = self.route.syntax
			if self.debug: raise Exception()  # noqa
			return False

		if not self.route.insert_static_route(scope,tokens):
			return False

		while True:
			r = self._dispatch(
				scope,'route',
				[],
				[
					'next-hop','origin','as-path','as-sequence','med','aigp',
					'local-preference','atomic-aggregate','aggregator',
					'path-information','community','originator-id','cluster-list',
					'extended-community','split','label','rd','route-distinguisher',
					'watchdog','withdraw','attribute'
				]
			)
			if r is False:
				return False
			if r is None:
				return self._split_last_route(scope)

	def _single_static_route (self, scope, tokens):
		if len(tokens) < 3:
			return False

		if not self.route.insert_static_route(scope,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)

			if command in ('withdraw','withdrawn'):
				if self.route.withdraw(scope,tokens):
					continue
				return False

			if len(tokens) < 1:
				return False

			if command in self._dispatch_route:
				if command in ('rd','route-distinguisher'):
					if self._dispatch_route[command](scope,tokens,SAFI.nlri_mpls):
						continue
				else:
					if self._dispatch_route[command](scope,tokens):
						continue
			else:
				return False
			return False

		if not self.route.check_static_route(scope):
			return False

		return self._split_last_route(scope)

	def _single_l2vpn_vpls (self, scope, tokens):
		# TODO: actual length?(like rd+lb+bo+ve+bs+rd; 14 or so)
		if len(tokens) < 10:
			return False

		if not self._insert_l2vpn_vpls(scope,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)
			if len(tokens) < 1:
				return False
			if command in self._dispatch_vpls:
				if command in ('rd','route-distinguisher'):
					if self._dispatch_vpls[command](scope,tokens,SAFI.vpls):
						continue
				else:
					if self._dispatch_vpls[command](scope,tokens):
						continue
			else:
				return False
			return False

		if not self._check_l2vpn_vpls(scope):
			return False
		return True

	# VPLS

	def _multi_l2vpn (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self._str_vpls_error
			if self.debug: raise Exception()  # noqa
			return False
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

	def _insert_l2vpn_vpls (self, scope, tokens=None):
		try:
			attributes = Attributes()
			change = Change(VPLS(None,None,None,None,None),attributes)
		except ValueError:
			self._error = self._str_vpls_error
			if self.debug: raise Exception()  # noqa
			return False

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(change)
		return True

	def _multi_l2vpn_vpls (self, scope, tokens):
		if len(tokens) > 1:
			self._error = self._str_vpls_error
			if self.debug: raise Exception()  # noqa
			return False

		if not self._insert_l2vpn_vpls(scope):
			return False

		while True:
			r = self._dispatch(
				scope,'l2vpn',
				[],
				[
					'next-hop','origin','as-path','med','local-preference',
					'community','originator-id','cluster-list','extended-community',
					'rd','route-distinguisher','withdraw',
					'endpoint','offset',
					'size','base'
				]
			)
			if r is False:
				return False
			if r is None:
				break

		return True

	# Group Flow  ........

	def _multi_flow (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

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

	def _insert_flow_route (self, scope, tokens=None):
		if self.flow.state != 'out':
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

		self.flow.state = 'match'

		try:
			attributes = Attributes()
			attributes[Attribute.CODE.EXTENDED_COMMUNITY] = ExtendedCommunities()
			flow = Change(Flow(),attributes)
		except ValueError:
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(flow)
		return True

	def _check_flow_route (self, scope):
		self.logger.configuration('warning: no check on flows are implemented')
		return True

	def _check_l2vpn_vpls (self, scope):
		nlri = scope[-1]['announce'][-1].nlri

		if nlri.ve is None:
			raise ValueError(self._str_vpls_bad_enpoint)

		if nlri.base is None:
			raise ValueError(self._str_vpls_bad_label)

		if nlri.offset is None:
			raise ValueError(self._str_vpls_bad_offset)

		if nlri.size is None:
			raise ValueError(self._str_vpls_bad_size)

		if nlri.base > (0xFFFFF - nlri.size):  # 20 bits, 3 bytes
			raise ValueError(self._str_vpls_bad_label)

		return True

	def _multi_flow_route (self, scope, tokens):
		if len(tokens) > 1:
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

		if not self._insert_flow_route(scope):
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
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

		return True

	def _l2vpn_vpls_endpoint (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_enpoint)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.ve = number
		return True

	def _l2vpn_vpls_size (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_size)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.size = number
		return True

	def _l2vpn_vpls_offset (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_offset)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.offset = number
		return True

	def _l2vpn_vpls_base (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			raise ValueError(self._str_vpls_bad_label)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.base = number
		return True

	# ..........................................

	def _multi_match (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

		if self.flow.state != 'match':
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

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

	def _multi_then (self, scope, tokens):
		if len(tokens) != 0:
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

		if self.flow.state != 'then':
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

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

	def _multi_api (self, scope, direction, tokens):
		if len(tokens) != 0:
			self._error = self.flow.syntax
			if self.debug: raise Exception()  # noqa
			return False

		while True:
			r = self._dispatch(
				scope,direction,
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

	def _multi_operational (self, scope, tokens):
		if len(tokens) != 0:
			self._error = 'syntax: operational { command; command; ... }'
			if self.debug: raise Exception()  # noqa
			return False
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

	def _single_operational_asm (self, scope, value):
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
			self._error = 'invalid operational syntax, wrong number of arguments'
			return False

		data = {}

		while tokens and parameters:
			command = tokens.pop(0).lower()
			value = tokens.pop(0)

			if command == 'router-id':
				if isipv4(value):
					data['routerid'] = RouterID(value)
				else:
					self._error = 'invalid operational value for %s' % command
					return False
				continue

			expected = parameters.pop(0)

			if command != expected:
				self._error = 'invalid operational syntax, unknown argument %s' % command
				return False
			if not validate.get(command,valid)(value):
				self._error = 'invalid operational value for %s' % command
				return False

			data[command] = convert[command](value)

		if tokens or parameters:
			self._error = 'invalid advisory syntax, missing argument(s) %s' % ', '.join(parameters)
			return False

		if 'routerid' not in data:
			data['routerid'] = None

		if 'operational-message' not in scope[-1]:
			scope[-1]['operational-message'] = []

		# iterate on each family for the peer if multiprotocol is set.
		scope[-1]['operationa-messagel'].append(klass(**data))
		return True
