# encoding: utf-8
"""
neighbor/__init__.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# import sys
import socket
from copy import deepcopy

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.neighbor import Neighbor

from exabgp.bgp.message import OUT
from exabgp.bgp.message.open.holdtime import HoldTime

from exabgp.bgp.message.update.nlri.flow import NLRI

from exabgp.configuration.core import Section
from exabgp.configuration.neighbor.api import ParseAPI
from exabgp.configuration.family import ParseFamily

from exabgp.configuration.parser import boolean
from exabgp.configuration.parser import ip
from exabgp.configuration.parser import asn
from exabgp.configuration.parser import port
from exabgp.configuration.neighbor.parser import ttl
from exabgp.configuration.neighbor.parser import md5
from exabgp.configuration.neighbor.parser import hold_time
from exabgp.configuration.neighbor.parser import router_id
from exabgp.configuration.neighbor.parser import hostname
from exabgp.configuration.neighbor.parser import domainname
from exabgp.configuration.neighbor.parser import description
from exabgp.configuration.neighbor.parser import inherit


def _hostname ():
	value = socket.gethostname()
	if not value:
		return 'localhost'
	return value.split('.')[0]


def _domainname ():
	value = socket.gethostname()
	if not value:
		return 'localdomain'
	return ''.join(value.split('.')[1:])


class ParseNeighbor (Section):
	TTL_SECURITY = 255

	syntax = ''

	known = {
		'inherit':       inherit,
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
		'connect':       port,
		'outgoing-ttl':  ttl,
		'incoming-ttl':  ttl,
		'md5-password':  md5,
		'md5-ip':        router_id,
		'group-updates': boolean,
		'auto-flush':    boolean,
		'adj-rib-out':   boolean,
		'manual-eor':    boolean,
	}

	action = {
		'inherit':       'set-command',
		'description':   'set-command',
		'hostname':      'set-command',
		'domainname':    'set-command',
		'router-id':     'set-command',
		'hold-time':     'set-command',
		'local-address': 'set-command',
		'peer-address':  'set-command',
		'local-as':      'set-command',
		'peer-as':       'set-command',
		'passive':       'set-command',
		'listen':        'set-command',
		'connect':       'set-command',
		'outgoing-ttl':  'set-command',
		'incoming-ttl':  'set-command',
		'md5-password':  'set-command',
		'md5-ip':        'set-command',
		'group-updates': 'set-command',
		'auto-flush':    'set-command',
		'adj-rib-out':   'set-command',
		'manual-eor':    'set-command',
		'route':         'append-name',
	}

	default = {
		'passive': False,
		'group-updates': True,
		'auto-flush': True,
		'adj-rib-out': False,
		'manual-eor': False,
	}

	name = 'neighbor'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)
		self._neighbors = []
		self.neighbors = {}

	def clear (self):
		self._neighbors = []
		self.neighbors = {}

	def pre (self):
		self.scope.to_context()
		return self.parse(self.name,'peer-address')

	def post (self):
		local = self.scope.pop_context(self.name)
		neighbor = Neighbor()

		# XXX: use the right class for the data type
		# XXX: we can use the scope.nlri interface ( and rename it ) to set some values
		neighbor.router_id        = local.get('router-id',None)
		neighbor.peer_address     = local.get('peer-address',None)
		neighbor.local_address    = local.get('local-address',None)
		neighbor.local_as         = local.get('local-as',None)
		neighbor.peer_as          = local.get('peer-as',None)
		neighbor.passive          = local.get('passive',False)
		neighbor.listen           = local.get('listen',0)
		neighbor.connect          = local.get('connect',0)
		neighbor.hold_time        = local.get('hold-time',HoldTime(180))
		neighbor.host_name        = local.get('host-name',_hostname())
		neighbor.domain_name      = local.get('domain-name',_domainname())
		neighbor.md5_password     = local.get('md5-password',None)
		neighbor.md5_ip           = local.get('md5-ip',neighbor.local_address)
		neighbor.description      = local.get('description','')
		neighbor.flush            = local.get('auto-flush',True)
		neighbor.adjribout        = local.get('adj-rib-out',True)
		neighbor.aigp             = local.get('aigp',None)
		neighbor.ttl_out          = local.get('outgoing-ttl',None)
		neighbor.ttl_in           = local.get('incoming-ttl',None)
		neighbor.group_updates    = local.get('group-updates',True)
		neighbor.manual_eor       = local.get('manual-eor', False)

		neighbor.api              = ParseAPI.extract()

		# capabilities
		capability = local.get('capability',{})

		neighbor.add_path         = capability.get('add-path',0)
		neighbor.asn4             = capability.get('asn4',True)
		neighbor.multisession     = capability.get('multi-session',False)
		neighbor.operational      = capability.get('operational',False)
		neighbor.route_refresh    = capability.get('route-refresh',0)

		if capability.get('graceful-restart',False) is not False:
			neighbor.graceful_restart = capability.get('graceful-restart',0) or int(neighbor.hold_time)

		families = []
		for family in ParseFamily.convert.keys():
			for pair in local.get('family',{}).get(family,[]):
				families.append(pair)

		families = families or NLRI.known_families()

		if (AFI.ipv4,SAFI.unicast) not in families:
			families.append((AFI(AFI.ipv4),SAFI(SAFI.unicast)))

		for family in families:
			neighbor.add_family(family)

		neighbor.changes = []

		for section in ('static','l2vpn','flow'):
			routes = local.get(section,{}).get('routes',[])
			for route in routes:
				route.nlri.action = OUT.ANNOUNCE
			neighbor.changes.extend(routes)

		messages = local.get('operational',{}).get('routes',[])

		if not neighbor.router_id:
			neighbor.router_id = neighbor.local_address

		if neighbor.route_refresh:
			if neighbor.adjribout:
				self.logger.configuration('route-refresh requested, enabling adj-rib-out')

		missing = neighbor.missing()
		if missing:
			return self.error.set('incomplete neighbor, missing %s' % missing)

		if neighbor.local_address.afi != neighbor.peer_address.afi:
			return self.error.set('local-address and peer-address must be of the same family')

		if neighbor.peer_address.top() in self._neighbors:
			return self.error.set('duplicate peer definition %s' % neighbor.peer_address.top())
		self._neighbors.append(neighbor.peer_address.top())

		# check we are not trying to announce routes without the right MP announcement
		for change in neighbor.changes:
			family = change.nlri.family()
			if family not in families and family != (AFI.ipv4,SAFI.unicast):
				return self.error.set('Trying to announce a route of type %s,%s when we are not announcing the family to our peer' % change.nlri.family())

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
			self.neighbors[neighbor.name()] = neighbor

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

		return True

		# display configuration
		# for line in str(neighbor).split('\n'):
		# 	self.logger.configuration(line)
		# self.logger.configuration("\n")
