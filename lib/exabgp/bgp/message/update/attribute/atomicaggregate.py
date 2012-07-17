#!/usr/bin/env python
# encoding: utf-8
"""
atomicaggregate.py

Created by Thomas Mangin on 2012-07-14.
Copyright (c) 2012 Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attribute import AttributeID,Flag,Attribute

# =================================================================== AtomicAggregate (6)

class AtomicAggregate (Attribute):
	ID = AttributeID.ATOMIC_AGGREGATE
	FLAG = Flag.TRANSITIVE
	MULTIPLE = False

	def pack (self):
		return self._attribute('')

	def __len__ (self):
		return 0

	def __str__ (self):
		return ''
