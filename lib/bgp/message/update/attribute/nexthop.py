#!/usr/bin/env python
# encoding: utf-8
"""
attributes.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import socket

from bgp.utils import *
from bgp.message.inet import AFI,SAFI
from bgp.message.inet import to_NLRI, NLRI
from bgp.message.update.attribute.parent import Attribute,Flag

# =================================================================== NextHop (3)

def new_NextHop (data,afi=AFI.ipv4,safi=SAFI.unicast):
	return NextHop(NLRI(chr(len(data)*8)+data,afi,safi))

def to_NextHop (ip):
	return NextHop(to_NLRI(ip,32))

class NextHop (Attribute):
	ID = Attribute.NEXT_HOP
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def __init__ (self,value):
		Attribute.__init__(self,value)

	def pack (self):
		return self._attribute(socket.inet_pton(socket.AF_INET,self.value.ip()))

	def __len__ (self):
		return len(self.value) - 1

	def __str__ (self):
		return self.value.ip()
