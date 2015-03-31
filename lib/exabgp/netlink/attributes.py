# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2015-03-31.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack
from struct import calcsize
from exabgp.netlink import NetLinkError


class AttributesError (NetLinkError):
	pass


class Attributes (object):
	class Header (object):
		PACK = 'HH'
		LEN = calcsize(PACK)

	class Type (object):
		IFA_UNSPEC     = 0x00
		IFA_ADDRESS    = 0x01
		IFA_LOCAL      = 0x02
		IFA_LABEL      = 0x03
		IFA_BROADCAST  = 0x04
		IFA_ANYCAST    = 0x05
		IFA_CACHEINFO  = 0x06
		IFA_MULTICAST  = 0x07

	@classmethod
	def decode (cls, data):
		while data:
			length, atype, = unpack(cls.Header.PACK,data[:cls.Header.LEN])
			if len(data) < length:
				raise AttributesError("Buffer underrun %d < %d" % (len(data),length))
			payload = data[cls.Header.LEN:length]
			yield atype, payload
			data = data[int((length + 3) / 4) * 4:]

	@classmethod
	def encode (cls, attributes):
		def _encode (atype, payload):
			def pad (length, to=4):
				return (length+to-1) & ~(to-1)
			length = cls.Header.LEN + len(payload)
			raw = pack(cls.Header.PACK,length,atype) + payload
			pad = pad(length) - len(raw)
			if pad:
				raw += '\0'*pad
			return raw

		return ''.join([_encode(k,v) for (k,v) in attributes.items()])
