# encoding: utf-8
"""
change.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


class Source (object):
	UNSET         = 0
	CONFIGURATION = 1
	API           = 2
	NETWORK       = 3


class Change (object):
	SOURCE = Source.UNSET

	__slots__ = ['nlri','attributes']

	def __init__ (self, nlri, attributes):
		self.nlri = nlri
		self.attributes = attributes

	def index (self):
		return '%02x%02x' % self.nlri.family() + self.nlri.index()

	def __eq__ (self, other):
		return self.nlri == other.nlri and self.attributes == other.attributes

	def __ne__ (self, other):
		return self.nlri != other.nlri or self.attributes != other.attributes

	def extensive (self):
		# If you change this you must change as well extensive in Update
		return "%s%s" % (str(self.nlri),str(self.attributes))

	def __str__ (self):
		return self.extensive()


class ConfigurationChange (Change):
	SOURCE = Source.CONFIGURATION


class APIChange (Change):
	SOURCE = Source.API


class NetworkChange (Change):
	SOURCE = Source.NETWORK
