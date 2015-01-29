# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2013-02-26.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


class FakeAddPath (object):
	def send (self, afi, safi):  # pylint: disable=W0613
		return False

	def receive (self, afi, safi):  # pylint: disable=W0613
		return False


class FakeNegotiated (object):
	def __init__ (self, header, asn4):  # pylint: disable=W0613
		self.asn4 = asn4
		self.addpath = FakeAddPath()
