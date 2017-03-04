# encoding: utf-8
"""
aggregator.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.ip import IPv4

from exabgp.bgp.message.update.attribute.attribute import Attribute


# =============================================================== AGGREGATOR (7)
#

class Aggregator (Attribute):
	ID = Attribute.CODE.AGGREGATOR
	FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
	CACHING = True

	__slots__ = ['asn','speaker','_str']

	def __init__ (self, asn, speaker):
		self.asn = asn
		self.speaker = speaker
		self._str = None

	def pack (self, negotiated):
		if negotiated.asn4:
			return self._attribute(self.asn.pack(True)+self.speaker.pack())
		elif self.asn.asn4():
			return self._attribute(self.asn.trans().pack()+self.speaker.pack()) + Aggregator4(self.asn,self.speaker).pack(negotiated)
		else:
			return self._attribute(self.asn.pack()+self.speaker.pack())

	def __len__ (self):
		raise RuntimeError('size can be 6 or 8 - we can not say - or can we ?')

	def __str__ (self):
		if not self._str:
			self._str = '%s:%s' % (self.asn,self.speaker)
		return self._str

	def json (self):
		return '{ "asn" : %d, "speaker" : "%d" }' % (self.asn,self.speaker)

	@classmethod
	def unpack (cls, data, negotiated):
		if negotiated.asn4:
			return cls(ASN.unpack(data[:4]),IPv4.unpack(data[-4:]))
		return cls(ASN.unpack(data[:2]),IPv4.unpack(data[-4:]))


# ============================================================== AGGREGATOR (18)
#

class Aggregator4 (Aggregator):
	ID = Attribute.CODE.AS4_AGGREGATOR
	__slots__ = ['pack']

	def pack (self, negotiated):
		return self._attribute(self.asn.pack(True)+self.speaker.pack())
