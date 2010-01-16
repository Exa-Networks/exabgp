#!/usr/bin/env python
# encoding: utf-8
"""
address.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.interface import IByteStream
from bgp.structure.afi  import AFI
from bgp.structure.safi import SAFI

## =================================================================== Address

class Address (object):
	def __init__ (self,afi,safi):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)

# Opaque ByteString container of for NLRI
class NLRI (Address,IByteStream):
	def __init__ (self,afi,safi,nlri):
		Address.__init__(self,afi,safi)
		self.nlri = nlri

	def pack (self):
		return self.nlri.pack()
	
	def __len__ (self):
		return len(self.nlri)

