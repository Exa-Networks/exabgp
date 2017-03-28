# encoding: utf-8
"""
neighbor.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import uuid

from collections import deque

# collections.counter is python2.7 only ..
try:
	from collections import Counter
except ImportError:
	from exabgp.vendoring.counter import Counter

from exabgp.protocol.family import AFI

from exabgp.bgp.message import Message
from exabgp.bgp.message.open.capability import AddPath

from exabgp.rib import RIB


# The definition of a neighbor (from reading the configuration)
class Neighbor (object):
	def __init__ (self):
		# self.logger should not be used here as long as we do use deepcopy as it contains a Lock
		self.description = None
		self.router_id = None
		self.host_name = None
		self.domain_name = None
		self.local_address = None
		self.peer_address = None
		self.peer_as = None
		self.local_as = None
		self.hold_time = None
		self.asn4 = None
		self.add_path = None
		self.md5_password = None
		self.md5_ip = None
		self.ttl_in = None
		self.ttl_out = None
		self.group_updates = None
		self.flush = None
		self.adjribout = None

		self.manual_eor = False

		self.api = None

		# passive indicate that we do not establish outgoing connections
		self.passive = False
		# the port to listen on ( zero mean that we do not listen )
		self.listen = 0
		# the port to connect to
		self.connect = 0

		# capability
		self.route_refresh = False
		self.graceful_restart = False
		self.multisession = None
		self.add_path = None
		self.aigp = None

		self._families = []
		self.rib = None

		# The routes we have parsed from the configuration
		self.changes = []
		# On signal update, the previous routes so we can compare what changed
		self.backup_changes = []

		self.operational = None
		self.eor = deque()
		self.asm = dict()

		self.messages = deque()
		self.refresh = deque()

		self.counter = Counter()
		# It is possible to :
		# - have multiple exabgp toward one peer on the same host ( use of pid )
		# - have more than once connection toward a peer
		# - each connection has it own neihgbor (hence why identificator is not in Protocol)
		self.uid = '%d-%s' % (os.getpid(),uuid.uuid1())

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

	def add_family (self, family):
		# the families MUST be sorted for neighbor indexing name to be predictable for API users
		if family not in self.families():
			afi,safi = family
			d = dict()
			d[afi] = [safi,]
			for afi,safi in self._families:
				d.setdefault(afi,[]).append(safi)
			self._families = [(afi,safi) for afi in sorted(d) for safi in sorted(d[afi])]

	def remove_family (self, family):
		if family in self.families():
			self._families.remove(family)

	def missing (self):
		if self.local_address is None:
			return 'local-address'
		if self.peer_address is None:
			return 'peer-address'
		if self.local_as is None:
			return 'local-as'
		if self.peer_as is None:
			return 'peer-as'
		if self.peer_address.afi == AFI.ipv6 and not self.router_id:
			return 'router-id'
		return ''

	# This function only compares the neighbor BUT NOT ITS ROUTES
	def __eq__ (self, other):
		return \
			self.router_id == other.router_id and \
			self.local_address == other.local_address and \
			self.local_as == other.local_as and \
			self.peer_address == other.peer_address and \
			self.peer_as == other.peer_as and \
			self.passive == other.passive and \
			self.listen == other.listen and \
			self.connect == other.connect and \
			self.hold_time == other.hold_time and \
			self.host_name == other.host_name and \
			self.domain_name == other.domain_name and \
			self.md5_password == other.md5_password and \
			self.md5_ip == other.md5_ip and \
			self.ttl_in == other.ttl_in and \
			self.ttl_out == other.ttl_out and \
			self.route_refresh == other.route_refresh and \
			self.graceful_restart == other.graceful_restart and \
			self.multisession == other.multisession and \
			self.add_path == other.add_path and \
			self.operational == other.operational and \
			self.group_updates == other.group_updates and \
			self.flush == other.flush and \
			self.adjribout == other.adjribout and \
			self.families() == other.families()

	def __ne__ (self, other):
		return not self.__eq__(other)

	def string (self, with_changes=True):
		changes = ''
		if with_changes:
			changes += '\nstatic { '
			for changes in self.rib.incoming.queued_changes():
				changes += '\n\t\t%s' % changes.extensive()
			changes += '\n}'

		families = ''
		for afi,safi in self.families():
			families += '\n\t\t%s %s;' % (afi.name(),safi.name())

		codes = Message.CODE

		_extension_receive = {
			'receive-packets':                        'packets',
			'receive-parsed':                         'parsed',
			'receive-consolidate':                    'consolidate',
			'receive-%s' % codes.NOTIFICATION.SHORT:  'notification',
			'receive-%s' % codes.OPEN.SHORT:          'open',
			'receive-%s' % codes.KEEPALIVE.SHORT:     'keepalive',
			'receive-%s' % codes.UPDATE.SHORT:        'update',
			'receive-%s' % codes.ROUTE_REFRESH.SHORT: 'refresh',
			'receive-%s' % codes.OPERATIONAL.SHORT:   'operational',
		}

		_extension_send = {
			'send-packets':                        'packets',
			'send-parsed':                         'parsed',
			'send-consolidate':                    'consolidate',
			'send-%s' % codes.NOTIFICATION.SHORT:  'notification',
			'send-%s' % codes.OPEN.SHORT:          'open',
			'send-%s' % codes.KEEPALIVE.SHORT:     'keepalive',
			'send-%s' % codes.UPDATE.SHORT:        'update',
			'send-%s' % codes.ROUTE_REFRESH.SHORT: 'refresh',
			'send-%s' % codes.OPERATIONAL.SHORT:   'operational',
		}

		_receive = []
		for api,name in _extension_receive.items():
			_receive.extend(['\t\t\t%s;\n' % name,] if self.api[api] else [])
		receive = ''.join(_receive)

		_send = []
		for api,name in _extension_send.items():
			_send.extend(['\t\t\t%s;\n' % name,] if self.api[api] else [])
		send = ''.join(_send)

		returned = \
			'neighbor %s {\n' \
			'\tdescription "%s";\n' \
			'\trouter-id %s;\n' \
			'\thost-name %s;\n' \
			'\tdomain-name %s;\n' \
			'\tlocal-address %s;\n' \
			'\tlocal-as %s;\n' \
			'\tpeer-as %s;\n' \
			'\thold-time %s;\n' \
			'\tmanual-eor %s;\n' \
			'%s%s%s%s%s%s%s%s%s%s\n' \
			'\tcapability {\n' \
			'%s%s%s%s%s%s%s\t}\n' \
			'\tfamily {%s\n' \
			'\t}\n' \
			'\tapi {\n' \
			'%s%s\t}%s\n' \
			'}' % (
				self.peer_address,
				self.description,
				self.router_id,
				self.host_name,
				self.domain_name,
				self.local_address,
				self.local_as,
				self.peer_as,
				self.hold_time,
				'true' if self.manual_eor else 'false',
				'\n\tpassive %s;\n' % ('true' if self.passive else 'false'),
				'\n\tlisten %d;\n' % self.listen if self.listen else '',
				'\n\tconnect %d;\n' % self.connect if self.connect else '',
				'\tgroup-updates %s;\n' % ('true' if self.group_updates else 'false'),
				'\tauto-flush %s;\n' % ('true' if self.flush else 'false'),
				'\tadj-rib-out %s;\n' % ('true' if self.adjribout else 'false'),
				'\tmd5-password "%s";\n' % self.md5_password if self.md5_password else '',
				'\tmd5-ip "%s";\n' % self.md5_ip if self.md5_ip else '',
				'\toutgoing-ttl %s;\n' % self.ttl_out if self.ttl_out else '',
				'\tincoming-ttl %s;\n' % self.ttl_in if self.ttl_in else '',
				'\t\tasn4 %s;\n' % ('enable' if self.asn4 else 'disable'),
				'\t\troute-refresh %s;\n' % ('enable' if self.route_refresh else 'disable'),
				'\t\tgraceful-restart %s;\n' % (self.graceful_restart if self.graceful_restart else 'disable'),
				'\t\tadd-path %s;\n' % (AddPath.string[self.add_path] if self.add_path else 'disable'),
				'\t\tmulti-session %s;\n' % ('enable' if self.multisession else 'disable'),
				'\t\toperational %s;\n' % ('enable' if self.operational else 'disable'),
				'\t\taigp %s;\n' % ('enable' if self.aigp else 'disable'),
				families,
				'\t\treceive {\n%s\t\t}\n' % receive if receive else '',
				'\t\tsend {\n%s\t\t}\n' % send if send else '',
				changes
			)
		return returned.replace('\t','  ')

	def __str__ (self):
		return self.string(False)
