# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from collections import deque

from exabgp.protocol.family import AFI

from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.capability import AddPath

from exabgp.reactor.api.encoding import APIOptions

from exabgp.rib import RIB

# The definition of a neighbor (from reading the configuration)
class Neighbor (object):
	def __init__ (self):
		# self.logger should not be used here as long as we do use deepcopy as it contains a Lock
		self.description = ''
		self.router_id = None
		self.local_address = None
		self.peer_address = None
		self.peer_as = None
		self.local_as = None
		self.hold_time = HoldTime(180)
		self.asn4 = None
		self.add_path = 0
		self.md5 = None
		self.ttl = None
		self.group_updates = None
		self.flush = None
		self.adjribout = None

		self.api = APIOptions()

		self.passive = False

		# capability
		self.route_refresh = False
		self.graceful_restart = False
		self.multisession = None
		self.add_path = None
		self.aigp = None

		self._families = []
		self.rib = None

		self.operational = None
		self.asm = dict()

		self.messages = deque()
		self.refresh = deque()

	def make_rib (self):
		self.rib = RIB(self.name(),self.adjribout,self._families)

	# will resend all the routes once we reconnect
	def reset_rib (self):
		self.rib.reset()
		self.messages = deque()
		self.refresh = deque()

	# back to square one, all the routes are removed
	def clear_rib (self):
		self.rib.clear()
		self.messages = deque()
		self.refresh = deque()

	def name (self):
		if self.multisession:
			session = '/'.join("%s-%s" % (afi.name(),safi.name()) for (afi,safi) in self.families())
		else:
			session = 'in-open'
		return "neighbor %s local-ip %s local-as %s peer-as %s router-id %s family-allowed %s" % (self.peer_address,self.local_address,self.local_as,self.peer_as,self.router_id,session)

	def families (self):
		# this list() is important .. as we use the function to modify self._families
		return list(self._families)

	def add_family (self,family):
		# the families MUST be sorted for neighbor indexing name to be predictable for API users
		if not family in self.families():
			afi,safi = family
			d = dict()
			d[afi] = [safi,]
			for afi,safi in self._families:
				d.setdefault(afi,[]).append(safi)
			self._families = [(afi,safi) for afi in sorted(d) for safi in sorted(d[afi])]

	def remove_family (self,family):
		if family in self.families():
			self._families.remove(family)

	def missing (self):
		if self.local_address is None: return 'local-address'
		if self.peer_address is None: return 'peer-address'
		if self.local_as is None: return 'local-as'
		if self.peer_as is None: return 'peer-as'
		if self.peer_address.afi == AFI.ipv6 and not self.router_id: return 'router-id'
		return ''

	# This function only compares the neighbor BUT NOT ITS ROUTES
	def __eq__ (self,other):
		return \
			self.router_id == other.router_id and \
			self.local_address == other.local_address and \
			self.local_as == other.local_as and \
			self.peer_address == other.peer_address and \
			self.peer_as == other.peer_as and \
			self.passive == other.passive and \
			self.hold_time == other.hold_time and \
			self.md5 == other.md5 and \
			self.ttl == other.ttl and \
			self.route_refresh == other.route_refresh and \
			self.graceful_restart == other.graceful_restart and \
			self.multisession == other.multisession and \
			self.add_path == other.add_path and \
			self.operational == other.operational and \
			self.group_updates == other.group_updates and \
			self.flush == other.flush and \
			self.adjribout == other.adjribout and \
			self.families() == other.families()

	def __ne__(self, other):
		return not self.__eq__(other)

	def pprint (self,with_changes=True):
		changes=''
		if with_changes:
			changes += '\nstatic { '
			for changes in self.rib.incoming.queued_changes():
				changes += '\n    %s' % changes.extensive()
			changes += '\n}'

		families = ''
		for afi,safi in self.families():
			families += '\n    %s %s;' % (afi.name(),safi.name())

		_api  = []
		_api.extend(['    neighbor-changes;\n',]    if self.api.neighbor_changes else [])
		_api.extend(['    receive-packets;\n',]     if self.api.receive_packets else [])
		_api.extend(['    send-packets;\n',]        if self.api.send_packets else [])
		_api.extend(['    receive-routes;\n',]      if self.api.receive_routes else [])
		_api.extend(['    receive-operational;\n',] if self.api.receive_operational else [])
		api = ''.join(_api)

		return """\
neighbor %s {
  description "%s";
  router-id %s;
  local-address %s;
  local-as %s;
  peer-as %s;%s
  hold-time %s;
%s%s%s%s%s
  capability {
%s%s%s%s%s%s%s  }
  family {%s
  }
  process {
%s  }%s
}""" % (
	self.peer_address,
	self.description,
	self.router_id,
	self.local_address,
	self.local_as,
	self.peer_as,
	'\n  passive;\n' if self.passive else '',
	self.hold_time,
	'  group-updates: %s;\n' % self.group_updates if self.group_updates else '',
	'  auto-flush: %s;\n' % 'true' if self.flush else 'false',
	'  adj-rib-out: %s;\n' % 'true' if self.adjribout else 'false',
	'  md5: %d;\n' % self.ttl if self.ttl else '',
	'  ttl-security: %d;\n' % self.ttl if self.ttl else '',
	'    asn4 enable;\n' if self.asn4 else '    asn4 disable;\n',
	'    route-refresh;\n' if self.route_refresh else '',
	'    graceful-restart %s;\n' % self.graceful_restart if self.graceful_restart else '',
	'    add-path %s;\n' % AddPath.string[self.add_path] if self.add_path else '',
	'    multi-session;\n' if self.multisession else '',
	'    operational;\n' if self.operational else '',
	'    aigp;\n' if self.aigp else '',
	families,
	api,
	changes
)

	def __str__ (self):
		return self.pprint(False)
