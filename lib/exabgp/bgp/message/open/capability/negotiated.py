# encoding: utf-8
"""
negotiated.py

Created by Thomas Mangin on 2012-07-19.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.asn import ASN,AS_TRANS
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.capability.id import CapabilityID as CID


class Negotiated (object):
	def __init__ (self):
		self.sent_open = None
		self.received_open = None

		self.peer_as = ASN(0)
		self.families = []
		self.asn4 = False
		self.addpath = None
		self.multisession = False
		self.msg_size = 4096-19

	def sent (self,sent_open):
		self.sent_open = sent_open
		if self.received_open:
			self._negociate()

	def received (self,received_open):
		self.received_open = received_open
		if self.sent_open:
			self._negociate()
		#else:
		#	import pdb; pdb.set_trace()

	def _negociate (self):
		sent_capa = self.sent_open.capabilities
		recv_capa = self.received_open.capabilities

		self.holdtime = HoldTime(min(self.sent_open.hold_time,self.received_open.hold_time))

		self.addpath = RequirePath(self.sent_open,self.received_open)
		self.asn4 = sent_capa.announced(CID.FOUR_BYTES_ASN) and recv_capa.announced(CID.FOUR_BYTES_ASN)

		self.local_as = self.sent_open.asn
		self.peer_as = self.received_open.asn
		if self.received_open.asn == AS_TRANS:
			self.peer_as = recv_capa[CID.FOUR_BYTES_ASN]

		self.families = []
		if recv_capa.announced(CID.MULTIPROTOCOL_EXTENSIONS) \
		and sent_capa.announced(CID.MULTIPROTOCOL_EXTENSIONS):
			for family in recv_capa[CID.MULTIPROTOCOL_EXTENSIONS]:
				if family in sent_capa[CID.MULTIPROTOCOL_EXTENSIONS]:
					self.families.append(family)

		self.multisession = sent_capa.announced(CID.MULTISESSION_BGP) and recv_capa.announced(CID.MULTISESSION_BGP)

		if self.multisession:
			sent_ms_capa = set(sent_capa[CID.MULTISESSION_BGP])
			recv_ms_capa = set(recv_capa[CID.MULTISESSION_BGP])

			if sent_ms_capa == set([]):
				sent_ms_capa = set([CID.MULTIPROTOCOL_EXTENSIONS])
			if recv_ms_capa == set([]):
				recv_ms_capa = set([CID.MULTIPROTOCOL_EXTENSIONS])

			if sent_ms_capa != recv_ms_capa:
				self.multisession = (2,8,'multisession, our peer did not reply with the same sessionid')

			# The way we implement MS-BGP, we only send one MP per session
			# therefore we can not collide due to the way we generate the configuration

			for capa in sent_ms_capa:
				# no need to check that the capability exists, we generated it
				# checked it is what we sent and only send MULTIPROTOCOL_EXTENSIONS
				if sent_capa[capa] != recv_capa[capa]:
					self.multisession = (2,8,'when checking session id, capability %s did not match' % str(capa))
					break

		elif sent_capa.announced(CID.MULTISESSION_BGP):
			self.multisession = (2,9,'multisession is mandatory with this peer')

		# XXX: Does not work as the capa is not yet defined
		#if received_open.capabilities.announced(CID.EXTENDED_MESSAGE) \
		#and sent_open.capabilities.announced(CID.EXTENDED_MESSAGE):
		#	if self.peer.bgp.received_open_size:
		#		self.received_open_size = self.peer.bgp.received_open_size - 19

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

		receive = received_open.capabilities.get(CID.ADD_PATH,FalseDict())
		send = sent_open.capabilities.get(CID.ADD_PATH,FalseDict())

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
