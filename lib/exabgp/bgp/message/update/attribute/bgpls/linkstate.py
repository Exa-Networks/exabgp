# encoding: utf-8
"""
Copyright (c) 2016 Evelio Vila <eveliovila@gmail.com>
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import unpack
import binascii

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify


@Attribute.register()
class LINKSTATE(Attribute):
	ID = Attribute.CODE.BGP_LS
	FLAG = Attribute.Flag.OPTIONAL
	TLV = -1

	# Registered subclasses we know how to decode
	registered_lsids = dict()

	# what this implementation knows as LS attributes
	node_lsids = []
	link_lsids = []
	prefix_lsids = []

	def __init__(self, ls_attrs):
		self.ls_attrs = ls_attrs

	@classmethod
	def register(cls,lsid=None,flag=None):
		def register_lsid (klass):
			scode = klass.TLV if lsid is None else lsid
			if scode in cls.registered_lsids:
				raise RuntimeError('only one class can be registered per BGP link state attribute type')
			cls.registered_lsids[scode] = klass
			return klass
		return register_lsid

	@classmethod
	def registered(cls, lsid, flag=None):
		return lsid in cls.registered_lsids

	@classmethod
	def unpack(cls, data, negotiated):
		ls_attrs = []
		while data:
			scode, length = unpack('!HH',data[:4])
			if scode in cls.registered_lsids:
				klass = cls.registered_lsids[scode].unpack(data[4:length+4],length)
			else:
				klass = GenericLSID(scode,data[4:length+4])
			klass.TLV = scode
			ls_attrs.append(klass)
			data = data[length+4:]

		return cls(ls_attrs=ls_attrs)

	def json(self, compact=None):
		json_data = []
		for attr in self.ls_attrs:
			json_data.append(attr.json())
		return json_data

	def __str__(self):
		return ', '.join(str(d) for d in self.ls_attrs)

class GenericLSID(object):
	TLV = 99999

	def __init__ (self, code, rep):
		self.rep = rep
		self.code = code

	def __repr__ (self):
		return "Unknown attribute is: %s" % (self.rep)

	@classmethod
	def unpack (cls,scode,data):
		length = len(data)
		info = binascii.b2a_uu(data[:length])
		return cls(code=scode,rep=info)

