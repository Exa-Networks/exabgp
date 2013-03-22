# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import sys
import stat
import time

from pprint import pformat
from copy import deepcopy
from struct import pack,unpack

from exabgp.structure.environment import environment

from exabgp.protocol.family import AFI,SAFI,known_families

from exabgp.bgp.neighbor import Neighbor

from exabgp.protocol import NamedProtocol
from exabgp.protocol.ip.inet import Inet,inet
from exabgp.protocol.ip.icmp import NamedICMPType,NamedICMPCode
from exabgp.protocol.ip.fragment import NamedFragment
from exabgp.protocol.ip.tcp.flags import NamedTCPFlags

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID

from exabgp.bgp.message.update.nlri.route import Route,NLRI,PathInfo,Labels,RouteDistinguisher,pack_int
from exabgp.bgp.message.update.nlri.flow import BinaryOperator,NumericOperator,Flow,Source,Destination,SourcePort,DestinationPort,AnyPort,IPProtocol,TCPFlag,Fragment,PacketLength,ICMPType,ICMPCode,DSCP

from exabgp.bgp.message.update.attribute.id import AttributeID
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.nexthop import cachedNextHop
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.communities import Community,cachedCommunity,Communities,ECommunity,ECommunities,to_ExtendedCommunity,to_FlowTrafficRate,to_FlowRedirectASN,to_FlowRedirectIP
from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
from exabgp.bgp.message.update.attribute.clusterlist import ClusterList

from exabgp.structure.log import Logger

# Duck class, faking part of the Attribute interface
# We add this to routes when when need o split a route in smaller route
# The value stored is the longer netmask we want to use
# As this is not a real BGP attribute this stays in the configuration file

class Split (int):
	ID = AttributeID.INTERNAL_SPLIT
	MULTIPLE = False


class Watchdog (str):
	ID = AttributeID.INTERNAL_WATCHDOG
	MULTIPLE = False

class Withdrawn (object):
	ID = AttributeID.INTERNAL_WITHDRAW
	MULTIPLE = False


def convert_length (data):
	number = int(data)
	if number > 65535:
		raise ValueError(Configuration._str_bad_length)
	return number

def convert_port (data):
	number = int(data)
	if number < 0 or number > 65535:
		raise ValueError(Configuration._str_bad_port)
	return number

def convert_dscp (data):
	number = int(data)
	if number < 0 or number > 65535:
		raise ValueError(Configuration._str_bad_dscp)
	return number


class Configuration (object):
	TTL_SECURITY = 255

#	'  hold-time 180;\n' \

	_str_bad_length = "cloudflare already found that invalid max-packet length for for you .."
	_str_bad_flow = "you tried to filter a flow using an invalid port for a component .."
	_str_bad_dscp = "you tried to filter a flow using an invalid dscp for a component .."

	_str_route_error = \
	'community, extended-communities and as-path can take a single community as parameter.\n' \
	'only next-hop is mandatory\n' \
	'\n' \
	'syntax:\n' \
	'route 10.0.0.1/22 {\n' \
	'  path-information 0.0.0.1;\n' \
	'  route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535' \
	'  next-hop 192.0.1.254;\n' \
	'  origin IGP|EGP|INCOMPLETE;\n' \
	'  as-path [ AS-SEQUENCE-ASN1 AS-SEQUENCE-ASN2 ( AS-SET-ASN3 )] ;\n' \
	'  med 100;\n' \
	'  local-preference 100;\n' \
	'  atomic-aggregate;\n' \
	'  community [ 65000 65001 65002 ];\n' \
	'  extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 ]\n' \
	'  originator-id 10.0.0.10;\n' \
	'  cluster-list [ 10.10.0.1 10.10.0.2 ];\n' \
	'  label [ 100 200 ];\n' \
	'  aggregator ( 65000:10.0.0.10 )\n' \
	'  split /24\n' \
	'  watchdog watchdog-name\n' \
	'  withdraw\n' \
	'}\n' \
	'\n' \
	'syntax:\n' \
	'route 10.0.0.1/22' \
	' path-information 0.0.0.1' \
	' route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535' \
	' next-hop 192.0.2.1' \
	' origin IGP|EGP|INCOMPLETE' \
	' as-path AS-SEQUENCE-ASN' \
	' med 100' \
	' local-preference 100' \
	' atomic-aggregate' \
	' community 65000' \
	' extended-community target:1234:5.6.7.8' \
	' originator-id 10.0.0.10' \
	' cluster-list 10.10.0.1' \
	' label 150' \
	' aggregator' \
	' split /24' \
	' watchdog watchdog-name' \
	' withdraw' \
	';\n' \

	_str_flow_error = \
	'syntax: flow {\n' \
	'          match {\n' \
	'             source 10.0.0.0/24;\n' \
	'             destination 10.0.1.0/24;\n' \
	'             port 25;\n' \
	'             source-port >1024\n' \
	'             destination-port =80 =3128 >8080&<8088;\n' \
	'             protocol [ udp tcp ];\n' \
	'             fragment [ not-a-fragment dont-fragment is-fragment first-fragment last-fragment ];\n' \
	'             packet-length >200&<300 >400&<500;'
	'          }\n' \
	'          then {\n' \
	'             discard;\n' \
	'             rate-limit 9600;\n' \
	'             redirect 30740:12345;\n' \
	'             redirect 1.2.3.4:5678;\n' \
	'          }\n' \
	'        }\n\n' \
	'one or more match term, one action\n' \
	'fragment code is totally untested\n' \

	_str_process_error = \
	'syntax: process name-of-process {\n' \
	'          run /path/to/command with its args;\n' \
	'        }\n\n' \

	_str_family_error = \
	'syntax: family {\n' \
	'          all;       # default if not family block is present, announce all we know\n' \
	'          minimal    # use the AFI/SAFI required to announce the routes in the configuration\n' \
	'          \n' \
	'          [inet|inet4] unicast;\n' \
	'          [inet|inet4] multicast;\n' \
	'          [inet|inet4] nlri-mpls;\n' \
	'          [inet|inet4] mpls-vpn;\n' \
	'          [inet|inet4] flow-vpnv4;\n' \
	'          inet6 unicast;\n' \
	'        }\n'

	_str_capa_error = \
	'syntax: capability {\n' \
	'          asn4 enable|disable;\n' \
	'          add-path disable|send|receive|send/receive;\n' \
	'        }\n'

	def __init__ (self,fname,text=False):
		self.debug = environment.settings().debug.configuration
		self.api_encoder = environment.settings().api.encoder

		self.logger = Logger()
		self._text = text
		self._fname = fname
		self._clear()

	def _clear (self):
		self.process = {}
		self.neighbor = {}
		self.error = ''
		self._neighbor = {}
		self._scope = []
		self._location = ['root']
		self._line = []
		self._error = ''
		self._number = 1
		self._flow_state = 'out'

	# Public Interface

	def reload (self):
		try:
			return self._reload()
		except KeyboardInterrupt:
			self.error = 'configuration reload aborted by ^C or SIGINT'
			return False

	def _reload (self):
		if self._text:
			self._tokens = self._tokenise(self._fname.split('\n'))
		else:
			try:
				f = open(self._fname,'r')
				self._tokens = self._tokenise(f)
				f.close()
			except IOError,e:
				error = str(e)
				if error.count(']'):
					self.error = error.split(']')[1].strip()
				else:
					self.error = error
				if self.debug: raise
				return False

		self._clear()

		r = False
		while not self.finished():
			r = self._dispatch(self._scope,'configuration',['group','neighbor'],[])
			if r is False: break

		if r not in [True,None]:
			self.error = "\nsyntax error in section %s\nline %d : %s\n\n%s" % (self._location[-1],self.number(),self.line(),self._error)
			return False

		self.neighbor = self._neighbor

		if environment.settings().debug.route:
			self.decode(environment.settings().debug.route)
			sys.exit(0)

		if environment.settings().debug.selfcheck:
			self.selfcheck()
			sys.exit(0)

		return True

	def parse_api_route (self,command):
		tokens = self._cleaned(command).split(' ')[1:]
		if len(tokens) < 4:
			return False
		if tokens[0] != 'route':
			return False
		scope = [{}]
		if not self._single_static_route(scope,tokens[1:]):
			return None
		return scope[0]['routes']

	def parse_api_flow (self,command):
		self._tokens = self._tokenise(' '.join(self._cleaned(command).split(' ')[2:]).split('\\n'))
		scope = [{}]
		if not self._dispatch(scope,'flow',['route',],[]):
			return None
		if not self._check_flow_route(scope):
			return None
		return scope[0]['routes']

	def add_route_all_peers (self,route):
		for neighbor in self.neighbor:
			self.neighbor[neighbor].add_route(route)

	def remove_route_all_peers (self,route):
		result = False
		for neighbor in self.neighbor:
			if self.neighbor[neighbor].remove_route(route):
				result = True
		return result

	# Tokenisation

	def _cleaned (self,line):
		return line.strip().replace('\t',' ').replace(']',' ]').replace('[','[ ').replace(')',' )').replace('(','( ').lower()

	def _tokenise (self,text):
		r = []
		config = ''
		for line in text:
			self.logger.configuration('loading | %s' % line.rstrip())
			replaced = self._cleaned(line)
			config += line
			if not replaced:
				continue
			if replaced.startswith('#'):
				continue
			if replaced[:3] == 'md5':
				password = line.strip()[3:].strip()
				if password[-1] == ';':
					password = password[:-1]
				r.append(['md5',password,';'])
			else:
				r.append([t for t in replaced[:-1].split(' ') if t] + [replaced[-1]])
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
	def _dispatch (self,scope,name,multi,single):
		try:
			tokens = self.tokens()
		except IndexError:
			self._error = 'configuration file incomplete (most likely missing })'
			if self.debug: raise
			return False
		self.logger.configuration('analysing tokens %s ' % str(tokens))
		self.logger.configuration('  valid block options %s' % str(multi))
		self.logger.configuration('  valid parameters    %s' % str(single))
		end = tokens[-1]
		if multi and end == '{':
			self._location.append(tokens[0])
			return self._multi_line(scope,name,tokens[:-1],multi)
		if single and end == ';':
			return self._single_line(scope,name,tokens[:-1],single)
		if end == '}':
			if len(self._location) == 1:
				self._error = 'closing too many parenthesis'
				if self.debug: raise
				return False
			self._location.pop(-1)
			return None
		return False

	def _multi_line (self,scope,name,tokens,valid):
		command = tokens[0]

		if valid and command not in valid:
			self._error = 'option %s in not valid here' % command
			if self.debug: raise
			return False

		if name == 'configuration':
			if command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if command == 'group':
				if len(tokens) != 2:
					self._error = 'syntax: group <name> { <options> }'
					if self.debug: raise
					return False
				return self._multi_group(scope,tokens[1])

		if name == 'group':
			if command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if command == 'static': return self._multi_static(scope,tokens[1:])
			if command == 'flow': return self._multi_flow(scope,tokens[1:])
			if command == 'process': return self._multi_process(scope,tokens[1:])
			if command == 'family': return self._multi_family(scope,tokens[1:])
			if command == 'capability': return self._multi_capability(scope,tokens[1:])

		if name == 'neighbor':
			if command == 'static': return self._multi_static(scope,tokens[1:])
			if command == 'flow': return self._multi_flow(scope,tokens[1:])
			if command == 'process': return self._multi_process(scope,tokens[1:])
			if command == 'family': return self._multi_family(scope,tokens[1:])
			if command == 'capability': return self._multi_capability(scope,tokens[1:])

		if name == 'static':
			if command == 'route':
				if self._multi_static_route(scope,tokens[1:]):
					return self._check_static_route(scope)
				return False

		if name == 'flow':
			if command == 'route':
				if self._multi_flow_route(scope,tokens[1:]):
					return self._check_flow_route(scope)
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
		return False

	def _single_line (self,scope,name,tokens,valid):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'invalid keyword "%s"' % command
			if self.debug: raise
			return False

		elif name == 'route':
			if command == 'origin': return self._route_origin(scope,tokens[1:])
			if command == 'as-path': return self._route_aspath(scope,tokens[1:])
			# For legacy with version 2.0.x
			if command == 'as-sequence': return self._route_aspath(scope,tokens[1:])
			if command == 'med': return self._route_med(scope,tokens[1:])
			if command == 'next-hop': return self._route_next_hop(scope,tokens[1:])
			if command == 'local-preference': return self._route_local_preference(scope,tokens[1:])
			if command == 'atomic-aggregate': return self._route_atomic_aggregate(scope,tokens[1:])
			if command == 'aggregator': return self._route_aggregator(scope,tokens[1:])
			if command == 'path-information': return self._route_path_information(scope,tokens[1:])
			if command == 'originator-id': return self._route_originator_id(scope,tokens[1:])
			if command == 'cluster-list': return self._route_cluster_list(scope,tokens[1:])
			if command == 'split': return self._route_split(scope,tokens[1:])
			if command == 'label': return self._route_label(scope,tokens[1:])
			if command in ('rd','route-distinguisher'): return self._route_rd(scope,tokens[1:])
			if command == 'watchdog': return self._route_watchdog(scope,tokens[1:])
			# withdrawn is here to not break legacy code
			if command in ('withdraw','withdrawn'): return self._route_withdraw(scope,tokens[1:])

			if command == 'community': return self._route_community(scope,tokens[1:])
			if command == 'extended-community': return self._route_extended_community(scope,tokens[1:])

		elif name == 'flow-match':
			if command == 'source': return self._flow_source(scope,tokens[1:])
			if command == 'destination': return self._flow_destination(scope,tokens[1:])
			if command == 'port': return self._flow_route_anyport(scope,tokens[1:])
			if command == 'source-port': return self._flow_route_source_port(scope,tokens[1:])
			if command == 'destination-port': return self._flow_route_destination_port(scope,tokens[1:])
			if command == 'protocol': return self._flow_route_protocol(scope,tokens[1:])
			if command == 'tcp-flags': return self._flow_route_tcp_flags(scope,tokens[1:])
			if command == 'icmp-type': return self._flow_route_icmp_type(scope,tokens[1:])
			if command == 'icmp-code': return self._flow_route_icmp_code(scope,tokens[1:])
			if command == 'fragment': return self._flow_route_fragment(scope,tokens[1:])
			if command == 'dscp': return self._flow_route_dscp(scope,tokens[1:])
			if command == 'packet-length': return self._flow_route_packet_length(scope,tokens[1:])

		elif name == 'flow-then':
			if command == 'discard': return self._flow_route_discard(scope,tokens[1:])
			if command == 'rate-limit': return self._flow_route_rate_limit(scope,tokens[1:])
			if command == 'redirect': return self._flow_route_redirect(scope,tokens[1:])

			if command == 'community': return self._route_community(scope,tokens[1:])
			if command == 'extended-community': return self._route_extended_community(scope,tokens[1:])

		if name in ('neighbor','group'):
			if command == 'description': return self._set_description(scope,tokens[1:])
			if command == 'router-id': return self._set_router_id(scope,'router-id',tokens[1:])
			if command == 'local-address': return self._set_ip(scope,'local-address',tokens[1:])
			if command == 'local-as': return self._set_asn(scope,'local-as',tokens[1:])
			if command == 'peer-as': return self._set_asn(scope,'peer-as',tokens[1:])
			if command == 'hold-time': return self._set_holdtime(scope,'hold-time',tokens[1:])
			if command == 'md5': return self._set_md5(scope,'md5',tokens[1:])
			if command == 'ttl-security': return self._set_ttl(scope,'ttl-security',tokens[1:])
			if command == 'group-updates': return self._set_group_updates(scope,'group-updates',tokens[1:])
			# deprecated
			if command == 'route-refresh': return self._set_routerefresh(scope,'route-refresh',tokens[1:])
			if command == 'graceful-restart': return self._set_gracefulrestart(scope,'graceful-restart',tokens[1:])
			if command == 'multi-session': return self._set_multisession(scope,'multi-session',tokens[1:])
			if command == 'add-path': return self._set_addpath(scope,'add-path',tokens[1:])

		elif name == 'family':
			if command == 'inet': return self._set_family_inet4(scope,tokens[1:])
			if command == 'inet4': return self._set_family_inet4(scope,tokens[1:])
			if command == 'inet6': return self._set_family_inet6(scope,tokens[1:])
			if command == 'minimal': return self._set_family_minimal(scope,tokens[1:])
			if command == 'all': return self._set_family_all(scope,tokens[1:])

		elif name == 'capability':
			if command == 'route-refresh': return self._set_routerefresh(scope,'route-refresh',tokens[1:])
			if command == 'graceful-restart': return self._set_gracefulrestart(scope,'graceful-restart',tokens[1:])
			if command == 'multi-session': return self._set_multisession(scope,'multi-session',tokens[1:])
			if command == 'add-path': return self._set_addpath(scope,'add-path',tokens[1:])
			if command == 'asn4': return self._set_asn4(scope,'asn4',tokens[1:])

		elif name == 'process':
			if command == 'run': return self._set_process_run(scope,'process-run',tokens[1:])
			# legacy ...
			if command == 'parse-routes':
				self._set_process_command(scope,'neighbor-changes',tokens[1:])
				self._set_process_command(scope,'receive-routes',tokens[1:])
				return True
			# legacy ...
			if command == 'peer-updates':
				self._set_process_command(scope,'neighbor-changes',tokens[1:])
				self._set_process_command(scope,'receive-routes',tokens[1:])
				return True
			# new interface
			if command == 'encoder': return self._set_process_encoder(scope,'encoder',tokens[1:])
			if command == 'receive-packets': return self._set_process_command(scope,'receive-packets',tokens[1:])
			if command == 'send-packets': return self._set_process_command(scope,'send-packets',tokens[1:])
			if command == 'receive-routes': return self._set_process_command(scope,'receive-routes',tokens[1:])
			if command == 'neighbor-changes': return self._set_process_command(scope,'neighbor-changes',tokens[1:])

		elif name == 'static':
			if command == 'route': return self._single_static_route(scope,tokens[1:])

		return False

	# Programs used to control exabgp

	def _multi_process (self,scope,tokens):
		while True:
			r = self._dispatch(scope,'process',[],['run','encoder','receive-packets','send-packets','receive-routes','neighbor-changes',  'peer-updates','parse-routes'])
			if r is False: return False
			if r is None: break

		name = tokens[0] if len(tokens) >= 1 else 'conf-only-%s' % str(time.time())[-6:]
		self.process.setdefault(name,{})['neighbor'] = scope[-1]['peer-address'] if 'peer-address' in scope[-1] else '*'

		run = scope[-1].pop('process-run','')
		if run:
			if len(tokens) != 1:
				self._error = self._str_process_error
				if self.debug: raise
				return False
			self.process[name]['encoder'] = scope[-1].get('encoder','') or self.api_encoder
			self.process[name]['run'] = run
			return True
		elif len(tokens):
			self._error = self._str_process_error
			if self.debug: raise
			return False

	def _set_process_command (self,scope,command,value):
		scope[-1][command] = True
		return True

	def _set_process_encoder (self,scope,command,value):
		if value and value[0] in ('text','json'):
			scope[-1][command] = value[0]
			return True

		self._error = self._str_process_error
		if self.debug: raise
		return False

	def _set_process_run (self,scope,command,value):
		line = ' '.join(value).strip()
		if len(line) > 2 and line[0] == line[-1] and line[0] in ['"',"'"]:
			line = line[1:-1]
		if ' ' in line:
			prg,args = line.split(' ',1)
		else:
			prg = line
			args = ''

		if not prg:
			self._error = 'prg requires the program to prg as an argument (quoted or unquoted)'
			if self.debug: raise
			return False
		if prg[0] != '/':
			if prg.startswith('etc/exabgp'):
				parts = prg.split('/')
				path = [os.environ.get('ETC','etc'),] + parts[2:]
				prg = os.path.join(*path)
			else:
				prg = os.path.abspath(os.path.join(os.path.dirname(self._fname),prg))
		if not os.path.exists(prg):
			self._error = 'can not locate the the program "%s"' % prg
			if self.debug: raise
			return False

		# XXX: Yep, race conditions are possible, those are sanity checks not security ones ...
		s = os.stat(prg)

		if stat.S_ISDIR(s.st_mode):
			self._error = 'can not execute directories "%s"' % prg
			if self.debug: raise
			return False

		if s.st_mode & stat.S_ISUID:
			self._error = 'refusing to run setuid programs "%s"' % prg
			if self.debug: raise
			return False

		check = stat.S_IXOTH
		if s.st_uid == os.getuid():
			check |= stat.S_IXUSR
		if s.st_gid == os.getgid():
			check |= stat.S_IXGRP

		if not check & s.st_mode:
			self._error = 'exabgp will not be able to run this program "%s"' % prg
			if self.debug: raise
			return False

		if args:
			scope[-1][command] = [prg] + args.split(' ')
		else:
			scope[-1][command] = [prg,]
		return True

	# Limit the AFI/SAFI pair announced to peers

	def _multi_family (self,scope,tokens):
		# we know all the families we should use
		self._family = False
		scope[-1]['families'] = []
		while True:
			r = self._dispatch(scope,'family',[],['inet','inet4','inet6','minimal','all'])
			if r is False: return False
			if r is None: break
		self._family = False
		return True

	def _set_family_inet4 (self,scope,tokens):
		if self._family:
			self._error = 'inet/inet4 can not be used with all or minimal'
			if self.debug: raise
			return False

		safi = tokens.pop(0)
		if safi == 'unicast':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))
		elif safi == 'multicast':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.multicast)))
		elif safi == 'nlri-mpls':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.nlri_mpls)))
		elif safi == 'mpls-vpn':
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.mpls_vpn)))
		elif safi in ('flow-vpnv4','flow'):
			scope[-1]['families'].append((AFI(AFI.ipv4),SAFI(SAFI.flow_ipv4)))
		else:
			return False
		return True

	def _set_family_inet6 (self,scope,tokens):
		if self._family:
			self._error = 'inet6 can not be used with all or minimal'
			if self.debug: raise
			return False

		safi = tokens.pop(0)
		if safi == 'unicast':
			scope[-1]['families'].append((AFI(AFI.ipv6),SAFI(SAFI.unicast)))
		elif safi == 'mpls-vpn':
			scope[-1]['families'].append((AFI(AFI.ipv6),SAFI(SAFI.mpls_vpn)))
		else:
			return False
		return True

	def _set_family_minimal (self,scope,tokens):
		if scope[-1]['families']:
			self._error = 'minimal can not be used with any other options'
			if self.debug: raise
			return False
		scope[-1]['families'] = 'minimal'
		self._family = True
		return True

	def _set_family_all (self,scope,tokens):
		if scope[-1]['families']:
			self._error = 'all can not be used with any other options'
			if self.debug: raise
			return False
		scope[-1]['families'] = 'all'
		self._family = True
		return True

	# capacity

	def _multi_capability (self,scope,tokens):
		# we know all the families we should use
		self._capability = False
		while True:
			r = self._dispatch(scope,'capability',[],['route-refresh','graceful-restart','multi-session','add-path','asn4'])
			if r is False: return False
			if r is None: break
		return True

	def _set_routerefresh (self,scope,command,value):
		scope[-1][command] = True
		return True

	def _set_gracefulrestart (self,scope,command,value):
		if not len(value):
			scope[-1][command] = None
			return True
		try:
			# README: Should it be a subclass of int ?
			grace = int(value[0])
			if grace < 0:
				raise ValueError('graceful-restart can not be negative')
			if grace >= pow(2,16):
				raise ValueError('graceful-restart must be smaller than %d' % pow(2,16))
			scope[-1][command] = grace
			return True
		except ValueError:
			self._error = '"%s" is an invalid graceful-restart time' % ' '.join(value)
			if self.debug: raise
			return False
		return True

	def _set_multisession (self,scope,command,value):
		scope[-1][command] = True
		return True

	def _set_addpath (self,scope,command,value):
		try:
			ap = value[0].lower()
			apv = 0
			if ap.endswith('receive'):
				apv += 1
			if ap.startswith('send'):
				apv += 2
			if not apv and ap not in ('disable','disabled'):
				raise ValueError('invalid add-path')
			scope[-1][command] = apv
			return True
		except ValueError:
			self._error = '"%s" is an invalid add-path' % ' '.join(value)
			if self.debug: raise
			return False

	def _set_asn4 (self,scope,command,value):
		try:
			if not value:
				scope[-1][command] = True
				return True
			asn4 = value[0].lower()
			if asn4 in ('disable','disabled'):
				scope[-1][command] = False
				return True
			if asn4 in ('enable','enabled'):
				scope[-1][command] = True
				return True
			self._error = '"%s" is an invalid asn4 parameter options are enable (default) and disable)' % ' '.join(value)
			return False
		except ValueError:
			self._error = '"%s" is an invalid asn4 parameter options are enable (default) and disable)' % ' '.join(value)
			if self.debug: raise
			return False


	# route grouping with watchdog

	def _route_watchdog (self,scope,tokens):
		w = tokens.pop(0)
		if w.lower() in ['announce','withdraw']:
			raise ValueError('invalid watchdog name %s' % w)
		try:
			scope[-1]['routes'][-1].attributes.add(Watchdog(w))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_withdraw (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(Withdrawn())
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	# Group Neighbor

	def _multi_group (self,scope,address):
		scope.append({})
		while True:
			r = self._dispatch(scope,'group',['static','flow','neighbor','process','family','capability'],['description','router-id','local-address','local-as','peer-as','hold-time','add-path','graceful-restart','md5','ttl-security','multi-session','group-updates','route-refresh','asn4'])
			if r is False:
				return False
			if r is None:
				scope.pop(-1)
				return True

	def _make_neighbor (self,scope):
		# we have local_scope[-2] as the group template and local_scope[-1] as the peer specific
		if len(scope) > 1:
			for key,content in scope[-2].iteritems():
				if key not in scope[-1]:
					scope[-1][key] = deepcopy(content)

		self.logger.configuration("\nPeer configuration complete :")
		for _key in scope[-1].keys():
			stored = scope[-1][_key]
			if hasattr(stored,'__iter__'):
				for category in scope[-1][_key]:
					for _line in pformat(str(category),3,3,3).split('\n'):
						self.logger.configuration("   %s: %s" %(_key,_line))
			else:
				for _line in pformat(str(stored),3,3,3).split('\n'):
					self.logger.configuration("   %s: %s" %(_key,_line))
		self.logger.configuration("\n")

		neighbor = Neighbor()
		for local_scope in scope:
			v = local_scope.get('router-id','')
			if v: neighbor.router_id = v
			v = local_scope.get('peer-address','')
			if v: neighbor.peer_address = v
			v = local_scope.get('local-address','')
			if v: neighbor.local_address = v
			v = local_scope.get('local-as','')
			if v: neighbor.local_as = v
			v = local_scope.get('peer-as','')
			if v: neighbor.peer_as = v
			v = local_scope.get('hold-time','')
			if v: neighbor.hold_time = v

			v = local_scope.get('routes',[])
			for route in v:
				# This add the family to neighbor.families()
				neighbor.add_route(route)

		for local_scope in (scope[0],scope[-1]):
			neighbor.api.receive_packets |= local_scope.get('receive-packets',False)
			neighbor.api.send_packets |= local_scope.get('send-packets',False)
			neighbor.api.receive_routes |= local_scope.get('receive-routes',False)
			neighbor.api.neighbor_changes |= local_scope.get('neighbor-changes',False)

		local_scope = scope[-1]
		neighbor.description = local_scope.get('description','')

		neighbor.md5 = local_scope.get('md5',None)
		neighbor.ttl = local_scope.get('ttl-security',None)
		neighbor.group_updates = local_scope.get('group-updates',False)

		neighbor.route_refresh = local_scope.get('route-refresh',0)
		neighbor.graceful_restart = local_scope.get('graceful-restart',0)
		if neighbor.graceful_restart is None:
			# README: Should it be a subclass of int ?
			neighbor.graceful_restart = int(neighbor.hold_time)
		neighbor.multisession = local_scope.get('multi-session',False)
		neighbor.add_path = local_scope.get('add-path','')
		neighbor.asn4 = local_scope.get('asn4',True)

		missing = neighbor.missing()
		if missing:
			self._error = 'incomplete neighbor, missing %s' % missing
			if self.debug: raise
			return False
		if neighbor.local_address.afi != neighbor.peer_address.afi:
			self._error = 'local-address and peer-address must be of the same family'
			if self.debug: raise
			return False
		if neighbor.peer_address.ip in self._neighbor:
			self._error = 'duplicate peer definition %s' % neighbor.peer_address.ip
			if self.debug: raise
			return False

		openfamilies = local_scope.get('families','everything')
		# announce every family we known
		if neighbor.multisession and openfamilies == 'everything':
			# announce what is needed, and no more, no need to have lots of TCP session doing nothing
			families = neighbor.families()
		elif openfamilies in ('all','everything'):
			families = known_families()
		# only announce what you have as routes
		elif openfamilies == 'minimal':
			families = neighbor.families()
		else:
			families = openfamilies

		# check we are not trying to announce routes without the right MP announcement
		for family in neighbor.families():
			if family not in families:
				afi,safi = family
				self._error = 'Trying to announce a route of type %s,%s when we are not announcing the family to our peer' % (afi,safi)
				if self.debug: raise
				return False

		# add the families to the list of families known
		initial_families = list(neighbor.families())
		for family in families:
			if family not in initial_families	:
				# we are modifying the data used by .families() here
				neighbor.add_family(family)

		# create one neighbor object per family for multisession
		if neighbor.multisession:
			for family in neighbor.families():
				m_neighbor = deepcopy(neighbor)
				for f in neighbor.families():
					if f == family:
						continue
					m_neighbor.remove_family_and_routes(f)
				self._neighbor[m_neighbor.name()] = m_neighbor
		else:
			self._neighbor[neighbor.name()] = neighbor

		for line in str(neighbor).split('\n'):
			self.logger.configuration(line)
		self.logger.configuration("\n")

		return True


	def _multi_neighbor (self,scope,tokens):
		if len(tokens) != 1:
			self._error = 'syntax: neighbor <ip> { <options> }'
			if self.debug: raise
			return False

		address = tokens[0]
		scope.append({})
		try:
			scope[-1]['peer-address'] = Inet(*inet(address))
		except:
			self._error = '"%s" is not a valid IP address' % address
			if self.debug: raise
			return False
		while True:
			r = self._dispatch(scope,'neighbor',['static','flow','process','family','capability'],['description','router-id','local-address','local-as','peer-as','hold-time','add-path','graceful-restart','md5','ttl-security','multi-session','group-updates','asn4'])
			if r is False: return False
			if r is None: return True

	# Command Neighbor

	def _set_router_id (self,scope,command,value):
		try:
			ip = RouterID(value[0])
		except (IndexError,ValueError):
			self._error = '"%s" is an invalid IP address' % ' '.join(value)
			if self.debug: raise
			return False
		scope[-1][command] = ip
		return True

	def _set_description (self,scope,tokens):
		text = ' '.join(tokens)
		if len(text) < 2 or text[0] != '"' or text[-1] != '"' or text[1:-1].count('"'):
			self._error = 'syntax: description "<description>"'
			if self.debug: raise
			return False
		scope[-1]['description'] = text[1:-1]
		return True

	# will raise ValueError if the ASN is not correct
	def _newASN (self,value):
		if value.count('.'):
			high,low = value.split('.',1)
			asn = (int(high) << 16) + int(low)
		else:
			asn = int(value)
		return ASN(asn)

	def _set_asn (self,scope,command,value):
		try:
			scope[-1][command] = self._newASN(value[0])
			return True
		except ValueError:
			self._error = '"%s" is an invalid ASN' % ' '.join(value)
			if self.debug: raise
			return False

	def _set_ip (self,scope,command,value):
		try:
			ip = Inet(*inet(value[0]))
		except (IndexError,ValueError):
			self._error = '"%s" is an invalid IP address' % ' '.join(value)
			if self.debug: raise
			return False
		scope[-1][command] = ip
		return True

	def _set_holdtime (self,scope,command,value):
		try:
			holdtime = HoldTime(value[0])
			if holdtime < 3 and holdtime != 0:
				raise ValueError('holdtime must be zero or at least three seconds')
			if holdtime >= pow(2,16):
				raise ValueError('holdtime must be smaller than %d' % pow(2,16))
			scope[-1][command] = holdtime
			return True
		except ValueError:
			self._error = '"%s" is an invalid hold-time' % ' '.join(value)
			if self.debug: raise
			return False

	def _set_md5 (self,scope,command,value):
		md5 = value[0]
		if len(md5) > 2 and md5[0] == md5[-1] and md5[0] in ['"',"'"]:
			md5 = md5[1:-1]
		if len(md5) > 80:
			self._error = 'md5 password must be no larger than 80 characters'
			if self.debug: raise
			return False
		if not md5:
			self._error = 'md5 requires the md5 password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.'
			if self.debug: raise
			return False
		scope[-1][command] = md5
		return True

	def _set_ttl (self,scope,command,value):
		if not len(value):
			scope[-1][command] = self.TTL_SECURITY
			return True
		try:
			# README: Should it be a subclass of int ?
			ttl = int(value[0])
			if ttl < 0:
				raise ValueError('ttl-security can not be negative')
			if ttl >= 255:
				raise ValueError('ttl must be smaller than 256')
			scope[-1][command] = ttl
			return True
		except ValueError:
			self._error = '"%s" is an invalid ttl-security' % ' '.join(value)
			if self.debug: raise
			return False
		return True

	def _set_group_updates (self,scope,command,value):
		scope[-1][command] = True
		return True

	#  Group Static ................

	def _multi_static (self,scope,tokens):
		if len(tokens) != 0:
			self._error = 'syntax: static { route; route; ... }'
			if self.debug: raise
			return False
		while True:
			r = self._dispatch(scope,'static',['route',],['route',])
			if r is False: return False
			if r is None: return True

	# Group Route  ........

	def _split_last_route (self,scope):
		# if the route does not need to be broken in smaller routes, return
		route = scope[-1]['routes'][-1]
		if not AttributeID.INTERNAL_SPLIT in route.attributes:
			return True

		# ignore if the request is for an aggregate, or the same size
		mask = route.nlri.mask
		split = route.attributes[AttributeID.INTERNAL_SPLIT]
		if mask >= split:
			return True

		# get a local copy of the route
		route = scope[-1]['routes'].pop(-1)

		# calculate the number of IP in the /<size> of the new route
		increment = pow(2,(len(route.nlri.packed)*8) - split)
		# how many new routes are we going to create from the initial one
		number = pow(2,split - route.nlri.mask)

		# convert the IP into a integer/long
		ip = 0
		for c in route.nlri.packed:
			ip = ip << 8
			ip += ord(c)

		afi = route.nlri.afi
		safi = route.nlri.safi
		# Really ugly
		labels = route.nlri.labels
		rd = route.nlri.rd
		path_info = route.nlri.path_info

		route.mask = split
		route.nlri = None
		# generate the new routes
		for _ in range(number):
			r = deepcopy(route)
			# update ip to the next route, this recalculate the "ip" field of the Inet class
			r.nlri = NLRI(afi,safi,pack_int(afi,ip,split),split)
			r.nlri.labels = labels
			r.nlri.rd = rd
			r.nlri.path_info = path_info
			# next ip
			ip += increment
			# save route
			scope[-1]['routes'].append(r)

		return True

	def _insert_static_route (self,scope,tokens):
		try:
			ip = tokens.pop(0)
		except IndexError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		try:
			ip,mask = ip.split('/')
		except ValueError:
			mask = '32'
		try:
			route = Route(NLRI(*inet(ip),mask=mask))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

		if 'routes' not in scope[-1]:
			scope[-1]['routes'] = []

		scope[-1]['routes'].append(route)
		return True

	def pop_last_static_route (self,scope):
		route = scope[-1]['routes'][-1]
		scope[-1]['routes'] = scope[-1]['routes'][:-1]
		return route

	def remove_route (self,route,scope):
		for r in scope[-1]['routes']:
			if r == route:
				scope[-1]['routes'].remove(r)
				return True
		return False

	def _check_static_route (self,scope):
		route = scope[-1]['routes'][-1]
		if not route.attributes.has(AttributeID.NEXT_HOP):
			self._error = 'syntax: route IP/MASK { next-hop IP; }'
			if self.debug: raise
			return False
		return True

	def _multi_static_route (self,scope,tokens):
		if len(tokens) != 1:
			self._error = self._str_route_error
			if self.debug: raise
			return False

		if not self._insert_static_route(scope,tokens):
			return False

		while True:
			r = self._dispatch(scope,'route',[],['next-hop','origin','as-path','as-sequence','med','local-preference','atomic-aggregate','aggregator','path-information','community','originator-id','cluster-list','extended-community','split','label','rd','route-distinguisher','watchdog','withdraw'])
			if r is False: return False
			if r is None: return self._split_last_route(scope)

	def _single_static_route (self,scope,tokens):
		if len(tokens) <3:
			return False

		have_next_hop = False

		if not self._insert_static_route(scope,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)
			if command == 'withdraw':
				if self._route_withdraw(scope,tokens):
					continue
				return False

			if len(tokens) < 1:
				return False

			if command == 'next-hop':
				if self._route_next_hop(scope,tokens):
					have_next_hop = True
					continue
				return False
			if command == 'origin':
				if self._route_origin(scope,tokens):
					continue
				return False
			if command == 'as-path':
				if self._route_aspath(scope,tokens):
					continue
				return False
			if command == 'as-sequence':
				if self._route_aspath(scope,tokens):
					continue
				return False
			if command == 'med':
				if self._route_med(scope,tokens):
					continue
				return False
			if command == 'local-preference':
				if self._route_local_preference(scope,tokens):
					continue
				return False
			if command == 'atomic-aggregate':
				if self._route_atomic_aggregate(scope,tokens):
					continue
				return False
			if command == 'aggregator':
				if self._route_aggregator(scope,tokens):
					continue
				return False
			if command == 'path-information':
				if self._route_path_information(scope,tokens):
					continue
				return False
			if command == 'community':
				if self._route_community(scope,tokens):
					continue
				return False
			if command == 'originator-id':
				if self._route_originator_id(scope,tokens):
					continue
				return False
			if command == 'cluster-list':
				if self._route_cluster_list(scope,tokens):
					continue
				return False
			if command == 'extended-community':
				if self._route_extended_community(scope,tokens):
					continue
				return False
			if command == 'split':
				if self._route_split(scope,tokens):
					continue
				return False
			if command == 'label':
				if self._route_label(scope,tokens):
					continue
				return False
			if command in ('rd','route-distinguisher'):
				if self._route_rd(scope,tokens):
					continue
				return False
			if command == 'watchdog':
				if self._route_watchdog(scope,tokens):
					continue
				return False
			return False

		if not have_next_hop:
			self._error = 'every route requires a next-hop'
			if self.debug: raise
			return False

		return self._split_last_route(scope)

	# Command Route

	def _route_next_hop (self,scope,tokens):
		try:
			# next-hop self is unsupported
			ip = tokens.pop(0)
			if ip.lower() == 'self':
				la = scope[-1]['local-address']
				nh = la.afi,la.safi,la.pack()
			else:
				nh = inet(ip)
			scope[-1]['routes'][-1].attributes.add(cachedNextHop(*nh))
			return True
		except:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_origin (self,scope,tokens):
		data = tokens.pop(0).lower()
		if data == 'igp':
			scope[-1]['routes'][-1].attributes.add(Origin(Origin.IGP))
			return True
		if data == 'egp':
			scope[-1]['routes'][-1].attributes.add(Origin(Origin.EGP))
			return True
		if data == 'incomplete':
			scope[-1]['routes'][-1].attributes.add(Origin(Origin.INCOMPLETE))
			return True
		self._error = self._str_route_error
		if self.debug: raise
		return False

	def _route_aspath (self,scope,tokens):
		as_seq = []
		as_set = []
		asn = tokens.pop(0)
		try:
			if asn == '[':
				while True:
					try:
						asn = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise
						return False
					if asn == '(':
						while True:
							try:
								asn = tokens.pop(0)
							except IndexError:
								self._error = self._str_route_error
								if self.debug: raise
								return False
							if asn == ')':
								break
							as_set.append(self._newASN(asn))
					if asn == ')':
						continue
					if asn == ']':
						break
					as_seq.append(self._newASN(asn))
			else:
				as_seq.append(self._newASN(asn))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		scope[-1]['routes'][-1].attributes.add(ASPath(as_seq,as_set))
		return True

	def _route_med (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(MED(pack('!L',int(tokens.pop(0)))))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_local_preference (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(LocalPreference(pack('!L',int(tokens.pop(0)))))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_atomic_aggregate (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(AtomicAggregate())
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_aggregator (self,scope,tokens):
		try:
			if tokens:
				if tokens.pop(0) != '(':
					raise ValueError('invalid aggregator syntax')
				asn,address = tokens.pop(0).split(':')
				if tokens.pop(0) != ')':
					raise ValueError('invalid aggregator syntax')
				local_as = ASN(asn)
				local_address = RouterID(address)
			else:
				local_as = scope[-1]['local-as']
				local_address = scope[-1]['local-address']
		except (ValueError,IndexError):
			self._error = self._str_route_error
			if self.debug: raise
			return False
		except KeyError:
			self._error = 'local-as and/or local-address missing from neighbor/group to make aggregator'
			if self.debug: raise
			return False
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

		scope[-1]['routes'][-1].attributes.add(Aggregator(local_as.pack(True)+local_address.pack()))
		return True

	def _route_path_information (self,scope,tokens):
		try:
			pi = tokens.pop(0)
			if pi.isdigit():
				scope[-1]['routes'][-1].nlri.path_info = PathInfo(integer=int(pi))
			else:
				scope[-1]['routes'][-1].nlri.path_info = PathInfo(ip=pi)
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _parse_community (self,scope,data):
		separator = data.find(':')
		if separator > 0:
			prefix = int(data[:separator])
			suffix = int(data[separator+1:])
			if prefix >= pow(2,16):
				raise ValueError('invalid community %s (prefix too large)' % data)
			if suffix >= pow(2,16):
				raise ValueError('invalid community %s (suffix too large)' % data)
			return cachedCommunity(pack('!L',(prefix<<16) + suffix))
		elif len(data) >=2 and data[1] in 'xX':
			value = long(data,16)
			if value >= pow(2,32):
				raise ValueError('invalid community %s (too large)' % data)
			return cachedCommunity(pack('!L',value))
		else:
			low = data.lower()
			if low == 'no-export':
				return cachedCommunity(Community.NO_EXPORT)
			elif low == 'no-advertise':
				return cachedCommunity(Community.NO_ADVERTISE)
			elif low == 'no-export-subconfed':
				return cachedCommunity(Community.NO_EXPORT_SUBCONFED)
			# no-peer is not a correct syntax but I am sure someone will make the mistake :)
			elif low == 'nopeer' or low == 'no-peer':
				return cachedCommunity(Community.NO_PEER)
			elif data.isdigit():
				value = unpack('!L',data)[0]
				if value >= pow(2,32):
					raise ValueError('invalid community %s (too large)' % data)
					return cachedCommunity(pack('!L',value))
			else:
				raise ValueError('invalid community name %s' % data)

	def _route_originator_id (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(OriginatorID(*inet(tokens.pop(0))))
			return True
		except:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_cluster_list (self,scope,tokens):
		_list = ''
		clusterid = tokens.pop(0)
		try:
			if clusterid == '[':
				while True:
					try:
						clusterid = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise
						return False
					if clusterid == ']':
						break
					_list += ''.join([chr(int(_)) for _ in clusterid.split('.')])
			else:
				_list = ''.join([chr(int(_)) for _ in clusterid.split('.')])
			if not _list:
				raise ValueError('no cluster-id in the cluster-list')
			clusterlist = ClusterList(_list)
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		scope[-1]['routes'][-1].attributes.add(clusterlist)
		return True

	def _route_community (self,scope,tokens):
		communities = Communities()
		community = tokens.pop(0)
		try:
			if community == '[':
				while True:
					try:
						community = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise
						return False
					if community == ']':
						break
					communities.add(self._parse_community(scope,community))
			else:
				communities.add(self._parse_community(scope,community))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		scope[-1]['routes'][-1].attributes.add(communities)
		return True

	def _parse_extended_community (self,scope,data):
		if data[:2].lower() == '0x':
			try:
				raw = ''
				for i in range(2,len(data),2):
					raw += chr(int(data[i:i+2],16))
			except ValueError:
				raise ValueError('invalid extended community %s' % data)
			if len(raw) != 8:
				raise ValueError('invalid extended community %s' % data)
			return ECommunity(raw)
		elif data.count(':'):
			return to_ExtendedCommunity(data)
		else:
			raise ValueError('invalid extended community %s - lc+gc' % data)

	def _route_extended_community (self,scope,tokens):
		extended_communities = ECommunities()
		extended_community = tokens.pop(0)
		try:
			if extended_community == '[':
				while True:
					try:
						extended_community = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise
						return False
					if extended_community == ']':
						break
					extended_communities.add(self._parse_extended_community(scope,extended_community))
			else:
				extended_communities.add(self._parse_extended_community(scope,extended_community))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		scope[-1]['routes'][-1].attributes.add(extended_communities)
		return True


	def _route_split (self,scope,tokens):
		try:
			size = tokens.pop(0)
			if not size or size[0] != '/':
				raise ValueError('route "as" require a CIDR')
			scope[-1]['routes'][-1].attributes.add(Split(int(size[1:])))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_label (self,scope,tokens):
		labels = []
		label = tokens.pop(0)
		try:
			if label == '[':
				while True:
					try:
						label = tokens.pop(0)
					except IndexError:
						self._error = self._str_route_error
						if self.debug: raise
						return False
					if label == ']':
						break
					labels.append(int(label))
			else:
				labels.append(int(label))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

		nlri = scope[-1]['routes'][-1].nlri
		if not nlri.safi.has_label():
			nlri.safi = SAFI(SAFI.nlri_mpls)
		nlri.labels = Labels(labels)
		return True

	def _route_rd (self,scope,tokens):
		try:
			try:
				data = tokens.pop(0)
			except IndexError:
				self._error = self._str_route_error
				if self.debug: raise
				return False

			separator = data.find(':')
			if separator > 0:
				prefix = data[:separator]
				suffix = int(data[separator+1:])

			if '.' in prefix:
				bytes = [chr(0),chr(1)]
				bytes.extend([chr(int(_)) for _ in prefix.split('.')])
				bytes.extend([suffix>>8,suffix&0xFF])
				rd = ''.join(bytes)
			else:
				number = int(prefix)
				if number < pow(2,16) and suffix < pow(2,32):
					rd = chr(0) + chr(0) + pack('!H',number) + pack('!L',suffix)
				elif number < pow(2,32) and suffix < pow(2,16):
					rd = chr(0) + chr(2) + pack('!L',number) + pack('!H',suffix)
				else:
					raise ValueError('invalid route-distinguisher %s' % data)

			nlri = scope[-1]['routes'][-1].nlri
			# overwrite nlri-mpls
			nlri.safi = SAFI(SAFI.mpls_vpn)
			nlri.rd = RouteDistinguisher(rd)
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False


	# Group Flow  ........

	def _multi_flow (self,scope,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		while True:
			r = self._dispatch(scope,'flow',['route',],[])
			if r is False: return False
			if r is None: break
		return True

	def _insert_flow_route (self,scope,tokens=None):
		if self._flow_state != 'out':
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		self._flow_state = 'match'

		try:
			flow = Flow()
		except ValueError:
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		if 'routes' not in scope[-1]:
			scope[-1]['routes'] = []

		scope[-1]['routes'].append(flow)
		return True

	def _check_flow_route (self,scope):
		self.logger.configuration('warning: no check on flows are implemented')
		return True

	def _multi_flow_route (self,scope,tokens):
		if len(tokens) > 1:
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		if not self._insert_flow_route(scope):
			return False

		while True:
			r = self._dispatch(scope,'flow-route',['match','then'],[])
			if r is False: return False
			if r is None: break

		if self._flow_state != 'out':
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		return True

	# ..........................................

	def _multi_match (self,scope,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		if self._flow_state != 'match':
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		self._flow_state = 'then'

		while True:
			r = self._dispatch(scope,'flow-match',[],['source','destination','port','source-port','destination-port','protocol','tcp-flags','icmp-type','icmp-code','fragment','dscp','packet-length'])
			if r is False: return False
			if r is None: break
		return True

	def _multi_then (self,scope,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		if self._flow_state != 'then':
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		self._flow_state = 'out'

		while True:
			r = self._dispatch(scope,'flow-then',[],['discard','rate-limit','redirect','community'])
			if r is False: return False
			if r is None: break
		return True

	# Command Flow

	def _flow_source (self,scope,tokens):
		try:
			ip,nm = tokens.pop(0).split('/')
			scope[-1]['routes'][-1].add_and(Source(ip,nm))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _flow_destination (self,scope,tokens):
		try:
			ip,nm = tokens.pop(0).split('/')
			scope[-1]['routes'][-1].add_and(Destination(ip,nm))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	# to parse the port configuration of flow

	def _operator (self,string):
		try:
			if string[0] == '=':
				return NumericOperator.EQ,string[1:]
			elif string[0] == '>':
				operator = NumericOperator.GT
			elif string[0] == '<':
				operator = NumericOperator.LT
			else:
				raise ValueError('Invalid operator in test %s' % string)
			if string[1] == '=':
				operator += NumericOperator.EQ
				return operator,string[2:]
			else:
				return operator,string[1:]
		except IndexError:
			raise('Invalid expression (too short) %s' % string)

	def _value (self,string):
		l = 0
		for c in string:
			if c not in ['&',]:
				l += 1
				continue
			break
		return string[:l],string[l:]

	# parse =80 or >80 or <25 or &>10<20
	def _flow_generic_expression (self,scope,tokens,converter,klass):
		try:
			for test in tokens:
				AND = BinaryOperator.NOP
				while test:
					operator,_ = self._operator(test)
					value,test = self._value(_)
					number = converter(value)
					scope[-1]['routes'][-1].add_or(klass(AND|operator,number))
					if test:
						if test[0] == '&':
							AND = BinaryOperator.AND
							test = test[1:]
							if not test:
								raise ValueError("Can not finish an expresion on an &")
						else:
							raise ValueError("Unknown binary operator %s" % test[0])
			return True
		except ValueError,e:
			self._error = self._str_route_error + str(e)
			if self.debug: raise
			return False

	# parse [ content1 content2 content3 ]
	def _flow_generic_list (self,scope,tokens,converter,klass):
		name = tokens.pop(0)
		AND = BinaryOperator.NOP
		try:
			if name == '[':
				while True:
					name = tokens.pop(0)
					if name == ']':
						break
					try:
						try:
							number = int(name)
						except ValueError:
							number = converter(name)
						scope[-1]['routes'][-1].add_or(klass(NumericOperator.EQ|AND,number))
					except IndexError:
						self._error = self._str_flow_error
						if self.debug: raise
						return False
			else:
				try:
					number = int(name)
				except ValueError:
					number = converter(name)
				scope[-1]['routes'][-1].add_or(klass(NumericOperator.EQ|AND,number))
		except ValueError:
			self._error = self._str_flow_error
			if self.debug: raise
			return False
		return True

	def _flow_generic_condition (self,scope,tokens,converter,klass):
		if tokens[0][0] in ['=','>','<']:
			return self._flow_generic_expression(scope,tokens,converter,klass)
		return self._flow_generic_list(scope,tokens,converter,klass)

	def _flow_route_anyport (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,convert_port,AnyPort)

	def _flow_route_source_port (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,convert_port,SourcePort)

	def _flow_route_destination_port (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,convert_port,DestinationPort)

	def _flow_route_packet_length (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,convert_length,PacketLength)

	def _flow_route_tcp_flags (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedTCPFlags,TCPFlag)

	def _flow_route_protocol (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedProtocol,IPProtocol)

	def _flow_route_icmp_type (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedICMPType,ICMPType)

	def _flow_route_icmp_code (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedICMPCode,ICMPCode)

	def _flow_route_fragment (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedFragment,Fragment)

	def _flow_route_dscp (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,convert_dscp,DSCP)

	def _flow_route_discard (self,scope,tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			scope[-1]['routes'][-1].add_action(to_FlowTrafficRate(ASN(0),0))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _flow_route_rate_limit (self,scope,tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			speed = int(tokens[0])
			if speed < 9600 and speed != 0:
				self.logger.warning("rate-limiting flow under 9600 bytes per seconds may not work",'configuration')
			if speed > 1000000000000:
				speed = 1000000000000
				self.logger.warning("rate-limiting changed for 1 000 000 000 000 bytes from %s" % tokens[0],'configuration')
			scope[-1]['routes'][-1].add_action(to_FlowTrafficRate(ASN(0),speed))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _flow_route_redirect (self,scope,tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			prefix,suffix=tokens[0].split(':',1)
			if prefix.count('.'):
				ip = prefix.split('.')
				if len(ip) != 4:
					raise ValueError('invalid IP %s' % prefix)
				ipn = 0
				while ip:
					ipn <<= 8
					ipn += int(ip.pop(0))
				number = int(suffix)
				if number >= pow(2,16):
					raise ValueError('number is too large, max 16 bits %s' % number)
				scope[-1]['routes'][-1].add_action(to_FlowRedirectIP(ipn,number))
				return True
			else:
				asn = int(prefix)
				route_target = int(suffix)
				if asn >= pow(2,16):
					raise ValueError('asn is a 32 bits number, it can only be 16 bit %s' % route_target)
				if route_target >= pow(2,32):
					raise ValueError('route target is a 32 bits number, value too large %s' % route_target)
				scope[-1]['routes'][-1].add_action(to_FlowRedirectASN(asn,route_target))
				return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False


	def decode (self,route):
		# self check to see if we can decode what we encode
		from exabgp.bgp.message.update import Update
		from exabgp.bgp.message.open import Open
		from exabgp.bgp.message.open.capability import Capabilities
		from exabgp.bgp.message.open.capability.negotiated import Negotiated
		from exabgp.bgp.message.open.capability.id import CapabilityID

		self.logger.info('\ndecoding routes in configuration','parser')

		if route.startswith('F'*32):
			route = route[19*2:]
		#	prepend = route[:19*2]
		#else:
		#	prepend = ''

		n = self.neighbor[self.neighbor.keys()[0]]

		path = {}
		for f in known_families():
			if n.add_path:
				path[f] = n.add_path

		capa = Capabilities().new(n,False)
		capa[CapabilityID.ADD_PATH] = path
		capa[CapabilityID.MULTIPROTOCOL_EXTENSIONS] = n.families()

		o1 = Open().new(4,n.local_as,str(n.local_address),capa,180)
		o2 = Open().new(4,n.peer_as,str(n.peer_address),capa,180)
		negotiated = Negotiated()
		negotiated.sent(o1)
		negotiated.received(o2)
		#grouped = False

		injected = ''.join(chr(int(_,16)) for _ in (route[i*2:(i*2)+2] for i in range(len(route)/2)))
		# This does not take the BGP header - let's assume we will not break that :)
		update = Update().factory(negotiated,injected)
		self.logger.info('','parser')
		for route in update.routes:
			self.logger.info('decoded route %s' % route.extensive(),'parser')
		import sys
		sys.exit(0)


# ASN4 merge test
#		injected = ['0x0', '0x0', '0x0', '0x2e', '0x40', '0x1', '0x1', '0x0', '0x40', '0x2', '0x8', '0x2', '0x3', '0x78', '0x14', '0xab', '0xe9', '0x5b', '0xa0', '0x40', '0x3', '0x4', '0x52', '0xdb', '0x0', '0x4f', '0xc0', '0x8', '0x8', '0x78', '0x14', '0xc9', '0x46', '0x78', '0x14', '0xfd', '0xea', '0xe0', '0x11', '0xa', '0x2', '0x2', '0x0', '0x0', '0xab', '0xe9', '0x0', '0x3', '0x5', '0x54', '0x17', '0x9f', '0x65', '0x9e', '0x15', '0x9f', '0x65', '0x80', '0x18', '0x9f', '0x65', '0x9f']
# EOR
#		injected = '\x00\x00\x00\x07\x90\x0f\x00\x03\x00\x02\x01'

	def selfcheck (self):
		# self check to see if we can decode what we encode
		from exabgp.structure.utils import dump
		from exabgp.bgp.message.update import Update
		from exabgp.bgp.message.open import Open
		from exabgp.bgp.message.open.capability import Capabilities
		from exabgp.bgp.message.open.capability.negotiated import Negotiated
		from exabgp.bgp.message.open.capability.id import CapabilityID

		self.logger.info('\ndecoding routes in configuration','parser')

		n = self.neighbor[self.neighbor.keys()[0]]

		path = {}
		for f in known_families():
			if n.add_path:
				path[f] = n.add_path

		capa = Capabilities().new(n,False)
		capa[CapabilityID.ADD_PATH] = path
		capa[CapabilityID.MULTIPROTOCOL_EXTENSIONS] = n.families()

		o1 = Open().new(4,n.local_as,str(n.local_address),capa,180)
		o2 = Open().new(4,n.peer_as,str(n.peer_address),capa,180)
		negotiated = Negotiated()
		negotiated.sent(o1)
		negotiated.received(o2)
		#grouped = False

		for nei in self.neighbor.keys():
			for family in self.neighbor[nei].families():
				if not family in self.neighbor[nei]._routes:
					continue
				for route in self.neighbor[nei]._routes[family]:
					str1 = route.extensive()
					update = Update().new([route])
					packed = update.announce(negotiated)
					self.logger.info('parsed route requires %d updates' % len(packed),'parser')
					for pack in packed:
						self.logger.info('update size is %d' % len(pack),'parser')
						# This does not take the BGP header - let's assume we will not break that :)
						update = Update().factory(negotiated,pack[19:])
						self.logger.info('','parser')
						for route in update.routes:
							str2 = route.extensive()
							self.logger.info('parsed  route %s' % str1,'parser')
							self.logger.info('recoded route %s' % str2,'parser')
							self.logger.info('recoded hex   %s\n' % dump(pack),'parser')
		import sys
		sys.exit(0)
