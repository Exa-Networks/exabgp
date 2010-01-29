#!/usr/bin/env python
# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2010 Exa Networks. All rights reserved.
"""

from struct import pack

from bgp.utils import *
from bgp.structure.address import Address,AFI,SAFI
from bgp.structure.ip import Prefix
from bgp.message.update.attributes import Attributes
from bgp.message.update.attribute.mprnlri import MPRNLRI
from bgp.message.update.attribute.communities import ECommunities
from bgp.message.update import Update,NLRIS

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
	NOP       = 0x00

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
		self.nlri = Prefix(AFI.ipv4,ipv4,netmask)

	def pack (self):
		raw = self.nlri.pack()
		return "%s%s" % (chr(self.ID),raw)

class IOperation (IComponent):
	# need to implement encode which encode the value of the operator
	
	def __init__ (self,operations,value):
		self.operations = operations
		self.value = value
		self.first = True

	def pack (self):
		l,v = self.encode(self.value)
		op = self.operations | _len_to_bit(l)
		if self.first:
			return "%s%s%s" % (chr(self.ID),chr(op),v)
		return "%s%s" % (chr(op),v)


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

class _DummyNLRI (object):
	def pack ():
		return ""

class _FlowNLRI (Attributes):
	def __init__ (self):
		Attributes.__init__(self)
		self.rules = []
		self.nlri = _DummyNLRI()

	def add (self,data):
		self.rules.append(data)
	
	def pack (self):
		components = ''.join([rule.pack() for rule in self.rules])
		l = len(components)
		if l < 0xF0:
			data = "%s%s" % (chr(l),components)
		elif l < 0x0FFF:
			data = "%s%s" % (pack('!H',l) | 0xF000,components)
		else:
			print "rule too big for NLRI - how to handle this - does this work ?"
			data = "%s" % chr(0)
		return data
		
	def __str__ (self):
		return 'Flow [ ' + ' '.join([hex(ord(_)) for _ in self.pack()]) + ' ]'
	
	def __repr__ (self):
		return str(self)

class Flow (Address):
	def __init__ (self,safi=SAFI.flow_ipv4):
		Address.__init__(self,AFI.ipv4,safi)
		self.rules = {}
		self.communities = ECommunities()

	def add_and (self,rule):
		ID = rule.ID
		if self.rules.has_key(ID):
			rule.first = False
			self.rules[ID][-1].operations |= CommonOperator.AND
		self.rules.setdefault(ID,[]).append(rule)
		return True

	def add_or (self,rule):
		ID = rule.ID
		if ID in [Destination, Source.ID]:
			return False
		if self.rules.has_key(ID):
			rule.first = False
		self.rules.setdefault(ID,[]).append(rule)
		return True

	def add_action (self,community):
		self.communities.add(community)

	def update (self):
		nlri = _FlowNLRI()
		# get all the possible type of component
		IDS = self.rules.keys()
		# the order is a RFC requirement
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
				nlri.add(rule)
		
		attributes = Attributes()
		attributes.add(MPRNLRI(self.afi,self.safi,nlri))
		attributes.add(self.communities)
		return Update(NLRIS(),NLRIS(),attributes)

