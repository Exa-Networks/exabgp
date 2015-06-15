# encoding: utf-8
"""
neighbor/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# import sys
import socket
from copy import deepcopy

from exabgp.bgp.neighbor import Neighbor

# from exabgp.bgp.message import Message
from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.current.generic import Generic

from exabgp.configuration.current.generic.parser import boolean
from exabgp.configuration.current.generic.parser import ip
from exabgp.configuration.current.generic.parser import asn
from exabgp.configuration.current.generic.parser import port
from exabgp.configuration.current.neighbor.parser import ttl
from exabgp.configuration.current.neighbor.parser import md5
from exabgp.configuration.current.neighbor.parser import hold_time
from exabgp.configuration.current.neighbor.parser import router_id
from exabgp.configuration.current.neighbor.parser import hostname
from exabgp.configuration.current.neighbor.parser import domainname
from exabgp.configuration.current.neighbor.parser import description


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


class ParseNeighbor (Generic):
	TTL_SECURITY = 255

	name = 'neighbor'

	syntax = ''

	known = {
		'description':   description,
		'hostname':      hostname,
		'domainname':    domainname,
		'router-id':     router_id,
		'hold-time':     hold_time,
		'local-address': ip,
		'peer-address':  ip,
		'local-as':      asn,
		'peer-as':       asn,
		'passive':       boolean,
		'listen':        port,
		'ttl-security':  ttl,
		'md5':           md5,
		'group-updates': boolean,
		'auto-flush':    boolean,
		'adj-rib-out':   boolean,
	}

	append = [
		'route',
	]

	default = {
		'passive': False,
		'group-updates': True,
		'auto-flush': True,
		'adj-rib-out': False,
	}

	name = 'neighbor'

	def __init__ (self, tokeniser, scope, error, logger):
		Generic.__init__(self,tokeniser,scope,error,logger)

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

	def pre (self):
		self.scope.new_context()
		return self.parse(self.name,'peer-address')

	def post (self):
		local = self.scope.pop_context()
		neighbor = Neighbor()

		# XXX: use the right class for the data type
		neighbor.router_id        = local.get('router-id',None)
		neighbor.peer_address     = local.get('peer-address',None)
		neighbor.local_address    = local.get('local-address',None)
		neighbor.local_as         = local.get('local-as',None)
		neighbor.peer_as          = local.get('peer-as',None)
		neighbor.passive          = local.get('passive',False)
		neighbor.listen           = local.get('listen',0)
		neighbor.hold_time        = local.get('hold-time','')
		neighbor.host_name        = local.get('host-name',hostname())
		neighbor.domain_name      = local.get('domain-name',domainname())
		neighbor.md5              = local.get('md5',None)
		neighbor.description      = local.get('description','')
		neighbor.multisession     = local.get('multi-session',False)
		neighbor.operational      = local.get('operational',False)
		neighbor.add_path         = local.get('add-path',0)
		neighbor.flush            = local.get('auto-flush',True)
		neighbor.adjribout        = local.get('adj-rib-out',True)
		neighbor.asn4             = local.get('asn4',True)
		neighbor.aigp             = local.get('aigp',None)
		neighbor.ttl              = local.get('ttl-security',None)
		neighbor.group_updates    = local.get('group-updates',True)
		neighbor.route_refresh    = local.get('route-refresh',0)
		neighbor.graceful_restart = local.get('graceful-restart',0)

		neighbor.changes          = local.get('section-static',[]) + local.get('section-route',[])

		messages = local.get('operational-message',[])

		openfamilies = local.get('families','everything')
		# announce every family we known
		if neighbor.multisession and openfamilies == 'everything':
			# announce what is needed, and no more, no need to have lots of TCP session doing nothing
			_families = set()
			for change in neighbor.changes:
				_families.add((change.nlri.afi,change.nlri.safi))
			families = list(_families)
		elif openfamilies in ('all','everything'):
			families = NLRI.known_families()
		# only announce what you have
		elif openfamilies == 'minimal':
			_families = set()
			for change in neighbor.changes:
				_families.add((change.nlri.afi,change.nlri.safi))
			families = list(_families)
		else:
			families = openfamilies

		# add the families to the list of families known
		initial_families = list(neighbor.families())
		for family in families:
			if family not in initial_families:
				# we are modifying the data used by .families() here
				neighbor.add_family(family)

		if not neighbor.router_id:
			neighbor.router_id = neighbor.local_address

		if neighbor.graceful_restart is None:
			neighbor.graceful_restart = int(neighbor.hold_time)

		if neighbor.route_refresh:
			if neighbor.adjribout:
				self.logger.configuration('route-refresh requested, enabling adj-rib-out')

		missing = neighbor.missing()
		if missing:
			return self.error.set('incomplete neighbor, missing %s' % missing)

		if neighbor.local_address.afi != neighbor.peer_address.afi:
			return self.error.set('local-address and peer-address must be of the same family')

		if neighbor.peer_address.ip in self._neighbors:
			return self.error.set('duplicate peer definition %s' % neighbor.peer_address.ip)

		# check we are not trying to announce routes without the right MP announcement
		for family in neighbor.families():
			if family not in families:
				afi,safi = family
				return self.error.set('Trying to announce a route of type %s,%s when we are not announcing the family to our peer' % (afi,safi))

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
		# for line in str(neighbor).split('\n'):
		# 	self.logger.configuration(line)
		# self.logger.configuration("\n")

		return True
