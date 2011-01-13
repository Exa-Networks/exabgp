#!/usr/bin/env python
# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import os

from bgp.structure.address    import AFI
from bgp.structure.ip         import to_IP,to_Prefix
from bgp.structure.asn        import ASN
from bgp.structure.neighbor   import Neighbor
from bgp.structure.protocol   import NamedProtocol
from bgp.structure.icmp       import NamedICMPType,NamedICMPCode
from bgp.structure.tcpflags   import NamedTCPFlags
from bgp.structure.fragments  import NamedFragments
from bgp.message.open         import HoldTime,RouterID
from bgp.message.update.route import Route
from bgp.message.update.flow  import BinaryOperator,NumericOperator
from bgp.message.update.flow  import Flow,Source,Destination,SourcePort,DestinationPort,AnyPort,IPProtocol,TCPFlag,Fragment,PacketLength,ICMPType,ICMPCode,DSCP
from bgp.message.update.attribute             import AttributeID
#from bgp.message.update.attributes            import Attributes
from bgp.message.update.attribute.origin      import Origin
from bgp.message.update.attribute.nexthop     import NextHop
from bgp.message.update.attribute.aspath      import ASPath
from bgp.message.update.attribute.med         import MED
from bgp.message.update.attribute.localpref   import LocalPreference
from bgp.message.update.attribute.communities import Community,Communities,to_FlowTrafficRate,to_RouteTargetCommunity_00,to_RouteTargetCommunity_01
#from bgp.message.update.attribute.labels      import Label,Labels


class Configuration (object):
	debug = False if os.environ.get('DEBUG_CONFIGURATION','0') == '0' else True
	
	_str_route_error = '' \
	'syntax:\n' \
	'route 10.0.0.1/24 {\n' \
	'  next-hop 192.0.1.254;\n'
	'  origin IGP|EGP|INCOMPLETE;\n' \
	'  as-path [ ASN1 ASN2 ];\n' \
	'  med 100;\n' \
	'  local-preference 100;\n' \
	'  community [ 65000 65001 65002 ]>\n' \
	'  label [ 100 200 ]>\n' \
	'}\n\n' \
	'route 10.0.0.1/24 next-hop 192.0.2.1' \
	' origin IGP|EGP|INCOMPLETE' \
	' as-path ASN' \
	' med 100' \
	' local-preference 100' \
	' community 65000' \
	' label 150' \
	';\n\n' \
	'community and as-path can take a single community as parameter. only next-hop is mandatory\n\n'


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


	def __init__ (self,fname,text=False):
		self._text = text
		self._fname = fname
		self._clear()
	
	def _clear (self):
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
				self._tokens = self._tokenise(f.readlines())
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

		while not self.finished():
			r = self._dispatch('configuration',['neighbor',],[])
			if r is False: break

		if r in [True,None]:
			self.neighbor = self._neighbor
			return True

		self.error = "syntax error in section %s\nline %d : %s\n%s" % (self._location[-1],self.number(),self.line(),self._error)
		return False

	# Tokenisation

	def _tokenise (self,text):
		r = []
		for line in text:
			line = line.strip().replace('\t',' ').replace(']',' ]').replace('[','[ ').lower()
			if not line:
				continue
			if line.startswith('#'):
				continue
			r.append([t for t in line[:-1].split(' ') if t] + [line[-1]])
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
	def _dispatch (self,name,multi=set([]),single=set([])):
		try:
			tokens = self.tokens()
			if self.debug: print 'dispatching', tokens, 'with valid options multi', multi, 'single', single 
		except IndexError:
			self._error = 'configuration file incomplete (most likely missing })'
			if self.debug: raise
			return False
		end = tokens[-1]
		if multi and end == '{':
			self._location.append(tokens[0])
			return self._multi_line(name,tokens[:-1],multi)
		if single and end == ';':
			return self._single_line(name,tokens[:-1],single)
		if end == '}':
			if len(self._location) == 1:
				self._error = 'closing too many parenthesis'
				return False
			self._location.pop(-1)
			return None
		return False

	def _multi_line (self,name,tokens,valid=set([])):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'option %s in not valid here' % command
			return False

		if name == 'configuration':
			if  command == 'neighbor':
				if len(tokens) != 2:
					self._error = 'syntax: neighbor <ip> { <options> }'
					return False
				if self._multi_neighbor(tokens[1]):
					return self._make_neighbor()
				return False

		if name == 'neighbor':
			if command == 'static': return self._multi_static(tokens[1:])
			if command == 'flow': return self._multi_flow(tokens[1:])

		if name == 'static':
			if command == 'route':
				if self._multi_static_route(tokens[1:]):
					return self._check_static_route()
				return False

		if name == 'flow':
			if command == 'route':
				if self._multi_flow_route(tokens[1:]):
					return self._check_flow_route()
				return False

		if name == 'flow-route':
			if command == 'match':
				if self._multi_match(tokens[1:]):
					return True
				return False
			if command == 'then':
				if self._multi_then(tokens[1:]):
					return True
				return False
		return False

	def _single_line (self,name,tokens,valid=set([])):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'invalid keyword "%s"' % command
			return False

		if command == 'description': return self._set_description(tokens[1:])
		if command == 'router-id': return self._set_router_id('router-id',tokens[1:])
		if command == 'local-address': return self._set_ip('local-address',tokens[1:])
		if command == 'local-as': return self._set_asn('local-as',tokens[1:])
		if command == 'peer-as': return self._set_asn('peer-as',tokens[1:])
		if command == 'hold-time': return self._set_holdtime('hold-time',tokens[1:])
		if command == 'graceful-restart': return self._set_gracefulrestart('graceful-restart',tokens[1:])
		if command == 'md5': return self._set_md5('md5',tokens[1:])

		if command == 'route': return self._single_static_route(tokens[1:])
		if command == 'origin': return self._route_origin(tokens[1:])
		if command == 'as-path': return self._route_aspath(tokens[1:])
		if command == 'med': return self._route_med(tokens[1:])
		if command == 'next-hop': return self._route_next_hop(tokens[1:])
		if command == 'local-preference': return self._route_local_preference(tokens[1:])
		if command == 'community': return self._route_community(tokens[1:])
		if command == 'label': return self._route_label(tokens[1:])
		
		if command == 'source': return self._flow_source(tokens[1:])
		if command == 'destination': return self._flow_destination(tokens[1:])
		if command == 'port': return self._flow_route_anyport(tokens[1:])
		if command == 'source-port': return self._flow_route_source_port(tokens[1:])
		if command == 'destination-port': return self._flow_route_destination_port(tokens[1:])
		if command == 'protocol': return self._flow_route_protocol(tokens[1:])
		if command == 'tcp-flags': return self._flow_route_tcp_flags(tokens[1:])
		if command == 'icmp-type': return self._flow_route_icmp_type(tokens[1:])
		if command == 'icmp-code': return self._flow_route_icmp_code(tokens[1:])
		if command == 'fragment': return self._flow_route_fragment(tokens[1:])
		if command == 'dscp': return self._flow_route_dscp(tokens[1:])
		if command == 'packet-length': return self._flow_route_packet_length(tokens[1:])
		if command == 'discard': return self._flow_route_discard(tokens[1:])
		if command == 'rate-limit': return self._flow_route_rate_limit(tokens[1:])
		if command == 'redirect': return self._flow_route_redirect(tokens[1:])
		
		return False

	# Group Neighbor

	def _make_neighbor (self):
		neighbor = Neighbor()
		for scope in self._scope:
			v = scope.get('router-id','')
			if v: neighbor.router_id = v
			v = scope.get('peer-address','')
			if v: neighbor.peer_address = v
			v = scope.get('local-address','')
			if v: neighbor.local_address = v
			v = scope.get('local-as','')
			if v: neighbor.local_as = v
			v = scope.get('peer-as','')
			if v: neighbor.peer_as = v
			v = scope.get('hold-time','')
			if v: neighbor.hold_time = v
			v = scope.get('routes',[])
			for route in v:
				neighbor.routes.append(route)
				if (route.afi,route.safi) not in neighbor.families:
					neighbor.families.append((route.afi,route.safi))

		# drop the neighbor
		scope = self._scope.pop(-1)
		neighbor.description = scope.get('description','')

		neighbor.graceful_restart = scope.get('graceful-restart',0)
		if neighbor.graceful_restart < 0:
			# README: Should it be a subclass of int ?
			neighbor.graceful_restart = int(neighbor.hold_time)

		neighbor.md5 = scope.get('md5','')

		missing = neighbor.missing()
		if missing:
			self._error = 'incomplete neighbor, missing %s' % missing
			return False
		if neighbor.local_address.afi != neighbor.peer_address.afi:
			self._error = 'local-address and peer-address must be of the same family'
			return False 
		if self._neighbor.has_key(neighbor.peer_address.ip):
			self.error = 'duplicate peer definition %s' % neighbor.peer_address.ip
			return False
		
		self._neighbor[neighbor.peer_address.ip] = neighbor
		return True


	def _multi_neighbor (self,address):
		self._scope.append({})
		try:
			self._scope[-1]['peer-address'] = to_IP(address)
		except:
			self._error = '"%s" is not a valid IP address' % address
			if self.debug: raise
			return False
		while True:
		 	r = self._dispatch('neighbor',['static','flow'],['description','router-id','local-address','local-as','peer-as','hold-time','graceful-restart','md5'])
			if r is False: return False
			if r is None: return True

	# Command Neighbor

	def _set_router_id (self,command,value):
		try:
			ip = RouterID(value[0])
		except (IndexError,ValueError):
			self._error = '"%s" is an invalid IP address' % ' '.join(value)
			if self.debug: raise
			return False
		self._scope[-1][command] = ip
		return True

	def _set_description (self,tokens):
		text = ' '.join(tokens)
		if len(text) < 2 or text[0] != '"' or text[-1] != '"' or text[1:-1].count('"'):
			self._error = 'syntax: description "<description>"'
			return False
		self._scope[-1]['description'] = text[1:-1]
		return True

	def _set_asn (self,command,value):
		try:
			self._scope[-1][command] = ASN(int(value[0]))
			return True
		except ValueError:
			self._error = '"%s" is an invalid ASN' % ' '.join(value)
			if self.debug: raise
			return False

	def _set_ip (self,command,value):
		try:
			ip = to_IP(value[0])
		except (IndexError,ValueError):
			self._error = '"%s" is an invalid IP address' % ' '.join(value)
			if self.debug: raise
			return False
		self._scope[-1][command] = ip
		return True

	def _set_holdtime (self,command,value):
		try:
			holdtime = HoldTime(value[0])
			if holdtime < 0:
				raise ValueError('holdtime can not be negative')
			if holdtime >= pow(2,16):
				raise ValueError('holdtime must be smaller than %d' % pow(2,16))
			self._scope[-1][command] = holdtime
			return True
		except ValueError:
			self._error = '"%s" is an invalid hold-time' % ' '.join(value)
			if self.debug: raise
			return False

	def _set_gracefulrestart (self,command,value):
		if not len(value):
			self._scope[-1]['graceful-restart'] = -1
			return True
		try:
			# README: Should it be a subclass of int ?
			grace = int(value[0])
			if grace < 0:
				raise ValueError('graceful-restart can not be negative')
			if grace >= pow(2,16):
				raise ValueError('graceful-restart must be smaller than %d' % pow(2,16))
			self._scope[-1][command] = grace
			return True
		except ValueError:
			self._error = '"%s" is an invalid graceful-restart time' % ' '.join(value)
			if self.debug: raise
			return False
		return True

	def _set_md5 (self,command,value):
		if not len(value):
			self._scope[-1]['md5'] = -1
			return True
		md5 = str(value[0])
		if not md5:
			self._error = 'md5 requires the md5 password as an argument'
			if self.debug: raise
			return False
		self._scope[-1][command] = md5
		return True

	#  Group Static ................

	def _multi_static (self,tokens):
		if len(tokens) != 0:
			self._error = 'syntax: static { route; route; ... }'
			return False
		while True:
		 	r = self._dispatch('static',['route',],['route',])
			if r is False: return False
			if r is None: return True

	# Group Route  ........

	def _insert_static_route (self,tokens):
		try:
			ip,nm = tokens.pop(0).split('/')
			prefix = to_Prefix(ip,nm)
			route = Route(prefix.afi,prefix.safi,prefix)
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

		if not self._scope[-1].has_key('routes'):
			self._scope[-1]['routes'] = []

		self._scope[-1]['routes'].append(route)
		return True

	def _check_static_route (self):
		route = self._scope[-1]['routes'][-1]
		if not route.has(AttributeID.NEXT_HOP):
			self._error = 'syntax: route IP/MASK { next-hop IP; }'
			return False
		return True

	def _multi_static_route (self,tokens):
		if len(tokens) != 1:
			self._error = self._str_route_error
			return False

		if not self._insert_static_route(tokens):
			return False

		while True:
			r = self._dispatch('route',[],['next-hop','origin','as-path','med','local-preference','community','label'])
			if r is False: return False
			if r is None: break
		return True

	def _single_static_route (self,tokens):
		if len(tokens) <3:
			self._error = self._str_route_error
			return False

		if not self._insert_static_route(tokens):
			return False

		if tokens.pop(0) != 'next-hop':
			self._error = self._str_route_error
			return False

		if not self._route_next_hop(tokens):
			return False

		while len(tokens):
			if len(tokens) < 2:
				self._error = self._str_route_error
				return False
			command = tokens.pop(0)
			if command == 'origin':
				if self._route_origin(tokens):
					continue
				return False
			if command == 'as-path':
				if self._route_aspath(tokens):
					continue
				return False
			if command == 'med':
				if self._route_med(tokens):
					continue
				return False
			if command == 'local-preference':
				if self._route_local_preference(tokens):
					continue
				return False
			if command == 'community':
				if self._route_community(tokens):
					continue
				return False
			if command == 'label':
				if self._route_label(tokens):
					continue
				return False
			self._error = self._str_route_error
			return False
		return True

	# Command Route

	def _route_next_hop (self,tokens):
		try:
			self._scope[-1]['routes'][-1].add(NextHop(to_IP(tokens.pop(0))))
			return True
		except:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_origin (self,tokens):
		data = tokens.pop(0).lower()
		if data == 'igp':
			self._scope[-1]['routes'][-1].add(Origin(0x00))
			return True
		if data == 'egp':
			self._scope[-1]['routes'][-1].add(Origin(0x01))
			return True
		if data == 'incomplete':
			self._scope[-1]['routes'][-1].add(Origin(0x02))
			return True
		self._error = self._str_route_error
		if self.debug: raise
		return False

	def _parse_asn (self,data):
		if not data.isdigit():
			self._error = self._str_route_error
			if self.debug: raise
			return False
		return ASN(int(data))

	def _route_aspath (self,tokens):
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
					aspath.add(self._parse_asn(asn))
			else:
				aspath.add(self._parse_asn(asn))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		self._scope[-1]['routes'][-1].add(aspath)
		return True

	def _route_med (self,tokens):
		try:
			self._scope[-1]['routes'][-1].add(MED(int(tokens.pop(0))))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_local_preference (self,tokens):
		try:
			self._scope[-1]['routes'][-1].add(LocalPreference(int(tokens.pop(0))))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _parse_community (self,data):
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
			value = long(data)
			if value >= pow(2,32):
				raise ValueError('invalid community %s (too large)' % data) 
			return Community(value)

	def _route_community (self,tokens):
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
		self._scope[-1]['routes'][-1].add(communities)
		return True

	def _route_label (self,tokens):
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
		self._scope[-1]['routes'][-1].add(communities)
		return True


	# Group Flow  ........

	def _multi_flow (self,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			return False

		while True:
			r = self._dispatch('flow',['route',],[])
			if r is False: return False
			if r is None: break
		return True

	def _insert_flow_route (self,tokens=None):
		try:
			flow = Flow()
		except ValueError:
			self._error = self._str_flow_error
			if self.debug: raise
			return False

		if not self._scope[-1].has_key('routes'):
			self._scope[-1]['routes'] = []

		self._scope[-1]['routes'].append(flow)
		return True

	def _check_flow_route (self):
		if self.debug: print "warning: no check on flows are implemented"
		return True

	def _multi_flow_route (self,tokens):
		if len(tokens) > 1:
			self._error = self._str_flow_error
			return False

		if not self._insert_flow_route():
			return False

		while True:
			r = self._dispatch('flow-route',['match',],[])
			if r is False: return False
			r = self._dispatch('flow-route',['then',],[])
			if r is False: return False
			if r is None: break
		return True

	# ..........................................
	
	def _multi_match (self,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			return False

		while True:
			r = self._dispatch('flow-match',[],['source','destination','port','source-port','destination-port','protocol','tcp-flags','icmp-type','icmp-code','fragment','dscp','packet-length'])
			if r is False: return False
			if r is None: break
		return True

	def _multi_then (self,tokens):
		if len(tokens) != 0:
			self._error = self._str_flow_error
			return False

		while True:
			r = self._dispatch('flow-then',[],['discard','rate-limit','redirect'])
			if r is False: return False
			if r is None: break
		return True

	# Command Flow

	def _flow_source (self,tokens):
		try:
			ip,nm = tokens.pop(0).split('/')
			self._scope[-1]['routes'][-1].add_and(Source(ip,nm))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _flow_destination (self,tokens):
		try:
			ip,nm = tokens.pop(0).split('/')
			self._scope[-1]['routes'][-1].add_and(Destination(ip,nm))
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
	def _flow_generic_expression (self,tokens,converter,klass):
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
					self._scope[-1]['routes'][-1].add_or(klass(AND|operator,number))
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
	def _flow_generic_list (self,tokens,converter,klass):
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
						self._scope[-1]['routes'][-1].add_or(klass(NumericOperator.EQ|AND,number))
					except IndexError:
						self._error = self._str_flow_error
						if self.debug: raise
						return False
			else:
				try:
					number = int(name)
				except ValueError:
					number = converter(name)
				self._scope[-1]['routes'][-1].add_or(klass(NumericOperator.EQ|AND,number))
		except ValueError:
			self._error = self._str_flow_error
			if self.debug: raise
			return False
		return True

	def _flow_generic_condition (self,tokens,converter,klass):
		if tokens[0][0] in ['=','>','<']:
			return self._flow_generic_expression(tokens,converter,klass)
		return self._flow_generic_list(tokens,converter,klass)

	def _flow_route_anyport (self,tokens):
		return self._flow_generic_condition(tokens,int,AnyPort)

	def _flow_route_source_port (self,tokens):
		return self._flow_generic_condition(tokens,int,SourcePort)

	def _flow_route_destination_port (self,tokens):
		return self._flow_generic_condition(tokens,int,DestinationPort)

	def _flow_route_packet_length (self,tokens):
		return self._flow_generic_condition(tokens,int,PacketLength)

	def _flow_route_tcp_flags (self,tokens):
		return self._flow_generic_list(tokens,NamedTCPFlags,TCPFlag)

	def _flow_route_protocol (self,tokens):
		return self._flow_generic_list(tokens,NamedProtocol,IPProtocol)

	def _flow_route_icmp_type (self,tokens):
		return self._flow_generic_list(tokens,NamedICMPType,ICMPType)

	def _flow_route_icmp_code (self,tokens):
		return self._flow_generic_list(tokens,NamedICMPCode,ICMPCode)

	def _flow_route_fragment (self,tokens):
		return self._flow_generic_list(tokens,NamedFragments,Fragment)
	
	def _flow_route_dscp (self,tokens):
		return self._flow_generic_condition(tokens,int,DSCP)

	def _flow_route_discard (self,tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			self._scope[-1]['routes'][-1].add_action(to_FlowTrafficRate(ASN(0),0))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _flow_route_rate_limit (self,tokens):
		# README: We are setting the ASN as zero as that what Juniper (and Arbor) did when we created a local flow route
		try:
			speed = int(tokens[0])
			if speed < 9600 and speed != 0:
				print "warning: rate-limiting flow under 9600 bytes per seconds may not work"
			if speed > 1000000000000:
				speed = 1000000000000
				print "warning: rate-limiting changed for 1 000 000 000 000 bytes from %s" % tokens[0]
			self._scope[-1]['routes'][-1].add_action(to_FlowTrafficRate(ASN(0),speed))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _flow_route_redirect (self,tokens):
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
				self._scope[-1]['routes'][-1].add_action(to_RouteTargetCommunity_01(ipn,number))
			else:
				asn = int(prefix)
				route_target = int(suffix)
				if asn >= pow(2,16):
					asn = asn & 0xFFFF
				if route_target >= pow(2,32):
					raise ValueError('route target is a 32 bits number, value too large %s' % route_target)
				self._scope[-1]['routes'][-1].add_action(to_RouteTargetCommunity_00(asn,route_target))
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False
		