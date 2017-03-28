# encoding: utf-8
"""
negotiated.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.open.routerid import RouterID


class Negotiated (object):
	MAX_SIZE = 4096
	FREE_SIZE = MAX_SIZE - 19 - 2 - 2

	def __init__ (self, neighbor):
		self.neighbor = neighbor

		self.sent_open = None
		self.received_open = None

		self.holdtime = HoldTime(0)
		self.local_as = ASN(0)
		self.peer_as = ASN(0)
		self.families = []
		self.asn4 = False
		self.addpath = RequirePath()
		self.multisession = False
		self.msg_size = self.MAX_SIZE
		self.operational = False
		self.refresh = REFRESH.ABSENT  # pylint: disable=E1101
		self.aigp = None

	def sent (self, sent_open):
		self.sent_open = sent_open
		if self.received_open:
			self._negotiate()

	def received (self, received_open):
		self.received_open = received_open
		if self.sent_open:
			self._negotiate()

	def _negotiate (self):
		sent_capa = self.sent_open.capabilities
		recv_capa = self.received_open.capabilities

		self.holdtime = HoldTime(min(self.sent_open.hold_time,self.received_open.hold_time))

		self.addpath.setup(self.sent_open,self.received_open)
		self.asn4 = sent_capa.announced(Capability.CODE.FOUR_BYTES_ASN) and recv_capa.announced(Capability.CODE.FOUR_BYTES_ASN)
		self.operational = sent_capa.announced(Capability.CODE.OPERATIONAL) and recv_capa.announced(Capability.CODE.OPERATIONAL)

		self.local_as = self.sent_open.asn
		self.peer_as = self.received_open.asn
		if self.received_open.asn == AS_TRANS and self.asn4:
			self.peer_as = recv_capa.get(Capability.CODE.FOUR_BYTES_ASN,self.peer_as)

		self.families = []
		if \
			recv_capa.announced(Capability.CODE.MULTIPROTOCOL) and \
			sent_capa.announced(Capability.CODE.MULTIPROTOCOL):
			for family in recv_capa[Capability.CODE.MULTIPROTOCOL]:
				if family in sent_capa[Capability.CODE.MULTIPROTOCOL]:
					self.families.append(family)

		if recv_capa.announced(Capability.CODE.ENHANCED_ROUTE_REFRESH) and sent_capa.announced(Capability.CODE.ENHANCED_ROUTE_REFRESH):
			self.refresh = REFRESH.ENHANCED  # pylint: disable=E1101
		elif recv_capa.announced(Capability.CODE.ROUTE_REFRESH) and sent_capa.announced(Capability.CODE.ROUTE_REFRESH):
			self.refresh = REFRESH.NORMAL  # pylint: disable=E1101

		self.multisession  = sent_capa.announced(Capability.CODE.MULTISESSION) and recv_capa.announced(Capability.CODE.MULTISESSION)
		self.multisession |= sent_capa.announced(Capability.CODE.MULTISESSION_CISCO) and recv_capa.announced(Capability.CODE.MULTISESSION_CISCO)

		if self.multisession:
			sent_ms_capa = set(sent_capa[Capability.CODE.MULTISESSION])
			recv_ms_capa = set(recv_capa[Capability.CODE.MULTISESSION])

			if sent_ms_capa == set([]):
				sent_ms_capa = set([Capability.CODE.MULTIPROTOCOL])
			if recv_ms_capa == set([]):
				recv_ms_capa = set([Capability.CODE.MULTIPROTOCOL])

			if sent_ms_capa != recv_ms_capa:
				self.multisession = (2,8,'multisession, our peer did not reply with the same sessionid')

			# The way we implement MS-BGP, we only send one MP per session
			# therefore we can not collide due to the way we generate the configuration

			for capa in sent_ms_capa:
				# no need to check that the capability exists, we generated it
				# checked it is what we sent and only send MULTIPROTOCOL
				if sent_capa[capa] != recv_capa[capa]:
					self.multisession = (2,8,'when checking session id, capability %s did not match' % str(capa))
					break

		elif sent_capa.announced(Capability.CODE.MULTISESSION):
			self.multisession = (2,9,'multisession is mandatory with this peer')

		# XXX: Does not work as the capa is not yet defined
		# if received_open.capabilities.announced(Capability.CODE.EXTENDED_MESSAGE) \
		# and sent_open.capabilities.announced(Capability.CODE.EXTENDED_MESSAGE):
		# 	if self.peer.bgp.received_open_size:
		# 		self.received_open_size = self.peer.bgp.received_open_size - 19

	def validate (self, neighbor):
		if self.peer_as != neighbor.peer_as:
			return (2,2,'ASN in OPEN (%d) did not match ASN expected (%d)' % (self.received_open.asn,neighbor.peer_as))

		# RFC 6286 : https://tools.ietf.org/html/rfc6286
		# XXX: FIXME: check that router id is not self
		if self.received_open.router_id == RouterID('0.0.0.0'):
			return (2,3,'0.0.0.0 is an invalid router_id')

		if self.received_open.asn == neighbor.local_as:
			# router-id must be unique within an ASN
			if self.received_open.router_id == neighbor.router_id:
				return (2,3,'BGP Identifier collision, same router-id (%s) on both sides of this IBGP session' % self.received_open.router_id)

		if self.received_open.hold_time and self.received_open.hold_time < 3:
			return (2,6,'Hold Time is invalid (%d)' % self.received_open.hold_time)

		if self.multisession not in (True,False):
			# XXX: FIXME: should we not use a string and perform a split like we do elswhere ?
			# XXX: FIXME: or should we use this trick in the other case ?
			return self.multisession

		return None

	def nexthopself (self, afi):
		if afi in (AFI.ipv4,AFI.ipv6):
			# return self.sent_open.router_id
			return self.neighbor.local_address
		raise RuntimeError('nexthop self is not implemented for this family %s' % afi)

# =================================================================== RequirePath


class RequirePath (object):
	REFUSE = 0
	ACCEPT = 1
	ANNOUNCE = 2

	def __init__ (self):
		self._send = {}
		self._receive = {}

	def setup (self, received_open, sent_open):
		# A Dict always returning False
		class FalseDict (dict):
			def __getitem__ (self, key):
				return False

		receive = received_open.capabilities.get(Capability.CODE.ADD_PATH,FalseDict())
		send = sent_open.capabilities.get(Capability.CODE.ADD_PATH,FalseDict())

		# python 2.4 compatibility mean no simple union but using sets.Set
		union = []
		union.extend(send.keys())
		union.extend([k for k in receive.keys() if k not in send.keys()])

		for k in union:
			self._send[k] = bool(receive.get(k,self.REFUSE) & self.ANNOUNCE and send.get(k,self.REFUSE) & self.ACCEPT)
			self._receive[k] = bool(receive.get(k,self.REFUSE) & self.ACCEPT and send.get(k,self.REFUSE) & self.ANNOUNCE)

	def send (self, afi, safi):
		return self._send.get((afi,safi),False)

	def receive (self, afi, safi):
		return self._receive.get((afi,safi),False)
