# encoding: utf-8
"""
rib/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from exabgp.rib.store import Store

class RIB:
	def __init__ (self,name,families,new=False):
		self.incoming = Store(False,families)
		self.outgoing = Store(True,families)

	def reset (self):
		self.incoming.reset()
		self.outgoing.reset()

	def resend (self,send_families,enhanced_refresh):
		self.outgoing.resend(send_families,enhanced_refresh)
