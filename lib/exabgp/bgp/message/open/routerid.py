# encoding: utf-8
"""
routerid.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.ip.inet import Inet,inet

# =================================================================== RouterID

class RouterID (Inet):
	def __init__ (self,ipv4):
		Inet.__init__(self,*inet(ipv4))
