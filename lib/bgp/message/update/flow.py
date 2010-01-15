#!/usr/bin/env python
# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from bgp.utils import *
from bgp.structure.family import AFI,SAFI
from bgp.message.inet import to_NLRI
from bgp.message.update.update import Route,MPRNLRI

# =================================================================== Flow Components

class IComponent (object):
	# all have ID
	# should have an interface for serialisation and put it here
	pass

class CommonOperator:
	# power (2,x) is the same as 1 << x which is what the RFC say the len is
	power = { 0:1, 1:2, 2:4, 3:8, }
	rewop = { 1:0, 2:1, 4:2, 8:3, }
	len_position = 0x30

	EOL       = 0x80
	AND       = 0x40

class NumericOperator (CommonOperator):
#	reserved  = 0x08
	LT        = 0x04
	GT        = 0x02
	EQ        = 0x01

class BinaryOperator (CommonOperator):
#	reserved  = 0x0C
	NOT       = 0x02
	MATCH     = 0x01

def _len_to_bit (value):
	return NumericOperator.rewop[value] << 4

def _bit_to_len (value):
	return NumericOperator.power[(value & CommonOperator.len_position) >> 4]

class Fragments:
#	reserved  = 0xF0
	DONT      = 0x08
	IS        = 0x40
	FIRST     = 0x20
	LAST      = 0x10

# Interface ..................

class IPrefix (IComponent):
	# not used, just present for simplying the nlri generation
	operations = 0x0

	def __init__ (self,ipv4,netmask):
		self.nlri = to_NLRI(ipv4,netmask)

	def pack (self):
		raw = self.nlri.pack()
		return "%s%s%s" % (chr(self.ID),chr(len(raw)),raw)

class IOperation (IComponent):
	# need to implement encode which encode the value of the operator
	
	def __init__ (self,operations,value):
		self.operations = operations
		self.value = value

	def pack (self):
		l,v = self.encode(self.value)
		op = self.operations | _len_to_bit(l)
		return "%s%s%s" % (chr(self.ID),chr(op),v)

class IOperationIPv4 (IOperation):
	def encode (self,value):
		return 4, socket.pton(socket.AF_INET,value)

class IOperationByte (IOperation):
	def encode (self,value):
		return 1,chr(value)

class IOperationByteShort (IOperation):
	def encode (self,value):
		if value < (1<<8):
			return 1,chr(value)
		return 2,pack('!H',value)

# Components ..............................

# Prefix
class Destination (IPrefix):
	ID = 0x01

# Prefix
class Source (IPrefix):
	ID = 0x02

# NumericOperator
class IPProtocol (IOperationByte):
	ID  = 0x03

# NumericOperator
class AnyPort (IOperationByteShort):
	ID  = 0x04

# NumericOperator
class SourcePort (IOperationByteShort):
	ID  = 0x06

# NumericOperator
class DestinationPort (IOperationByteShort):
	ID  = 0x07

# NumericOperator
class ICMP (IOperationByte):
	ID = 0x08

# BinaryOperator
class TCPFlag (IOperationByte):
	ID = 0x09

# NumericOperator
class PacketLength (IOperationByteShort):
	ID = 0x0A

# NumericOperator
# RFC2474
class DSCP (IOperationByteShort):
	ID = 0x0B

# BinaryOperator
class Fragment (IOperationByteShort):
	ID = 0x0D

# ..........................................................

class _DummyPrefix (object):
	def __init__ (self,parent):
		self.parent = parent
	
	def pack (self):
		return self.parent._pack()

class _DummyNH (object):
	def pack (self):
		return ""

class _DummyNLRI (object):
	def __init__ (self,afi,safi):
		self.data = []
		self.afi = afi
		self.safi = safi
		self.nlri = _DummyPrefix(self)
		self.next_hop = _DummyNH()
	
	def add (self,data):
		self.data.append(data)
	
	def _pack (self):
		components = ''.join(self.data)
		l = len(components)
		if l < 0xF0:
			size = chr(l)
		elif l < 0x0FFF:
			size = pack('!H',l) | 0xF000
		else:
			print "rule too big for NLRI - how to handle this - does this work ?"
			return "%s" % (chr(0))
		return "%s%s" % (size,components)
	
	def __str__ (self):
		return '[ ' + ' '.join([hex(ord(_)) for _ in self.pack()]) + ' ]'
	
	def __repr__ (self):
		return str(self)

class Policy (object):
	def __init__ (self,safi=SAFI.flow_ipv4):
		self.afi = AFI(AFI.ipv4)
		self.safi = SAFI(safi)
		self.rules = {}
		self.last = -1

	def add_and (self,rule):
		ID = rule.ID
		if self.last > 0:
			self.rules[ID][-1] |= CommonOperator.AND
		self.rules.setdefault(ID,[]).append(rule)
		return True

	def add_or (self,rule):
		ID = rule.ID
		if ID in [flow.Destination, flow.Source]:
			return False
		self.rules.setdefault(ID,[]).append(rule)
		return True

	def flow (self):
		nlri = _DummyNLRI(self.afi,self.safi)
		# get all the possible type of component
		IDS = self.rules.keys()
		# the RFC order is the best to use for packing
		IDS.sort()
		for ID in IDS:
			rules = self.rules[ID]
			# for each component get all the operation to do
			# the format use does not prevent two opposing rules meaning that no packet can ever match
			for rule in rules:
				# clear the EOL if it has been set (it should not have been done.)
				rule.operations &= (CommonOperator.EOL ^ 0xFF)
			# and add it to the last rule
			rules[-1].operations |= CommonOperator.EOL
			
			for rule in rules:
				nlri.add(rule.pack())
		
		route = Route(MPRNLRI(self.afi,self.safi,nlri))
		#route.attributes.append()
		return route
