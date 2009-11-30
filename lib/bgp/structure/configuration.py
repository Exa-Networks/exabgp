#!/usr/bin/env python
# encoding: utf-8
"""
configuration.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import re

from bgp.message.inet         import AFI,to_ASN,to_IP
from bgp.structure.neighbor   import Neighbor
from bgp.message.open         import HoldTime
from bgp.message.update       import to_Route, Attributes
from bgp.message.update.attribute.origin      import to_Origin
from bgp.message.update.attribute.aspath      import ASPath
from bgp.message.update.attribute.med         import MED
from bgp.message.update.attribute.localpref   import LocalPreference
from bgp.message.update.attribute.communities import to_Community,Communities

class Configuration (object):
	debug = True
	_str_route_error = 'syntax: route IP/MASK next-hop IP' \
	' origin IGP|EGP|INCOMPLETE' \
	' as-path ASN| as-path [ASN1 ASN2 ...]' \
	' med NUMBER' \
	' local-preference NUMBER]' \
	' community COMMUNITY| community [COMMUNITY1 COMMUNITY2 ...]' \

	def __init__ (self,fname,text=False):
		self._text = text
		self._fname = fname
		self.neighbor = {}
		self.error = ''

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

		self._neighbor = {}
		self._scope = []
		self._location = ['root']
		self._line = []
		self._error = ''
		self._number = 0

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

	def _dispatch (self,name,multi=set([]),single=set([])):
		try:
			tokens = self.tokens()
		except IndexError:
			self._error = 'configuration file incomplete (most likely missing })'
			if self.debug: raise
			return False
		end = tokens[-1]
		if multi and end == '{':
			self._location.append(tokens[0])
			return self._multi_line(tokens[:-1],multi)
		if single and end == ';':
			return self._single_line(tokens[:-1],single)
		if end == '}':
			if len(self._location) == 1:
				self._error = 'closing too many parenthesis'
				return False
			self._location.pop(-1)
			return None
		return False

	def _multi_line (self,tokens,valid=set([])):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'option %s in not valid here' % command
			return False
		if command == 'neighbor':
			if len(tokens) != 2:
				self._error = 'syntax: neighbor <ip> { <options> }'
				return False
			if self._multi_neighbor(tokens[1]):
				return self._make_neighbor()
			return False
		if command == 'static': return self._multi_static(tokens[1:])
		if command == 'route':
			if self._multi_route(tokens[1:]):
				return self._check_route()
			return False
		return False

	def _single_line (self,tokens,valid=set([])):
		command = tokens[0]
		if valid and command not in valid:
			self._error = 'invalid keyword "%s"' % command
			return False

		if command == 'description': return self._set_description(tokens[1:])
		if command == 'router-id': return self._set_ip('router-id',tokens[1:])
		if command == 'local-address': return self._set_ip('local-address',tokens[1:])
		if command == 'local-as': return self._set_asn('local-as',tokens[1:])
		if command == 'peer-as': return self._set_asn('peer-as',tokens[1:])
		if command == 'hold-time': return self._set_holdtime('hold-time',tokens[1:])
		if command == 'graceful-restart': return self._set_gracefulrestart('graceful-restart',tokens[1:])

		if command == 'route': return self._single_route(tokens[1:])
		if command == 'origin': return self._route_origin(tokens[1:])
		if command == 'as-path': return self._route_aspath(tokens[1:])
		if command == 'med': return self._route_med(tokens[1:])
		if command == 'next-hop': return self._route_next_hop(tokens[1:])
		if command == 'local-preference': return self._route_local_preference(tokens[1:])
		if command == 'community': return self._route_community(tokens[1:])
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

		# drop the neiborg
		scope = self._scope.pop(-1)
		neighbor.description = scope.get('description','')
		neighbor.graceful_restart = scope.get('graceful-restart',False)

		missing = neighbor.missing()
		if missing:
			self._error = 'incomplete neighbor, missing %s' % missing
			return False
		if neighbor.router_id.afi != AFI.ipv4:
			self._error = 'router-id must be a IPv4 address (not %s)' % neighbor.router_id
			return False
		if self._neighbor.has_key(neighbor.peer_address):
			self_error = 'duplicate peer definition %s' % neighbor.peer_address
			return False
		self._neighbor[neighbor.peer_address.ip()] = neighbor
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
		 	r = self._dispatch('neigbor',['static',],['description','router-id','local-address','local-as','peer-as','hold-time','graceful-restart'])
			if r is False: return False
			if r is None: return True

	# Command Neighbor

	def _set_description (self,tokens):
		text = ' '.join(tokens)
		if len(text) < 2 or text[0] != '"' or text[-1] != '"' or text[1:-1].count('"'):
			self._error = 'syntax: description "<description>"'
			return False
		self._scope[-1]['description'] = text[1:-1]
		return True

	def _set_asn (self,command,value):
		# XXX: we do not support 32 bits ASN...
		try:
			self._scope[-1][command] = to_ASN(value[0])
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
			self._scope[-1][command] = HoldTime(value[0])
			return True
		except ValueError:
			self._error = '"%s" is an invalid hold-time' % ' '.join(value)
			if self.debug: raise
			return False

	def _set_gracefulrestart (self,command,value):
		if len(value):
			self._error = 'graceful-restart is not taking parameters "%s"' % ' '.join(value)
			if self.debug: raise
			return False
		self._scope[-1]['graceful-restart'] = True
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

	def _insert_route (self,tokens):
		try:
			ip,nm = tokens.pop(0).split('/')
			route = to_Route(ip,nm)
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

		if not self._scope[-1].has_key('routes'):
			self._scope[-1]['routes'] = []

		self._scope[-1]['routes'].append(route)
		return True

	def _check_route (self):
		route = self._scope[-1]['routes'][-1]
		next_hop = self._scope[-1]['routes'][-1].next_hop

		if not next_hop:
			self._error = 'syntax: route IP/MASK { next-hop IP; }'
			return False
		return True

	def _multi_route (self,tokens):
		if len(tokens) != 1:
			self._error = self._str_route_error
			return False

		if not self._insert_route(tokens):
			return False

		while True:
			r = self._dispatch('route',[],['next-hop','origin','as-path','med','local-preference','community'])
			if r is False: return False
			if r is None: break
		return True

	def _single_route (self,tokens):
		if len(tokens) <3:
			self._error = self._str_route_error
			return False

		if not self._insert_route(tokens):
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
			self._error = self._str_route_error
			return False
		return True

	# Command Route

	def _route_next_hop (self,tokens):
		try:
			t = tokens.pop(0)
			self._scope[-1]['routes'][-1].next_hop = t
			return True
		except:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_origin (self,tokens):
		try:
			self._scope[-1]['routes'][-1].attributes.add(to_Origin(tokens.pop(0)))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False


	def _parse_asn (self,data):
		if not data.isdigit():
			self._error = self._str_route_error
			if self.debug: raise
			return False
		return to_ASN(data)

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
		self._scope[-1]['routes'][-1].attributes.add(aspath)
		return True

	def _route_med (self,tokens):
		try:
			self._scope[-1]['routes'][-1].attributes.add(MED(int(tokens.pop(0))))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _route_local_preference (self,tokens):
		try:
			self._scope[-1]['routes'][-1].attributes.add(LocalPreference(int(tokens.pop(0))))
			return True
		except ValueError:
			self._error = self._str_route_error
			if self.debug: raise
			return False

	def _parse_community (self,data):
		return to_Community(data)

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
		self._scope[-1]['routes'][-1].attributes.add(communities)
		return True
