# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2013-02-26.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

class FakeAddPath (object):
	def send (self,afi,safi):
		return False

	def receive (self,afi,safi):
		return False

class FakeNegotiated (object):
	def __init__ (self,header,asn4):
		self.asn4 = asn4
		self.addpath = FakeAddPath()
