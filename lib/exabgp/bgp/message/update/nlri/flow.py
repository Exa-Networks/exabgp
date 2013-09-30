# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from struct import pack,unpack

from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address
from exabgp.bgp.message.direction import OUT
from exabgp.bgp.message.update.nlri.prefix import Prefix
from exabgp.bgp.message.notification import Notify

from exabgp.protocol import Protocol,NamedProtocol
from exabgp.protocol.ip.icmp import ICMPType,ICMPCode,NamedICMPType,NamedICMPCode
from exabgp.protocol.ip.fragment import Fragment,NamedFragment
from exabgp.protocol.ip.tcp.flag import TCPFlag,NamedTCPFlag

# =================================================================== Flow Components

class IComponent (object):
	# all have ID
	# should have an interface for serialisation and put it here
	pass

class CommonOperator (object):
	# power (2,x) is the same as 1 << x which is what the RFC say the len is
	power = {0:1, 1:2, 2:4, 3:8,}
	rewop = {1:0, 2:1, 4:2, 8:3,}
	len_position = 0x30

	EOL       = 0x80  # 0b10000000
	AND       = 0x40  # 0b01000000
	LEN       = 0x30  # 0b00110000
	NOP       = 0x00

	OPERATOR  = 0xFF ^ (EOL | LEN)

	@staticmethod
	def eol (data):
		return data & CommonOperator.EOL

	@staticmethod
	def operator (data):
		return data & CommonOperator.OPERATOR

	@staticmethod
	def length (data):
		return 1 << ((data & CommonOperator.LEN) >> 4)

class NumericOperator (CommonOperator):
#	reserved  = 0x08  # 0b00001000
	LT        = 0x04  # 0b00000100
	GT        = 0x02  # 0b00000010
	EQ        = 0x01  # 0b00000001

class BinaryOperator (CommonOperator):
#	reserved  = 0x0C  # 0b00001100
	NOT       = 0x02  # 0b00000010
	MATCH     = 0x01  # 0b00000001

def _len_to_bit (value):
	return NumericOperator.rewop[value] << 4

def _bit_to_len (value):
	return NumericOperator.power[(value & CommonOperator.len_position) >> 4]

def _number (string):
	value = 0
	for c in string:
		value = (value << 8) + ord(c)
	return value

# def short (value):
# 	return (ord(value[0]) << 8) + ord(value[1])

# Interface ..................

class IPv4 (object):
	afi = AFI.ipv4

class IPv6 (object):
	afi = AFI.ipv6

class IPrefix (object):
	pass

# Prococol

class IPrefix4 (IPrefix,IComponent,IPv4):
	# not used, just present for simplying the nlri generation
	operations = 0x0
	# NAME

	def __init__ (self,raw,netmask):
		self.nlri = Prefix(self.afi,SAFI.flow_ip,raw,netmask)

	def pack (self):
		raw = self.nlri.pack()
		return "%s%s" % (chr(self.ID),raw)

	def __str__ (self):
		return str(self.nlri)

class IPrefix6 (IPrefix,IComponent,IPv6):
	# not used, just present for simplying the nlri generation
	operations = 0x0
	# NAME

	def __init__ (self,raw,netmask,offset):
		self.nlri = Prefix(self.afi,SAFI.flow_ip,raw,netmask)
		self.offset = offset

	def pack (self):
		raw = self.nlri.packed_ip()
		return "%s%s%s%s" % (chr(self.ID),chr(self.nlri.mask),chr(self.offset),raw)

	def __str__ (self):
		return "%s/%s" % (self.nlri,self.offset)


class IOperation (IComponent):
	# need to implement encode which encode the value of the operator

	def __init__ (self,operations,value):
		self.operations = operations
		self.value = value
		self.first = None  # handled by pack/str

	def pack (self):
		l,v = self.encode(self.value)
		op = self.operations | _len_to_bit(l)
		return "%s%s" % (chr(op),v)

	def encode (self,value):
		raise NotImplemented('this method must be implemented by subclasses')

	def decode (self,value):
		raise NotImplemented('this method must be implemented by subclasses')

#class IOperationIPv4 (IOperation):
#	def encode (self,value):
#		return 4, socket.pton(socket.AF_INET,value)

class IOperationByte (IOperation):
	def encode (self,value):
		return 1,chr(value)

	def decode (self,bgp):
		return ord(bgp[0]),bgp[1:]

class IOperationByteShort (IOperation):
	def encode (self,value):
		if value < (1<<8):
			return 1,chr(value)
		return 2,pack('!H',value)

	def decode (self,bgp):
		return unpack('!H',bgp[:2])[0],bgp[2:]

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
		return "%s%s" % (self._string[self.operations & (CommonOperator.EOL ^ 0xFF)], self.value)


class BinaryString (object):
	_string = {
		BinaryOperator.NOT   : '!',
		BinaryOperator.MATCH : '=',
		BinaryOperator.AND|BinaryOperator.NOT   : '&!',
		BinaryOperator.AND|BinaryOperator.MATCH : '&=',
	}

	def __str__ (self):
		return "%s%s" % (self._string[self.operations & (CommonOperator.EOL ^ 0xFF)], self.value)

# Components ..............................

def converter (function,klass=int):
	def _integer (value):
		try:
			return klass(value)
		except ValueError:
			return function(value)
	return _integer

def decoder (function,klass=int):
	def _inner (value):
		return klass(function(value))
	return _inner

def PacketLength (data):
	_str_bad_length = "cloudflare already found that invalid max-packet length for for you .."
	number = int(data)
	if number > 0xFFFF:
		raise ValueError(_str_bad_length)
	return number

def PortValue (data):
	_str_bad_port = "you tried to set an invalid port number .."
	number = int(data)
	if number < 0 or number > 0xFFFF:
		raise ValueError(_str_bad_port)
	return number

def DSCPValue (data):
	_str_bad_dscp = "you tried to filter a flow using an invalid dscp for a component .."
	number = int(data)
	if number < 0 or number > 0xFFFF:
		raise ValueError(_str_bad_dscp)
	return number

def ClassValue (data):
	_str_bad_class = "you tried to filter a flow using an invalid traffic class for a component .."
	number = int(data)
	if number < 0 or number > 0xFFFF:
		raise ValueError(_str_bad_class)
	return number

def LabelValue (data):
	_str_bad_label = "you tried to filter a flow using an invalid traffic label for a component .."
	number = int(data)
	if number < 0 or number > 0xFFFFF:  # 20 bits 5 bytes
		raise ValueError(_str_bad_label)
	return number

# Protocol Shared

class FlowDestination (object):
	ID = 0x01
	NAME = 'destination'

class FlowSource (object):
	ID = 0x02
	NAME = 'source'

# Prefix
class Flow4Destination (IPrefix4,FlowDestination):
	pass

# Prefix
class Flow4Source (IPrefix4,FlowSource):
	pass

# Prefix
class Flow6Destination (IPrefix6,FlowDestination):
	pass

# Prefix
class Flow6Source (IPrefix6,FlowSource):
	pass

class FlowIPProtocol (IOperationByte,NumericString,IPv4):
	ID  = 0x03
	NAME = 'protocol'
	converter = staticmethod(converter(NamedProtocol,Protocol))
	decoder = staticmethod(decoder(ord,Protocol))

class FlowNextHeader (IOperationByte,NumericString,IPv6):
	ID  = 0x03
	NAME = 'next-header'
	converter = staticmethod(converter(NamedProtocol,Protocol))
	decoder = staticmethod(decoder(ord,Protocol))

class FlowAnyPort (IOperationByteShort,NumericString,IPv4,IPv6):
	ID  = 0x04
	NAME = 'port'
	converter = staticmethod(converter(PortValue))
	decoder = staticmethod(_number)

class FlowDestinationPort (IOperationByteShort,NumericString,IPv4,IPv6):
	ID  = 0x05
	NAME = 'destination-port'
	converter = staticmethod(converter(PortValue))
	decoder = staticmethod(_number)

class FlowSourcePort (IOperationByteShort,NumericString,IPv4,IPv6):
	ID  = 0x06
	NAME = 'source-port'
	converter = staticmethod(converter(PortValue))
	decoder = staticmethod(_number)

class FlowICMPType (IOperationByte,BinaryString,IPv4,IPv6):
	ID = 0x07
	NAME = 'icmp-type'
	converter = staticmethod(converter(NamedICMPType))
	decoder = staticmethod(decoder(_number,ICMPType))

class FlowICMPCode (IOperationByte,BinaryString,IPv4,IPv6):
	ID = 0x08
	NAME = 'icmp-code'
	converter = staticmethod(converter(NamedICMPCode))
	decoder = staticmethod(decoder(_number,ICMPCode))

class FlowTCPFlag (IOperationByte,BinaryString,IPv4,IPv6):
	ID = 0x09
	NAME = 'tcp-flags'
	converter = staticmethod(converter(NamedTCPFlag))
	decoder = staticmethod(decoder(ord,TCPFlag))

class FlowPacketLength (IOperationByteShort,NumericString,IPv4,IPv6):
	ID = 0x0A
	NAME = 'packet-length'
	converter = staticmethod(converter(PacketLength))
	decoder = staticmethod(_number)

# RFC2474
class FlowDSCP (IOperationByteShort,NumericString,IPv4):
	ID = 0x0B
	NAME = 'dscp'
	converter = staticmethod(converter(DSCPValue))
	decoder = staticmethod(_number)

# RFC2460
class FlowTrafficClass (IOperationByte,NumericString,IPv6):
	ID = 0x0B
	NAME = 'traffic-class'
	converter = staticmethod(converter(ClassValue))
	decoder = staticmethod(_number)

# BinaryOperator
class FlowFragment (IOperationByteShort,NumericString,IPv4):
	ID = 0x0C
	NAME = 'fragment'
	converter = staticmethod(converter(NamedFragment))
	decoder = staticmethod(decoder(ord,Fragment))

# draft-raszuk-idr-flow-spec-v6-01
class FlowFlowLabel (IOperationByteShort,NumericString,IPv6):
	ID = 0x0D
	NAME = 'flow-label'
	converter = staticmethod(converter(LabelValue))
	decoder = staticmethod(_number)


# ..........................................................

decode = {AFI.ipv4: {}, AFI.ipv6: {}}
factory = {AFI.ipv4: {}, AFI.ipv6: {}}

for content in dir():
	klass = globals().get(content,None)
	if not isinstance(klass,type(IComponent)):
		continue
	if not issubclass(klass,IComponent):
		continue
	if issubclass(klass,IPv4):
		afi = AFI.ipv4
	elif issubclass(klass,IPv6):
		afi = AFI.ipv6
	else:
		continue
	ID = getattr(klass,'ID',None)
	if not ID:
		continue
	factory[afi][ID] = klass
	name = getattr(klass,'NAME')

	if issubclass(klass, IOperation):
		if issubclass(klass, BinaryString):
			decode[afi][ID] = 'binary'
		elif issubclass(klass, NumericString):
			decode[afi][ID] = 'numeric'
		else:
			raise RuntimeError('invalid class defined (string)')
	elif issubclass(klass, IPrefix):
		decode[afi][ID] = 'prefix'
	else:
		raise RuntimeError('unvalid class defined (type)')

# ..........................................................

def _unique ():
	value = 0
	while True:
		yield value
		value += 1

unique = _unique()

class FlowNLRI (Address):
	def __init__ (self,afi=AFI.ipv4,safi=SAFI.flow_ip,rd=None):
		Address.__init__(self,afi,safi)
		self.rules = {}
		self.action = OUT.announce
		self.nexthop = None
		self.rd = rd

	def __len__ (self):
		return len(self.pack())

	def add (self,rule):
		ID = rule.ID
		if ID in (FlowDestination.ID,FlowSource.ID):
			if ID in self.rules:
				return False
			if ID == FlowDestination.ID:
				pair = self.rules.get(FlowSource.ID,[])
			else:
				pair = self.rules.get(FlowDestination.ID,[])
			if pair:
				if rule.afi != pair[0].afi:
					return False
		self.rules.setdefault(ID,[]).append(rule)
		return True

	# The API requires addpath, but it is irrelevant here.
	def pack (self,addpath=None):
		ordered_rules = []
		# the order is a RFC requirement
		for ID in sorted(self.rules.keys()):
			rules = self.rules[ID]
			# for each component get all the operation to do
			# the format use does not prevent two opposing rules meaning that no packet can ever match
			for rule in rules:
				rule.operations &= (CommonOperator.EOL ^ 0xFF)
			rules[-1].operations |= CommonOperator.EOL
			# and add it to the last rule
			if ID not in (FlowDestination.ID,FlowSource.ID):
				ordered_rules.append(chr(ID))
			ordered_rules.append(''.join(rule.pack() for rule in rules))

		components = ''.join(ordered_rules)

		if self.safi == SAFI.flow_vpn:
			components = self.rd.pack() + components

		l = len(components)
		if l < 0xF0:
			data = "%s%s" % (chr(l),components)
		elif l < 0x0FFF:
			data = "%s%s" % (pack('!H',l | 0xF000),components)
		else:
			raise Notify("rule too big for NLRI - how to handle this - does this work ?")
			data = "%s" % chr(0)

		return data

	def extensive (self):
		string = []
		for index in sorted(self.rules):
			rules = self.rules[index]
			s = []
			for idx,rule in enumerate(rules):
				# only add ' ' after the first element
				if idx and not rule.operations & NumericOperator.AND:
					s.append(' ')
				s.append(rule)
			string.append(' %s %s' % (rules[0].NAME,''.join(str(_) for _ in s)))
		nexthop = ' next-hop %s' % self.nexthop if self.nexthop else ''
		rd = str(self.rd) if self.rd else ''
		return 'flow' + rd + ''.join(string) + nexthop

	def __str__ (self):
		return self.extensive()

	def json (self):
		# this is a stop gap so flow route parsing does not crash exabgp
		# delete unique when this is fixed
		return '"flow-%d": { "string": "%s" }' % (unique.next(),str(self),)

	def index (self):
		return self.pack()


def _next_index ():
	value = 0
	while True:
		yield str(value)
		value += 1

next_index = _next_index()
