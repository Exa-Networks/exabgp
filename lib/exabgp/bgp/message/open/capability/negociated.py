# encoding: utf-8
"""
negociated.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.asn import ASN,AS_TRANS
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.capability.id import CapabilityID


class Negociated (object):
	def __init__ (self):
		self.sent_open = None
		self.received_open = None

		self.peer_as = ASN(0)
		self.families = []
		self.asn4 = False
		self.addpath = None
		self.msg_size = 4096-19

	def sent (self,sent_open):
		self.sent_open = sent_open
		if self.received_open:
			self._negociate()

	def received (self,received_open):
		self.received_open = received_open
		if self.sent_open:
			self._negociate()

	def _negociate (self):
		self.holdtime = HoldTime(min(self.sent_open.hold_time,self.received_open.hold_time))
		
		self.addpath = RequirePath(self.sent_open,self.received_open)
		self.asn4 = self.received_open.capabilities.announced(CapabilityID.FOUR_BYTES_ASN)

		self.local_as = self.sent_open.asn
		self.peer_as = self.received_open.asn
		if self.received_open.asn == AS_TRANS:
			self.peer_as = self.received_open.capabilities[CapabilityID.FOUR_BYTES_ASN]

		self.families = []
		if self.received_open.capabilities.announced(CapabilityID.MULTIPROTOCOL_EXTENSIONS) \
		and self.sent_open.capabilities.announced(CapabilityID.MULTIPROTOCOL_EXTENSIONS):
			for family in self.received_open.capabilities[CapabilityID.MULTIPROTOCOL_EXTENSIONS]:
				if family in self.sent_open.capabilities[CapabilityID.MULTIPROTOCOL_EXTENSIONS]:
					self.families.append(family)

		# XXX: Does not work as the capa is not yet defined
		#if received_open.capabilities.announced(CapabilityID.EXTENDED_MESSAGE) \
		#and sent_open.capabilities.announced(CapabilityID.EXTENDED_MESSAGE):
		#	if self.peer.bgp.received_open_size:
		#		self.received_open_size = self.peer.bgp.received_open_size - 19

	def asn4_problem (self):
		return self.sent_open.asn.asn4() and not self.asn4


# =================================================================== RequirePath

class RequirePath (object):
	REFUSE = 0
	ACCEPT = 1
	ANNOUNCE = 2

	def __init__(self,received_open,sent_open):
		# A Dict always returning False
		class FalseDict (dict):
			def __getitem__(self,key):
				return False

		receive = received_open.capabilities.get(CapabilityID.ADD_PATH,FalseDict())
		send = sent_open.capabilities.get(CapabilityID.ADD_PATH,FalseDict())

		self._send = {}
		self._receive = {}

		# python 2.4 compatibility mean no simple union but using sets.Set
		union = []
		union.extend(send.keys())
		union.extend([k for k in receive.keys() if k not in send.keys()])

		for k in union:
			self._send[k] = bool(receive.get(k,self.REFUSE) & self.ANNOUNCE and send.get(k,self.REFUSE) & self.ACCEPT)
			self._receive[k] = bool(receive.get(k,self.REFUSE) & self.ACCEPT and send.get(k,self.REFUSE) & self.ANNOUNCE)

	def send (self,afi,safi):
		return self._send.get((afi,safi),False)

	def receive (self,afi,safi):
		return self._receive.get((afi,safi),False)

