# encoding: utf-8
"""
parse_neighbor.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import sys
import socket
import string
from copy import deepcopy

from exabgp.protocol.ip import IP

from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.routerid import RouterID

from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.message import Message
from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.current.basic import Basic
from exabgp.configuration.current.capability import ParseCapability

from exabgp.configuration.environment import environment


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


class ParseNeighbor (Basic):
	TTL_SECURITY = 255

	syntax = ''

	def __init__ (self, error, logger):
		self.error = error
		self.logger = logger
		self.capability = ParseCapability(error)
		self.fifo = environment.settings().api.file

		self.neighbors = {}
		self._neighbors = {}
		self._previous = {}

	def clear (self):
		self._previous = self.neighbors
		self._neighbors = {}
		self.neighbors = {}

	def cancel (self):
		self.neighbors = self._previous
		self._neighbors = {}
		self._previous = {}

	def complete (self):
		self.neighbors = self._neighbors
		self._neighbors = {}

		# installing in the neighbor the API routes
		for neighbor in self.neighbors:
			if neighbor in self._previous:
				self.neighbors[neighbor].changes = self._previous[neighbor].changes

		self._previous = {}

	def router_id (self, scope, command, tokens):
		try:
			ip = RouterID(tokens[0])
		except (IndexError,ValueError):
			return self.error.set('"%s" is an invalid IP address' % ' '.join(tokens))

		scope[-1][command] = ip
		return True

	def ip (self, scope, command, tokens):
		try:
			ip = IP.create(tokens[0])
		except (IndexError,ValueError):
			return self.error.set('"%s" is an invalid IP address' % ' '.join(tokens))

		scope[-1][command] = ip
		return True

	def description (self, scope, command, tokens):
		text = ' '.join(tokens)
		if len(text) < 2 or text[0] != '"' or text[-1] != '"' or text[1:-1].count('"'):
			return self.error.set('syntax: description "<description>"')

		scope[-1]['description'] = text[1:-1]
		return True

	def asn (self, scope, command, tokens):
		try:
			value = Basic.newASN(tokens[0])
		except ValueError:
			return self.error.set('"%s" is an invalid ASN' % ' '.join(tokens))
		except IndexError:
			return self.error.set('please provide an ASN')

		scope[-1][command] = value
		return True

	def passive (self, scope, command, tokens):
		if tokens:
			return self.error.set('"%s" is an invalid for passive' % ' '.join(tokens))

		scope[-1][command] = True
		return True

	def listen (self, scope, command, tokens):
		try:
			listen = int(tokens[0])
		except IndexError:
			return self.error.set('please provide a port to listen on')
		except ValueError:
			return self.error.set('"%s" is an invalid port to listen on' % ' '.join(tokens))

		if listen < 0:
			return self.error.set('the listenening port must positive')
		if listen >= pow(2,16):
			return self.error.set('the listening port must be smaller than %d' % pow(2,16))

		scope[-1][command] = listen
		return True

	def hostname (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('single host-name required')

		name = tokens[0]

		if not name:
			return self.error.set('bad host-name')
		if not name[0].isalnum() or name[0].isdigit():
			return self.error.set('bad host-name')
		if not name[-1].isalnum() or name[-1].isdigit():
			return self.error.set('bad host-name')
		if '..' in name:
			return self.error.set('bad host-name')
		if not all(True if c in string.ascii_letters + string.digits + '.-' else False for c in name):
			return self.error.set('bad host-name')
		if len(name) > 255:
			return self.error.set('bad host-name (length)')

		scope[-1][command] = name.encode('utf-8')
		return True

	def domainname (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('single domain-name required')

		name = tokens[0]

		if not name:
			return self.error.set('bad domain-name')
		if not name[0].isalnum() or name[0].isdigit():
			return self.error.set('bad domain-name')
		if not name[-1].isalnum() or name[-1].isdigit():
			return self.error.set('bad domain-name')
		if '..' in name:
			return self.error.set('bad domain-name')
		if not all(True if c in string.ascii_letters + string.digits + '.-' else False for c in name):
			return self.error.set('bad domain-name')
		if len(name) > 255:
			return self.error.set('bad domain-name (length)')

		scope[-1][command] = name.encode('utf-8')
		return True

	def holdtime (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('hold-time required')

		try:
			holdtime = HoldTime(tokens[0])
		except ValueError:
			return self.error.set('"%s" is an invalid hold-time' % ' '.join(tokens))

		if holdtime < 3 and holdtime != 0:
			return self.error.set('holdtime must be zero or at least three seconds')
		if holdtime >= pow(2,16):
			return self.error.set('holdtime must be smaller than %d' % pow(2,16))

		scope[-1][command] = holdtime
		return True

	def md5 (self, scope, command, tokens):
		if not len(tokens) == 1:
			return self.error.set('md5 required')

		md5 = tokens[0]
		if len(md5) > 2 and md5[0] == md5[-1] and md5[0] in ['"',"'"]:
			md5 = md5[1:-1]

		if len(md5) > 80:
			return self.error.set('md5 password must be no larger than 80 characters')
		if not md5:
			return self.error.set('md5 requires the md5 password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.')

		scope[-1][command] = md5
		return True

	def ttl (self, scope, command, tokens):
		if not len(tokens):
			scope[-1][command] = self.TTL_SECURITY
			return True

		try:
			# README: Should it be a subclass of int ?
			ttl = int(tokens[0])
		except ValueError:
			return self.error.set('"%s" is an invalid ttl-security (1-254)' % ' '.join(tokens))

		if ttl <= 0:
			return self.error.set('ttl-security must be a positive number (1-254)')
		if ttl >= 255:
			return self.error.set('ttl must be smaller than 255 (1-254)')

		scope[-1][command] = ttl
		return True

	groupupdate = Basic.boolean
	autoflush = Basic.boolean
	adjribout = Basic.boolean

	def make (self, scope, configuration):
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
			configuration.processes[_cli_name] = {
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
					configuration.processes[_cli_name]['%s-%d' % (direction,message)] = False

		for name in configuration.processes.keys():
			process = configuration.processes[name]

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
			return self.error.set('incomplete option route-refresh and no adj-rib-out')

		# XXX: check that if we have any message, we have parsed/packets
		# XXX: and vice-versa

		missing = neighbor.missing()
		if missing:
			return self.error.set('incomplete neighbor, missing %s' % missing)

		if neighbor.local_address.afi != neighbor.peer_address.afi:
			return self.error.set('local-address and peer-address must be of the same family')

		if neighbor.peer_address.ip in self._neighbors:
			return self.error.set('duplicate peer definition %s' % neighbor.peer_address.ip)

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
				return self.error.set('Trying to announce a route of type %s,%s when we are not announcing the family to our peer' % (afi,safi))

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
