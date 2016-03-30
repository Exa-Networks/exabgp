# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# Do not use __slots__ here, we never create enough of them to be worth it
# And it really break complex inheritance

from struct import pack
from struct import unpack

from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.direction import OUT
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.cidr import CIDR

from exabgp.protocol import Protocol
from exabgp.protocol.ip.icmp import ICMPType
from exabgp.protocol.ip.icmp import ICMPCode
from exabgp.protocol.ip.fragment import Fragment
from exabgp.protocol.ip.tcp.flag import TCPFlag

from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


# =================================================================== Flow Components

class IComponent (object):
	# all have ID
	# should have an interface for serialisation and put it here
	FLAG = False


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
	# reserved= 0x08  # 0b00001000
	LT        = 0x04  # 0b00000100
	GT        = 0x02  # 0b00000010
	EQ        = 0x01  # 0b00000001


class BinaryOperator (CommonOperator):
	# reserved= 0x0C  # 0b00001100
	NOT       = 0x02  # 0b00000010
	MATCH     = 0x01  # 0b00000001
	INCLUDE   = 0x00  # 0b00000000


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
	# Must be defined in subclasses
	CODE = -1
	NAME = ''

	# not used, just present for simplying the nlri generation
	operations = 0x0

	def __init__ (self, raw, netmask):
		self.cidr = CIDR(raw,netmask)

	def pack (self):
		raw = self.cidr.pack_nlri()
		# ID is defined in subclasses
		return "%s%s" % (chr(self.ID),raw)  # pylint: disable=E1101

	def __str__ (self):
		return str(self.cidr)

	@classmethod
	def make (cls, bgp):
		prefix,mask = CIDR.decode(AFI.ipv4,bgp)
		return cls(prefix,mask), bgp[CIDR.size(mask)+1:]


class IPrefix6 (IPrefix,IComponent,IPv6):
	# Must be defined in subclasses
	CODE = -1
	NAME = ''

	# not used, just present for simplying the nlri generation
	operations = 0x0

	def __init__ (self, raw, netmask, offset):
		self.cidr = CIDR(raw,netmask)
		self.offset = offset

	def pack (self):
		# ID is defined in subclasses
		return "%s%s%s%s" % (chr(self.ID),chr(self.cidr.mask),chr(self.offset),self.cidr.pack_ip())  # pylint: disable=E1101

	def __str__ (self):
		return "%s/%s" % (self.cidr,self.offset)

	@classmethod
	def make (cls, bgp):
		offset = ord(bgp[1])
		prefix,mask = CIDR.decode(AFI.ipv6,bgp[0]+bgp[2:])
		return cls(prefix,mask,offset), bgp[CIDR.size(mask)+2:]


class IOperation (IComponent):
	# need to implement encode which encode the value of the operator

	def __init__ (self, operations, value):
		self.operations = operations
		self.value = value
		self.first = None  # handled by pack/str

	def pack (self):
		l,v = self.encode(self.value)
		op = self.operations | _len_to_bit(l)
		return "%s%s" % (chr(op),v)

	def encode (self, value):
		raise NotImplementedError('this method must be implemented by subclasses')

	def decode (self, value):
		raise NotImplementedError('this method must be implemented by subclasses')


# class IOperationIPv4 (IOperation):
# 	def encode (self, value):
# 		return 4, socket.pton(socket.AF_INET,value)

class IOperationByte (IOperation):
	def encode (self, value):
		return 1,chr(value)

	def decode (self, bgp):
		return ord(bgp[0]),bgp[1:]


class IOperationByteShort (IOperation):
	def encode (self, value):
		if value < (1 << 8):
			return 1,chr(value)
		return 2,pack('!H',value)

	def decode (self, bgp):
		return unpack('!H',bgp[:2])[0],bgp[2:]


# String representation for Numeric and Binary Tests

class NumericString (object):
	OPERATION = 'numeric'
	operations = None
	value = None

	_string = {
		NumericOperator.LT: '<',
		NumericOperator.GT: '>',
		NumericOperator.EQ: '=',
		NumericOperator.LT | NumericOperator.EQ: '<=',
		NumericOperator.GT | NumericOperator.EQ: '>=',

		NumericOperator.AND | NumericOperator.LT: '&<',
		NumericOperator.AND | NumericOperator.GT: '&>',
		NumericOperator.AND | NumericOperator.EQ: '&=',
		NumericOperator.AND | NumericOperator.LT | NumericOperator.EQ: '&<=',
		NumericOperator.AND | NumericOperator.GT | NumericOperator.EQ: '&>=',
	}

	def __str__ (self):
		return "%s%s" % (self._string[self.operations & (CommonOperator.EOL ^ 0xFF)], self.value)


class BinaryString (object):
	OPERATION = 'binary'
	operations = None
	value = None

	_string = {
		BinaryOperator.INCLUDE: '',
		BinaryOperator.NOT:     '!',
		BinaryOperator.MATCH:   '=',
		BinaryOperator.AND | BinaryOperator.NOT:   '&!',
		BinaryOperator.AND | BinaryOperator.MATCH: '&=',
	}

	def __str__ (self):
		return "%s%s" % (self._string[self.operations & (CommonOperator.EOL ^ 0xFF)], self.value)


# Components ..............................

def converter (function, klass=None):
	def _integer (value):
		if klass is None:
			return function(value)
		try:
			return klass(value)
		except ValueError:
			return function(value)
	return _integer


def decoder (function, klass=int):
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
	NAME = 'destination-ipv4'


# Prefix
class Flow4Source (IPrefix4,FlowSource):
	NAME = 'source-ipv4'


# Prefix
class Flow6Destination (IPrefix6,FlowDestination):
	NAME = 'destination-ipv6'


# Prefix
class Flow6Source (IPrefix6,FlowSource):
	NAME = 'source-ipv6'


class FlowIPProtocol (IOperationByte,NumericString,IPv4):
	ID  = 0x03
	NAME = 'protocol'
	converter = staticmethod(converter(Protocol.named,Protocol))
	decoder = staticmethod(decoder(ord,Protocol))


class FlowNextHeader (IOperationByte,NumericString,IPv6):
	ID  = 0x03
	NAME = 'next-header'
	converter = staticmethod(converter(Protocol.named,Protocol))
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
	converter = staticmethod(converter(ICMPType.named))
	decoder = staticmethod(decoder(_number,ICMPType))


class FlowICMPCode (IOperationByte,BinaryString,IPv4,IPv6):
	ID = 0x08
	NAME = 'icmp-code'
	converter = staticmethod(converter(ICMPCode.named))
	decoder = staticmethod(decoder(_number,ICMPCode))


class FlowTCPFlag (IOperationByte,BinaryString,IPv4,IPv6):
	ID = 0x09
	NAME = 'tcp-flags'
	FLAG = True
	converter = staticmethod(converter(TCPFlag.named))
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
class FlowFragment (IOperationByteShort,BinaryString,IPv4):
	ID = 0x0C
	NAME = 'fragment'
	FLAG = True
	converter = staticmethod(converter(Fragment.named))
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
	kls = globals().get(content,None)
	if not isinstance(kls,type(IComponent)):
		continue
	if not issubclass(kls,IComponent):
		continue
	if issubclass(kls,IPv4):
		_afi = AFI.ipv4
	elif issubclass(kls,IPv6):
		_afi = AFI.ipv6
	else:
		continue
	_ID = getattr(kls,'ID',None)
	if not _ID:
		continue
	factory[_afi][_ID] = kls
	name = getattr(kls,'NAME')

	if issubclass(kls, IOperation):
		if issubclass(kls, BinaryString):
			decode[_afi][_ID] = 'binary'
		elif issubclass(kls, NumericString):
			decode[_afi][_ID] = 'numeric'
		else:
			raise RuntimeError('invalid class defined (string)')
	elif issubclass(kls, IPrefix):
		decode[_afi][_ID] = 'prefix'
	else:
		raise RuntimeError('unvalid class defined (type)')


# ..........................................................

def _unique ():
	value = 0
	while True:
		yield value
		value += 1


unique = _unique()


@NLRI.register(AFI.ipv4,SAFI.flow_ip)
@NLRI.register(AFI.ipv6,SAFI.flow_ip)
@NLRI.register(AFI.ipv4,SAFI.flow_vpn)
@NLRI.register(AFI.ipv6,SAFI.flow_vpn)
class Flow (NLRI):
	def __init__ (self, afi=AFI.ipv4, safi=SAFI.flow_ip, action=OUT.UNSET):
		NLRI.__init__(self,afi,safi,action)
		self.rules = {}
		self.nexthop = NoNextHop
		self.rd = RouteDistinguisher.NORD
		self.unique = unique.next()

	def __eq__ (self, other):
		return \
			self.rules == other.rules and \
			self.action == other.action and \
			self.nexthop == other.nexthop and \
			self.rd == other.rd

	def __ne__ (self, other):
		return not self.__eq__(other)

	def __lt__ (self, other):
		raise RuntimeError('comparing Flow for ordering does not make sense')

	def __le__ (self, other):
		raise RuntimeError('comparing Flow for ordering does not make sense')

	def __gt__ (self, other):
		raise RuntimeError('comparing Flow for ordering does not make sense')

	def __ge__ (self, other):
		raise RuntimeError('comparing Flow for ordering does not make sense')

	def __len__ (self):
		return len(self.pack())

	def add (self, rule):
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
			if rule.NAME.endswith('ipv6'):  # better way to check this ?
				self.afi = AFI(AFI.ipv6)
		self.rules.setdefault(ID,[]).append(rule)
		return True

	# The API requires addpath, but it is irrelevant here.
	def pack (self, negotiated=None):
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

		components = self.rd.pack() + ''.join(ordered_rules)

		l = len(components)
		if l < 0xF0:
			return "%s%s" % (chr(l),components)
		if l < 0x0FFF:
			return "%s%s" % (pack('!H',l | 0xF000),components)
		raise Notify(3,0,"my administrator attempted to announce a Flow Spec rule larger than encoding allows, protecting the innocent the only way I can")

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
			line = ''.join(str(_) for _ in s)
			if len(s) > 1:
				line = '[ %s ]' % line
			string.append(' %s %s' % (rules[0].NAME,line))
		nexthop = ' next-hop %s' % self.nexthop if self.nexthop is not NoNextHop else ''
		rd = '' if self.rd is RouteDistinguisher.NORD else str(self.rd)
		return 'flow' + ''.join(string) + rd + nexthop

	def __str__ (self):
		return self.extensive()

	def _json (self):
		string = []
		for index in sorted(self.rules):
			rules = self.rules[index]
			s = []
			for idx,rule in enumerate(rules):
				# only add ' ' after the first element
				if idx and not rule.operations & NumericOperator.AND:
					s.append(', ')
				if rule.FLAG:
					s.append(', '.join('"%s"' % flag for flag in rule.value.named_bits()))
				else:
					s.append('"%s"' % rule)
			string.append(' "%s": [ %s ]' % (rules[0].NAME,''.join(str(_) for _ in s).replace('""','')))
		nexthop = ', "next-hop": "%s"' % self.nexthop if self.nexthop is not NoNextHop else ''
		rd = '' if self.rd is RouteDistinguisher.NORD else ', %s' % self.rd.json()
		compatibility = ', "string": "%s"' % self.extensive()
		return '{' + ','.join(string) + rd + nexthop + compatibility + ' }'

	def json (self):
		# this is a stop gap so flow route parsing does not crash exabgp
		# delete unique when this is fixed
		return '"flow-%d": %s' % (self.unique,self._json())

	def index (self):
		return self.pack()

	@classmethod
	def unpack_nlri (cls, afi, safi, bgp, action, addpath):
		length,bgp = ord(bgp[0]),bgp[1:]

		if length & 0xF0 == 0xF0:  # bigger than 240
			extra,bgp = ord(bgp[0]),bgp[1:]
			length = ((length & 0x0F) << 16) + extra

		if length > len(bgp):
			raise Notify(3,10,'invalid length at the start of the the flow')

		over = bgp[length:]
		bgp = bgp[:length]

		nlri = Flow(afi,safi,action)

		if safi == SAFI.flow_vpn:
			nlri.rd = RouteDistinguisher(bgp[:8])
			bgp = bgp[8:]

		seen = []

		while bgp:
			what,bgp = ord(bgp[0]),bgp[1:]

			if what not in decode.get(afi,{}):
				raise Notify(3,10,'unknown flowspec component received for address family %d' % what)

			seen.append(what)
			if sorted(seen) != seen:
				raise Notify(3,10,'components are not sent in the right order %s' % seen)

			decoded = decode[afi][what]
			klass = factory[afi][what]

			if decoded == 'prefix':
				adding,bgp = klass.make(bgp)
				if not nlri.add(adding):
					raise Notify(3,10,'components are incompatible (two sources, two destinations, mix ipv4/ipv6) %s' % seen)
				# logger.parser(LazyFormat("added flow %s (%s) payload " % (klass.NAME,adding),bgp[:-len(left)]))
			else:
				end = False
				while not end:
					byte,bgp = ord(bgp[0]),bgp[1:]
					end = CommonOperator.eol(byte)
					operator = CommonOperator.operator(byte)
					length = CommonOperator.length(byte)
					value,bgp = bgp[:length],bgp[length:]
					adding = klass.decoder(value)
					nlri.add(klass(operator,adding))
					# logger.parser(LazyFormat("added flow %s (%s) operator %d len %d payload " % (klass.NAME,adding,byte,length),value))

		return nlri, bgp+over
