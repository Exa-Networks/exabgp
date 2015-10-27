# encoding: utf-8
"""
nlri.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message import OUT
from exabgp.bgp.message.notification import Notify

from exabgp.logger import Logger
from exabgp.logger import LazyNLRI


class NLRI (Family):
	__slots__ = ['action']

	EOR = False

	registered_nlri = dict()
	registered_families = [(AFI(AFI.ipv4), SAFI(SAFI.multicast))]
	logger = None

	def __init__ (self, afi, safi, action=OUT.UNSET):
		Family.__init__(self,afi,safi)
		self.action = action

	def assign (self, name, value):
		setattr(self,name,value)

	def index (self):
		return '%s%s%s' % (self.afi,self.safi,self.pack())

	# remove this when code restructure is finished
	def pack (self, negotiated=None):
		raise RuntimeError('deprecated API')

	def pack_nlri (self, negotiated=None):
		raise Exception('unimplemented in NLRI children class')

	def __eq__ (self,other):
		return self.index() == other.index()

	def __ne__ (self,other):
		return not self.__eq__(other)

	def __lt__ (self, other):
		raise RuntimeError('comparing NLRI for ordering does not make sense')

	def __le__ (self, other):
		raise RuntimeError('comparing NRLI for ordering does not make sense')

	def __gt__ (self, other):
		raise RuntimeError('comparing NLRI for ordering does not make sense')

	def __ge__ (self, other):
		raise RuntimeError('comparing NLRI for ordering does not make sense')

	@classmethod
	def has_label (cls):
		return False

	@classmethod
	def has_rd (cls):
		return False

	@classmethod
	def register (cls, afi, safi, force=False):
		def register_nlri (klass):
			new = (AFI(afi),SAFI(safi))
			if new in cls.registered_nlri:
				if force:
					# python has a bug and does not allow %ld/%ld (pypy does)
					cls.registered_nlri['%s/%s' % new] = klass
				else:
					raise RuntimeError('Tried to register %s/%s twice' % new)
			else:
				# python has a bug and does not allow %ld/%ld (pypy does)
				cls.registered_nlri['%s/%s' % new] = klass
				cls.registered_families.append(new)
			return klass
		return register_nlri

	@staticmethod
	def known_families ():
		# we do not want to take the risk of the caller modifying the list by accident
		# it can not be a generator
		return list(NLRI.registered_families)

	@classmethod
	def unpack_nlri (cls, afi, safi, data, action, addpath):
		if not cls.logger:
			cls.logger = Logger()
		cls.logger.parser(LazyNLRI(afi,safi,data))

		key = '%s/%s' % (AFI(afi),SAFI(safi))
		if key in cls.registered_nlri:
			return cls.registered_nlri[key].unpack_nlri(afi,safi,data,action,addpath)
		raise Notify(3,0,'trying to decode unknown family %s/%s' % (AFI(afi),SAFI(safi)))
