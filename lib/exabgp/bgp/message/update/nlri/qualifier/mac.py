# encoding: utf-8
"""
labels.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2014-2014 Orange. All rights reserved.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""



class MAC(object):

	def __init__(self,mac):
		'''
		mac: a colon separated MAC address (eg. "de:ad:00:00be:ef")
		'''
		self.bytes = MAC.bytesFromMac(mac)

	@staticmethod
	def bytesFromMac(mac):
		if not (isinstance(mac,str) or isinstance(mac,unicode)):
			raise Exception("cannot create MAC from something else than a string (%s was given)" % type(mac))
		try:
			bytesV = map(lambda x: int(x,16), mac.split(":"))
		except ValueError as e:
			raise Exception("wrong mac format (%s)" % e)

		if len(bytesV) != 6 :
			raise Exception("wrong mac format (must have six bytes)")

		for b in bytesV:
			if b>=256: raise Exception("wrong mac format (at least one value is too big))")

		return bytesV

	def __str__ (self):
		return ":".join( map(lambda x: ("0" if x<16 else "")+(hex(x).lower()[2:4]), self.bytes ) )

	def __repr__(self):
		return self.__str__()

	def pack (self):
		return pack("B"*len(self.bytes),*self.bytes)

	def __len__ (self):
		return 10

	def __cmp__(self,other):
		if (isinstance(other,MAC) and
				self.bytes == other.bytes):
			return 0
		else:
			return -1

	def __hash__(self): #FIXME: improve for better performance?
		return hash( self.__str__() )

	@staticmethod
	def unpack(data):
		bytesL = list(unpack("B"*len(data),data))

		return MAC( ":".join( map(lambda x: hex(x)[2:4], bytesL ) ) )


class MAC (object):
	def __init__ (self,bytes=None):
		self.esi = self.DEFAULT if bytes is None else bytes

	def __str__ (self):
		if self.esi == self.DEFAULT:
			return "-"
		return ":".join('%02x' % ord(_) for _ in self.esi)

	def __repr__ (self):
		return self.__str__()

	def pack (self):
		return self.esi

	def __len__ (self):
		return 10

	def __cmp__ (self,other):
		if not isinstance(other,self.__class__):
			return -1
		if self.esi != other.esi:
			return -1
		return 0

	def __hash__ (self):
		return hash(self.esi)

	@staticmethod
	def unpack (data):
		return ESI(data[:10])
