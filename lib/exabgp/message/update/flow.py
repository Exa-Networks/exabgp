# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2010-2012 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.structure.address import Address,AFI,SAFI
from exabgp.structure.ip import Prefix
from exabgp.message.update.attributes import Attributes
from exabgp.message.update.attribute.id import AttributeID
from exabgp.message.update.attribute.communities import ECommunities

from exabgp.log import Logger
logger = Logger()

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

# Interface ..................

class IPrefix (IComponent):
	# not used, just present for simplying the nlri generation
	operations = 0x0
	ID = None
	NAME = None

	def __init__ (self,ipv4,netmask):
		self.nlri = Prefix(AFI.ipv4,ipv4,netmask)

	def pack (self):
		raw = self.nlri.pack()
		return "%s%s" % (chr(self.ID),raw)

	def __str__ (self):
		return str(self.nlri)

	def __repr__ (self):
		return str(self)

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

	def encode (self,value):
		raise NotImplemented('this method must be implemented by subclasses')

#class IOperationIPv4 (IOperation):
#	def encode (self,value):
#		return 4, socket.pton(socket.AF_INET,value)

class IOperationByte (IOperation):
	def encode (self,value):
		return 1,chr(value)

class IOperationByteShort (IOperation):
	def encode (self,value):
		if value < (1<<8):
			return 1,chr(value)
		return 2,pack('!H',value)

# String representation for Numeric and Binary Tests

class NumericString (object):
	_string = {
		NumericOperator.LT   : '<',
		NumericOperator.GT   : '>',
		NumericOperator.EQ   : '=',
		NumericOperator.LT|NumericOperator.EQ : '<=',
		NumericOperator.GT|NumericOperator.EQ : '>=',

		NumericOperator.AND|NumericOperator.LT   : '&<',
		NumericOperator.AND|NumericOperator.GT   : '&>',
		NumericOperator.AND|NumericOperator.EQ   : '&=',
		NumericOperator.AND|NumericOperator.LT|NumericOperator.EQ : '&<=',
		NumericOperator.AND|NumericOperator.GT|NumericOperator.EQ : '&>=',
	}

	def __str__ (self):
		return "%s%s" % (self._string[self.operations & (CommonOperator.EOL ^ 0xFF) ], self.value)

	def __repr__ (self):
		return str(self)

class BinaryString (object):
	_string = {
		BinaryOperator.NOT   : '!',
		BinaryOperator.MATCH : '=',
		BinaryOperator.AND|BinaryOperator.NOT   : '&!',
		BinaryOperator.AND|BinaryOperator.MATCH : '&=',
	}

	def __str__ (self):
		return "%s%s" % (self._string[self.operations & (CommonOperator.EOL ^ 0xFF) ], self.value)

	def __repr__ (self):
		return str(self)

# Components ..............................

# Prefix
class Destination (IPrefix):
	ID = 0x01
	NAME = 'destination'

# Prefix
class Source (IPrefix):
	ID = 0x02
	NAME = 'source'

# NumericOperator
class IPProtocol (IOperationByte,NumericString):
	ID  = 0x03
	NAME = 'protocol'

# NumericOperator
class AnyPort (IOperationByteShort,NumericString):
	ID  = 0x04
	NAME = 'port'

# NumericOperator
class DestinationPort (IOperationByteShort,NumericString):
	ID  = 0x05
	NAME = 'destination-port'

# NumericOperator
class SourcePort (IOperationByteShort,NumericString):
	ID  = 0x06
	NAME = 'source-port'

# BinaryOperator
class ICMPType (IOperationByte,BinaryString):
	ID = 0x07
	NAME = 'icmp-type'

# BinaryOperator
class ICMPCode (IOperationByte,BinaryString):
	ID = 0x08
	NAME = 'icmp-code'

# BinaryOperator
class TCPFlag (IOperationByte,BinaryString):
	ID = 0x09
	NAME = 'tcp-flags'

# NumericOperator
class PacketLength (IOperationByteShort,NumericString):
	ID = 0x0A
	NAME = 'packet-length'

# NumericOperator
# RFC2474
class DSCP (IOperationByteShort,NumericString):
	ID = 0x0B
	NAME = 'dscp'

# BinaryOperator
class Fragment (IOperationByteShort,NumericString):
	ID = 0x0D
	NAME = 'fragment'

# ..........................................................

class _FlowNLRI (Attributes,Address):
	def __init__ (self,afi,safi):
		Attributes.__init__(self)
		Address.__init__(self,afi,safi)
		self.rules = {}

	def add_and (self,rule):
		ID = rule.ID
		if self.rules.has_key(ID):
			rule.first = False
			# Source and Destination do not use operations, it is just here to make the code simpler
			self.rules[ID][-1].operations |= CommonOperator.AND
		self.rules.setdefault(ID,[]).append(rule)
		return True

	def add_or (self,rule):
		ID = rule.ID
		# This test currently always fails (we do not call add_or with Source/Destinations).
		if ID in [Destination.ID, Source.ID]:
			return False
		if self.rules.has_key(ID):
			rule.first = False
		self.rules.setdefault(ID,[]).append(rule)
		return True

	def pack (self):
		ordered_rules = []

		# the order is a RFC requirement
		IDS = self.rules.keys()
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
				ordered_rules.append(rule)

		components = ''.join([rule.pack() for rule in ordered_rules])
		l = len(components)
		if l < 0xF0:
			data = "%s%s" % (chr(l),components)
		elif l < 0x0FFF:
			data = "%s%s" % (pack('!H',l | 0xF000),components)
		else:
			logger.critical("rule too big for NLRI - how to handle this - does this work ?")
			data = "%s" % chr(0)
		return data

	def __str__ (self):
		string = []
		for _,rules in self.rules.iteritems():
			s = []
			for rule in rules:
				if rule.operations & NumericOperator.AND:
					s.append(str(rule))
				else:
					s.append(' ')
					s.append(str(rule))
			string.append('%s %s' % (rules[0].NAME,''.join(s[1:])))
		return ' '.join(string)

	def __repr__ (self):
		return str(self)

class Flow (object):
	def __init__ (self,afi=AFI.ipv4,safi=SAFI.flow_ipv4):
		self.attributes = Attributes()
		self.nlri = _FlowNLRI(afi,safi)
		self.attributes[AttributeID.EXTENDED_COMMUNITY] = ECommunities()

	def add_and (self,rule):
		return self.nlri.add_and(rule)

	def add_or (self,rule):
		return self.nlri.add_or(rule)

	def add_action (self,community):
		self.attributes[AttributeID.EXTENDED_COMMUNITY].add(community)

	def __str__ (self):
		return "%s %s%s" % (Address.__str__(self.nlri),str(self.nlri),str(self.attributes))

	def __repr__ (self):
		return str(self)
