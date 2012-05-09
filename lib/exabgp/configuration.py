# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import stat
from pprint import pformat
from copy import deepcopy

from exabgp.structure.ip         import to_IP,to_Route
from exabgp.structure.asn        import ASN
from exabgp.structure.neighbor   import Neighbor
from exabgp.structure.protocol   import NamedProtocol
from exabgp.structure.icmp       import NamedICMPType,NamedICMPCode
from exabgp.structure.tcpflags   import NamedTCPFlags
from exabgp.structure.fragments  import NamedFragments
from exabgp.message.open         import HoldTime,RouterID
#from exabgp.message.update.route import Route
from exabgp.message.update.flow  import BinaryOperator,NumericOperator
from exabgp.message.update.flow  import Flow,Source,Destination,SourcePort,DestinationPort,AnyPort,IPProtocol,TCPFlag,Fragment,PacketLength,ICMPType,ICMPCode,DSCP
from exabgp.message.update.attribute             import AttributeID #,Attribute
from exabgp.message.update.attribute.origin      import Origin
from exabgp.message.update.attribute.nexthop     import NextHop
from exabgp.message.update.attribute.aspath      import ASPath
from exabgp.message.update.attribute.med         import MED
from exabgp.message.update.attribute.localpref   import LocalPreference
from exabgp.message.update.attribute.communities import Community,Communities,ECommunity,ECommunities,to_ExtendedCommunity,to_FlowTrafficRate,to_RouteTargetCommunity_00,to_RouteTargetCommunity_01

from exabgp.log import Logger
logger = Logger()

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
	ID = AttributeID.INTERNAL_WITHDRAWN
	MULTIPLE = False

class Configuration (object):
	TTL_SECURITY = 255
	debug = os.environ.get('RAISE_CONFIGURATION',None) != None

	_str_route_error = \
	'community, extended-communities and as-path can take a single community as parameter.\n' \
	'only next-hop is mandatory\n' \
	'\n' \
	'syntax:\n' \
	'route 10.0.0.1/22 {\n' \
	'  next-hop 192.0.1.254;\n' \
	'  origin IGP|EGP|INCOMPLETE;\n' \
	'  as-path [ ASN1 ASN2 ];\n' \
	'  med 100;\n' \
	'  local-preference 100;\n' \
	'  community [ 65000 65001 65002 ];\n' \
	'  extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 ]\n' \
	'  label [ 100 200 ];\n' \
	'  split /24\n' \
	'  watchdog watchog-name\n' \
	'  withdrawn\n' \
	'}\n' \
	'\n' \
	'syntax:\n' \
	'route 10.0.0.1/22 next-hop 192.0.2.1' \
	' origin IGP|EGP|INCOMPLETE' \
	' as-path ASN' \
	' med 100' \
	' local-preference 100' \
	' community 65000' \
	' label 150' \
	' split /24' \
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

	def __init__ (self,fname,text=False):
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

	# Public Interface

	def reload (self):
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

		if r in [True,None]:
			self.neighbor = self._neighbor
			return True

		self.error = "\nsyntax error in section %s\nline %d : %s\n\n%s" % (self._location[-1],self.number(),self.line(),self._error)
		return False

	def parse_single_route (self,command):
		tokens = command.split(' ')[1:]
		if len(tokens) < 4:
			return False
		if tokens[0] != 'route':
			return False
		scope = [{}]
		if not self._single_static_route(scope,tokens[1:]):
			return None
		return scope[0]['routes'][0]

	def parse_single_flow (self,command):
		self._tokens = self._tokenise(' '.join(command.split(' ')[2:]).split('\\n'))
		scope = [{}]
		if not self._dispatch(scope,'flow',['route',],[]):
			return None
		if not self._check_flow_route(scope):
			return None
		return scope[0]['routes'][0]

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

	def _tokenise (self,text):
		r = []
		config = ''
		for line in text:
			replaced = line.strip().replace('\t',' ').replace(']',' ]').replace('[','[ ').lower()
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
		logger.config(config)
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
		logger.configuration('analysing tokens %s ' % str(tokens))
		logger.configuration('  valid block options %s' % str(multi))
		logger.configuration('  valid parameters    %s' % str(single))
		end = tokens[-1]
		if multi and end == '{':
			self._location.append(tokens[0])
			return self._multi_line(scope,name,tokens[:-1],multi)
		if single and end == ';':
			return self._single_line(scope,name,tokens[:-1],single)
		if end == '}':
			if len(self._location) == 1:
				self._error = 'closing too many parenthesis'
				return False
			self._location.pop(-1)
			return None
		return False

	def _multi_line (self,scope,name,tokens,valid):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'option %s in not valid here' % command
			return False

		if name == 'configuration':
			if  command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if  command == 'group':
				if len(tokens) != 2:
					self._error = 'syntax: group <name> { <options> }'
					return False
				return self._multi_group(scope,tokens[1])

		if name == 'group':
			if  command == 'neighbor':
				if self._multi_neighbor(scope,tokens[1:]):
					return self._make_neighbor(scope)
				return False
			if command == 'static': return self._multi_static(scope,tokens[1:])
			if command == 'flow': return self._multi_flow(scope,tokens[1:])
			if command == 'process': return self._multi_process(scope,tokens[1:])

		if name == 'neighbor':
			if command == 'static': return self._multi_static(scope,tokens[1:])
			if command == 'flow': return self._multi_flow(scope,tokens[1:])
			if command == 'process': return self._multi_process(scope,tokens[1:])

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
			return False

		if command == 'description': return self._set_description(scope,tokens[1:])
		if command == 'router-id': return self._set_router_id(scope,'router-id',tokens[1:])
		if command == 'local-address': return self._set_ip(scope,'local-address',tokens[1:])
		if command == 'local-as': return self._set_asn(scope,'local-as',tokens[1:])
		if command == 'peer-as': return self._set_asn(scope,'peer-as',tokens[1:])
		if command == 'hold-time': return self._set_holdtime(scope,'hold-time',tokens[1:])
		if command == 'graceful-restart': return self._set_gracefulrestart(scope,'graceful-restart',tokens[1:])
		if command == 'md5': return self._set_md5(scope,'md5',tokens[1:])
		if command == 'ttl-security': return self._set_ttl(scope,'ttl-security',tokens[1:])
		if command == 'multi-session': return self._set_multisession(scope,'multi-session',tokens[1:])

		if command == 'route': return self._single_static_route(scope,tokens[1:])
		if command == 'origin': return self._route_origin(scope,tokens[1:])
		if command == 'as-path': return self._route_aspath(scope,tokens[1:])
		if command == 'as-sequence': return self._route_aspath(scope,tokens[1:])
		if command == 'med': return self._route_med(scope,tokens[1:])
		if command == 'next-hop': return self._route_next_hop(scope,tokens[1:])
		if command == 'local-preference': return self._route_local_preference(scope,tokens[1:])
		if command == 'community': return self._route_community(scope,tokens[1:])
		if command == 'split': return self._route_split(scope,tokens[1:])
		if command == 'label': return self._route_label(scope,tokens[1:])
		if command == 'watchdog': return self._route_watchdog(scope,tokens[1:])
		if command == 'withdrawn': return self._route_withdrawn(scope,tokens[1:])

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
		if command == 'discard': return self._flow_route_discard(scope,tokens[1:])
		if command == 'rate-limit': return self._flow_route_rate_limit(scope,tokens[1:])
		if command == 'redirect': return self._flow_route_redirect(scope,tokens[1:])

		if command == 'run': return self._set_process_run(scope,'process-run',tokens[1:])
		if command == 'parse-routes': return self._set_process_parse_routes(scope,'parse-routes',tokens[1:])

		return False

	# Group Watchdog

	def _multi_process (self,scope,tokens):
		if len(tokens) != 1:
			self._error = self._str_process_error
			return False
		while True:
			r = self._dispatch(scope,'process',[],['run','parse-routes'])
			if r is False: return False
			if r is None: break
		self.process.setdefault(tokens[0],{})['run'] = scope[-1].pop('process-run')
		self.process[tokens[0]]['receive-routes'] = scope[-1].get('parse-routes',False)
		if 'peer-address' in scope[-1]:
			self.process[tokens[0]]['neighbor'] = scope[-1]['peer-address']
		else:
			self.process[tokens[0]]['neighbor'] = '*'
		return True

	def _set_process_parse_routes (self,scope,command,value):
		scope[-1][command] = True
		return True

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
				prg = os.path.join(os.getcwd(),prg)
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

	def _route_watchdog (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(Watchdog(tokens.pop(0)))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_withdrawn (self,scope,tokens):
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
			r = self._dispatch(scope,'group',['static','flow','neighbor','process'],['description','router-id','local-address','local-as','peer-as','hold-time','graceful-restart','md5','ttl-security','multi-session'])
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

		logger.configuration("\nPeer configuration complete :")
		for _key in scope[-1].keys():
			for _line in pformat(scope[-1][_key],3,3,3).split('\n'):
				logger.configuration("   %s: %s" %(_key,_line))
		logger.configuration("\n")

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
			neighbor.parse_routes = local_scope.get('parse-routes',False)
			v = local_scope.get('routes',[])
			for route in v:
				# This add the family to neighbor.families()
				neighbor.add_route(route)

		# drop the neighbor
		local_scope = scope.pop(-1)
		neighbor.description = local_scope.get('description','')

		neighbor.graceful_restart = local_scope.get('graceful-restart',0)
		if neighbor.graceful_restart is None:
			# README: Should it be a subclass of int ?
			neighbor.graceful_restart = int(neighbor.hold_time)

		neighbor.md5 = local_scope.get('md5',None)
		neighbor.ttl = local_scope.get('ttl-security',None)
		neighbor.multisession = local_scope.get('multi-session',False)

		missing = neighbor.missing()
		if missing:
			self._error = 'incomplete neighbor, missing %s' % missing
			return False
		if neighbor.local_address.afi != neighbor.peer_address.afi:
			self._error = 'local-address and peer-address must be of the same family'
			return False
		if self._neighbor.has_key(neighbor.peer_address.ip):
			self._error = 'duplicate peer definition %s' % neighbor.peer_address.ip
			return False

		if neighbor.multisession:
			for family in neighbor.families():
				afi,safi = family
				family_n = deepcopy(neighbor)
				for f in neighbor.families():
					if f == family:
						continue
					family_n.remove_family(f)
				self._neighbor[family_n.name()] = family_n
		else:
			self._neighbor[neighbor.name()] = neighbor
		return True


	def _multi_neighbor (self,scope,tokens):
		if len(tokens) != 1:
			self._error = 'syntax: neighbor <ip> { <options> }'
			return False

		address = tokens[0]
		scope.append({})
		try:
			scope[-1]['peer-address'] = to_IP(address)
		except:
			self._error = '"%s" is not a valid IP address' % address
			if self.debug: raise
			return False
		while True:
		 	r = self._dispatch(scope,'neighbor',['static','flow','process'],['description','router-id','local-address','local-as','peer-as','hold-time','graceful-restart','md5','ttl-security','multi-session'])
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
			ip = to_IP(value[0])
		except (IndexError,ValueError):
			self._error = '"%s" is an invalid IP address' % ' '.join(value)
			if self.debug: raise
			return False
		scope[-1][command] = ip
		return True

	def _set_holdtime (self,scope,command,value):
		try:
			holdtime = HoldTime(value[0])
			if holdtime < 0:
				raise ValueError('holdtime can not be negative')
			if holdtime >= pow(2,16):
				raise ValueError('holdtime must be smaller than %d' % pow(2,16))
			scope[-1][command] = holdtime
			return True
		except ValueError:
			self._error = '"%s" is an invalid hold-time' % ' '.join(value)
			if self.debug: raise
			return False

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

	def _set_md5 (self,scope,command,value):
		md5 = value[0]
		if len(md5) > 2 and md5[0] == md5[-1] and md5[0] in ['"',"'"]:
			md5 = md5[1:-1]
		if len(md5) > 80:
			self._error = 'md5 password must be no larger than 80 characters'
			if self.debug: raise
			return False
		if not md5:
			self._error = 'md5 requires the md5 password as an argument (quoted or unquoted)'
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

	def _set_multisession (self,scope,command,value):
		scope[-1][command] = True
		return True

	#  Group Static ................

	def _multi_static (self,scope,tokens):
		if len(tokens) != 0:
			self._error = 'syntax: static { route; route; ... }'
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

		# remove the route, we are going to replace it
		route = scope[-1]['routes'].pop(-1)

		# calculate the number of IP in the /<size> of the new route
		increment = pow(2,(len(route.nlri)*8) - split)
		# how many new routes are we going to create from the initial one
		number = pow(2,split - route.nlri.mask)

		# convert the IP into a integer/long
		ip = 0
		for c in route.nlri.raw:
			ip = ip << 8
			ip += ord(c)

		# route is becoming a template we will clone (deepcopy) so change its netmask
		route.nlri.mask = split

		# generate the new routes
		for _ in range(number):
			r = deepcopy(route)
			# convert the ip to a network packed format
			ipn = ip
			i = ''
			while ipn:
				lower = ipn&0xFF
				ipn = ipn >> 8
				i = chr(lower) + i

			# change the route network
			r.nlri.update_raw(i)
			# update ip to the next route
			ip += increment

			# save route
			scope[-1]['routes'].append(r)

		# route is no longer needed - delete it explicitely
		del(route)
		return True

	def _insert_static_route (self,scope,tokens):
		try:
			ip = tokens.pop(0)
		except IndexError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		try:
			ip,nm = ip.split('/')
		except ValueError:
			nm = '32'
		try:
			route = to_Route(ip,nm)
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

		if not scope[-1].has_key('routes'):
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
			return False
		return True

	def _multi_static_route (self,scope,tokens):
		if len(tokens) != 1:
			self._error = self._str_route_error
			return False

		if not self._insert_static_route(scope,tokens):
			return False

		while True:
			r = self._dispatch(scope,'route',[],['next-hop','origin','as-path','as-sequence','med','local-preference','community','extended-community','split','label','watchdog','withdrawn'])
			if r is False: return False
			if r is None: return self._split_last_route(scope)

	def _single_static_route (self,scope,tokens):
		if len(tokens) <3:
			return False

		if not self._insert_static_route(scope,tokens):
			return False

		if tokens.pop(0) != 'next-hop':
			return False

		if not self._route_next_hop(scope,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)
			if command == 'withdrawn':
				if self._route_withdrawn(scope,tokens):
					continue
				return False

			if len(tokens) < 1:
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
			if command == 'community':
				if self._route_community(scope,tokens):
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
			if command == 'watchdog':
				if self._route_watchdog(scope,tokens):
					continue
				return False
			return False
		return self._split_last_route(scope)

	# Command Route

	def _route_next_hop (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(NextHop(to_IP(tokens.pop(0))))
			return True
		except:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_origin (self,scope,tokens):
		data = tokens.pop(0).lower()
		if data == 'igp':
			scope[-1]['routes'][-1].attributes.add(Origin(0x00))
			return True
		if data == 'egp':
			scope[-1]['routes'][-1].attributes.add(Origin(0x01))
			return True
		if data == 'incomplete':
			scope[-1]['routes'][-1].attributes.add(Origin(0x02))
			return True
		self._error = self._str_route_error
		if self.debug: raise
		return False

	def _route_aspath (self,scope,tokens):
		aspath = ASPath()
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
					if asn == ']':
						break
					aspath.add(self._newASN(asn))
			else:
				aspath.add(self._newASN(asn))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		scope[-1]['routes'][-1].attributes.add(aspath)
		return True

	def _route_med (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(MED(int(tokens.pop(0))))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_local_preference (self,scope,tokens):
		try:
			scope[-1]['routes'][-1].attributes.add(LocalPreference(int(tokens.pop(0))))
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
			return Community((prefix<<16) + suffix)
		elif len(data) >=2 and data[1] in 'xX':
			value = long(data,16)
			if value >= pow(2,32):
				raise ValueError('invalid community %s (too large)' % data)
			return Community(value)
		else:
			low = data.lower()
			if low == 'no-export':
				data = 0xFFFFFF01
			elif low == 'no-advertise':
				data = 0xFFFFFF02
			elif low == 'no-export-subconfed':
				data = 0xFFFFFF03
			value = long(data)
			if value >= pow(2,32):
				raise ValueError('invalid community %s (too large)' % data)
			return Community(value)

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
					communities.add(self._parse_community(community))
			else:
				communities.add(self._parse_community(community))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		scope[-1]['routes'][-1].attributes.add(communities)
		return True

	# Group Flow  ........

	def _multi_flow (self,scope,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			return False

		while True:
			r = self._dispatch(scope,'flow',['route',],[])
			if r is False: return False
			if r is None: break
		return True

	def _insert_flow_route (self,scope,tokens=None):
		try:
			flow = Flow()
		except ValueError:
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		if not scope[-1].has_key('routes'):
			scope[-1]['routes'] = []

		scope[-1]['routes'].append(flow)
		return True

	def _check_flow_route (self,scope):
		logger.configuration('warning: no check on flows are implemented')
		return True

	def _multi_flow_route (self,scope,tokens):
		if len(tokens) > 1:
			self._error = self._str_flow_error
			return False

		if not self._insert_flow_route(scope):
			return False

		r = self._dispatch(scope,'flow-route',['match',],[])
		if r is False: return False
		r = self._dispatch(scope,'flow-route',['then',],[])
		return r

	# ..........................................

	def _multi_match (self,scope,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			return False

		while True:
			r = self._dispatch(scope,'flow-match',[],['source','destination','port','source-port','destination-port','protocol','tcp-flags','icmp-type','icmp-code','fragment','dscp','packet-length'])
			if r is False: return False
			if r is None: break
		return True

	def _multi_then (self,scope,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			return False

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
					try:
						number = int(value)
					except ValueError:
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
		except ValueError:
			self._error = self._str_route_error
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
		return self._flow_generic_condition(scope,tokens,int,AnyPort)

	def _flow_route_source_port (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,int,SourcePort)

	def _flow_route_destination_port (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,int,DestinationPort)

	def _flow_route_packet_length (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,int,PacketLength)

	def _flow_route_tcp_flags (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedTCPFlags,TCPFlag)

	def _flow_route_protocol (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedProtocol,IPProtocol)

	def _flow_route_icmp_type (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedICMPType,ICMPType)

	def _flow_route_icmp_code (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedICMPCode,ICMPCode)

	def _flow_route_fragment (self,scope,tokens):
		return self._flow_generic_list(scope,tokens,NamedFragments,Fragment)

	def _flow_route_dscp (self,scope,tokens):
		return self._flow_generic_condition(scope,tokens,int,DSCP)

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
				logger.warning("rate-limiting flow under 9600 bytes per seconds may not work","configuration")
			if speed > 1000000000000:
				speed = 1000000000000
				logger.warning("rate-limiting changed for 1 000 000 000 000 bytes from %s" % tokens[0],"configuration")
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
					raise ValueError('')
				ipn = 0
				while ip:
					ipn <<= 8
					ipn += int(ip.pop(0))
				number = int(suffix)
				scope[-1]['routes'][-1].add_action(to_RouteTargetCommunity_01(ipn,number))
				return True
			else:
				asn = int(prefix)
				route_target = int(suffix)
				if asn >= pow(2,16):
					asn = asn & 0xFFFF
				if route_target >= pow(2,32):
					raise ValueError('route target is a 32 bits number, value too large %s' % route_target)
				scope[-1]['routes'][-1].add_action(to_RouteTargetCommunity_00(asn,route_target))
				return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

