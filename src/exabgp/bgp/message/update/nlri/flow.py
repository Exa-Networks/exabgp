"""flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json

from struct import pack

from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.ip.port import Port
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.action import Action
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

# Flow validation constants
MAX_PACKET_LENGTH = 0xFFFF  # Maximum packet length (16-bit value)
MAX_DSCP_VALUE = 0x3F  # Maximum DSCP value (6 bits, 0b00111111)
MAX_TRAFFIC_CLASS = 0xFFFF  # Maximum traffic class value (16-bit)
MAX_FLOW_LABEL = 0xFFFFF  # Maximum flow label value (20 bits)


class IComponent:
    # all have ID
    # should have an interface for serialisation and put it here
    FLAG = False


class CommonOperator:
    # power (2,x) is the same as 1 << x which is what the RFC say the len is
    power = {
        0: 1,
        1: 2,
        2: 4,
        3: 8,
    }
    rewop = {
        1: 0,
        2: 1,
        4: 2,
        8: 3,
    }
    len_position = 0x30

    EOL = 0x80  # 0b10000000
    AND = 0x40  # 0b01000000
    LEN = 0x30  # 0b00110000
    NOP = 0x00

    # The AND bit and the comparison bits, with the reserved bits left out. Each flavour of
    # operator reserves a different part of the low nibble, so the subclasses narrow this.
    OPERATOR = 0xFF ^ (EOL | LEN)

    @staticmethod
    def eol(data):
        return data & CommonOperator.EOL

    @classmethod
    def operator(cls, data):
        return data & cls.OPERATOR

    @staticmethod
    def length(data):
        return 1 << ((data & CommonOperator.LEN) >> 4)


class NumericOperator(CommonOperator):
    # reserved= 0x08  # 0b00001000
    LT = 0x04  # 0b00000100
    GT = 0x02  # 0b00000010
    EQ = 0x01  # 0b00000001
    NEQ = LT | GT
    TRUE = LT | GT | EQ
    FALSE = 0x00
    # RFC 8955 section 4.2.1.1 lays the octet out as | e | a | len | 0 | lt | gt | eq |, so
    # bit 0x08 is reserved and MUST be ignored on decoding. Keeping it left NumericString
    # unable to find 0x09 in its table, and a match on TCP reached the API as
    # `protocol 09tcp`.
    OPERATOR = CommonOperator.AND | TRUE


class BinaryOperator(CommonOperator):
    # reserved= 0x0C  # 0b00001100
    INCLUDE = 0x00  # 0b00000000
    NOT = 0x02  # 0b00000010
    MATCH = 0x01  # 0b00000001
    DIFF = NOT | MATCH
    # RFC 8955 section 4.2.1.2 lays the octet out as | e | a | len | 0 | 0 | not | m |, so
    # the two bits 0x0C are reserved and MUST be ignored on decoding, one more than the
    # numeric operator reserves.
    OPERATOR = CommonOperator.AND | DIFF


def _len_to_bit(value):
    return NumericOperator.rewop[value] << 4


def _bit_to_len(value):
    return NumericOperator.power[(value & CommonOperator.len_position) >> 4]


def _number(string):
    value = 0
    for c in string:
        value = (value << 8) + c
    return value


# Interface ..................


class IPv4:
    afi = AFI.ipv4


class IPv6:
    afi = AFI.ipv6


class IPrefix:
    pass


# Prococol


class IPrefix4(IPrefix, IComponent, IPv4):
    # Must be defined in subclasses
    CODE = -1
    NAME = ''

    # not used, just present for simplying the nlri generation
    operations = 0x0

    def __init__(self, raw, netmask):
        self.cidr = CIDR(raw, netmask)

    def pack(self):
        raw = self.cidr.pack_nlri()
        # ID is defined in subclasses
        return bytes([self.ID]) + raw  # pylint: disable=E1101

    def short(self):
        return str(self.cidr)

    def __str__(self):
        return str(self.cidr)

    @classmethod
    def make(cls, bgp):
        prefix, mask = CIDR.decode(AFI.ipv4, bgp)
        return cls(prefix, mask), bgp[CIDR.size(mask) + 1 :]


IPV6_ADDRESS_BITS = 128
IPV6_ADDRESS_BYTES = IPV6_ADDRESS_BITS // 8


def _pattern_size_bytes(length, offset):
    """How many octets the pattern of an IPv6 FlowSpec prefix takes.

    RFC 8956 section 3.1: "The encoded pattern contains enough octets for the bits used in
    matching (length minus offset bits)", not the ceil(length / 8) octets a plain prefix
    carries.  The two only agree when the offset is zero.
    """
    return (length - offset + 7) // 8


def _address_from_pattern(pattern, length, offset):
    """The sixteen octet address a pattern stands for: the pattern shifted right by offset.

    The padding is dropped rather than carried into the address.  RFC 8956 section 3.1
    says it "MUST be ignored on decoding", and two components describing the same match
    have to render alike and hash to the same RIB index.
    """
    bits = length - offset
    matched = int.from_bytes(pattern, 'big') >> (len(pattern) * 8 - bits) if bits > 0 else 0
    return (matched << (IPV6_ADDRESS_BITS - length)).to_bytes(IPV6_ADDRESS_BYTES, 'big')


def _pattern_from_address(address, length, offset):
    """The bits of an address between offset and length, left aligned and zero padded."""
    bits = length - offset
    if bits <= 0:
        return b''
    size = _pattern_size_bytes(length, offset)
    value = int.from_bytes(bytes(address).ljust(IPV6_ADDRESS_BYTES, b'\x00'), 'big')
    matched = (value >> (IPV6_ADDRESS_BITS - length)) & ((1 << bits) - 1)
    return (matched << (size * 8 - bits)).to_bytes(size, 'big')


class IPrefix6(IPrefix, IComponent, IPv6):
    # Must be defined in subclasses
    CODE = -1
    NAME = ''

    # not used, just present for simplying the nlri generation
    operations = 0x0

    def __init__(self, raw, netmask, offset):
        self.cidr = CIDR(raw, netmask)
        self.offset = offset

    def pack(self):
        """Pack to wire format: [ID][length][offset][pattern...]

        The pattern is the length-minus-offset bits of the address, left aligned, and not
        the whole prefix: a /64-104 goes out as the five octets RFC 8956 section 3.8.1
        writes rather than as thirteen no other implementation could read.  Routing it
        through the shared helper also zeroes the padding below the mask, which the old
        path did not: fe80::1/1 now goes out as 80 rather than fe.
        """
        length = self.cidr.mask
        pattern = _pattern_from_address(self.cidr.pack_ip(), length, self.offset)
        # ID is defined in subclasses
        return bytes([self.ID, length, self.offset]) + pattern  # pylint: disable=E1101

    def short(self):
        return '{}/{}'.format(self.cidr, self.offset)

    def __str__(self):
        return '{}/{}'.format(self.cidr, self.offset)

    @classmethod
    def make(cls, bgp):
        """Unpack from wire format [length][offset][pattern...].

        Sizing the pattern from the length alone, as a plain prefix is sized, read
        ceil(length / 8) octets where RFC 8956 section 3.1 writes
        ceil((length - offset) / 8).  The RFC's own first example then ran off the end of
        its NLRI and came back as an invalid NLRI: no IPv6 flow specification carrying an
        offset could be read at all, and none exabgp sent could be read by anybody else.
        """
        if len(bgp) < 2:
            raise Notify(3, 10, 'not enough data to extract the length and offset of a flow ipv6 prefix')
        length, offset = bgp[0], bgp[1]
        # RFC 8956 section 3.1: "If length = 0 and offset = 0, this component matches every
        # address; otherwise, length MUST be in the range offset < length < 129" or the
        # component is malformed.  The offset half was never compared to anything, so a
        # match on bits 64 through 32, which do not exist, was accepted from any peer.
        if (length, offset) != (0, 0) and not offset < length <= IPV6_ADDRESS_BITS:
            raise Notify(
                3,
                10,
                'flow ipv6 prefix of length %d and offset %d is outside the range RFC 8956 allows' % (length, offset),
            )
        size = _pattern_size_bytes(length, offset)
        pattern = bytes(bgp[2 : 2 + size])
        if len(pattern) != size:
            raise Notify(
                3,
                10,
                'flow ipv6 prefix needs %d octets of pattern but only %d are left' % (size, len(pattern)),
            )
        return cls(_address_from_pattern(pattern, length, offset), length, offset), bgp[2 + size :]


class IOperation(IComponent):
    # need to implement encode which encode the value of the operator

    def __init__(self, operations, value):
        self.operations = operations
        self.value = value
        self.first = None  # handled by pack/str

    def pack(self):
        length, value = self.encode(self.value)
        op = self.operations | _len_to_bit(length)
        return bytes([op]) + value

    def encode(self, value):
        raise NotImplementedError('this method must be implemented by subclasses')

    # def decode (self, value):
    # 	raise NotImplementedError('this method must be implemented by subclasses')


# class IOperationIPv4 (IOperation):
# 	def encode (self, value):
# 		return 4, socket.pton(socket.AF_INET,value)


class IOperationByte(IOperation):
    def encode(self, value):
        return 1, bytes([value])

    # def decode (self, bgp):
    # 	return bgp[0],bgp[1:]


class IOperationByteShort(IOperation):
    def encode(self, value):
        if value < (1 << 8):
            return 1, bytes([value])
        return 2, pack('!H', value)


class IOperationByteShortLong(IOperation):
    def encode(self, value):
        if value < (1 << 8):
            return 1, bytes([value])
        if value < (1 << 16):
            return 2, pack('!H', value)
        return 4, pack('!L', value)


# String representation for Numeric and Binary Tests


class NumericString:
    OPERATION = 'numeric'
    operations = None
    value = None

    _string = {
        NumericOperator.TRUE: 'true',
        NumericOperator.LT: '<',
        NumericOperator.GT: '>',
        NumericOperator.EQ: '=',
        NumericOperator.LT | NumericOperator.EQ: '<=',
        NumericOperator.GT | NumericOperator.EQ: '>=',
        NumericOperator.NEQ: '!=',
        NumericOperator.FALSE: 'false',
        NumericOperator.AND | NumericOperator.TRUE: '&true',
        NumericOperator.AND | NumericOperator.LT: '&<',
        NumericOperator.AND | NumericOperator.GT: '&>',
        NumericOperator.AND | NumericOperator.EQ: '&=',
        NumericOperator.AND | NumericOperator.LT | NumericOperator.EQ: '&<=',
        NumericOperator.AND | NumericOperator.GT | NumericOperator.EQ: '&>=',
        NumericOperator.AND | NumericOperator.NEQ: '&!=',
        NumericOperator.AND | NumericOperator.FALSE: '&false',
    }

    def short(self):
        op = self.operations & (CommonOperator.EOL ^ 0xFF)
        if op in [NumericOperator.TRUE, NumericOperator.FALSE]:
            return self._string[op]
        # ugly hack as dynamic languages are what they are and use used __str__ in the past
        value = self.value.short() if hasattr(self.value, 'short') else str(self.value)
        return '{}{}'.format(self._string.get(op, '{:02X}'.format(op)), value)

    def __str__(self):
        return self.short()


class BinaryString:
    OPERATION = 'binary'
    operations = None
    value = None

    _string = {
        BinaryOperator.INCLUDE: '',
        BinaryOperator.NOT: '!',
        BinaryOperator.MATCH: '=',
        BinaryOperator.NOT | BinaryOperator.MATCH: '!=',
        BinaryOperator.AND | BinaryOperator.INCLUDE: '&',
        BinaryOperator.AND | BinaryOperator.NOT: '&!',
        BinaryOperator.AND | BinaryOperator.MATCH: '&=',
        BinaryOperator.AND | BinaryOperator.NOT | BinaryOperator.MATCH: '&!=',
    }

    def short(self):
        op = self.operations & (CommonOperator.EOL ^ 0xFF)
        return '{}{}'.format(self._string.get(op, '{:02X}'.format(op)), self.value)

    def __str__(self):
        return self.short()


# Components ..............................


def converter(function, klass=None):
    def _integer(value):
        if klass is None:
            return function(value)
        try:
            return klass(value)
        except ValueError:
            return function(value)

    return _integer


def decoder(function, klass=int):
    def _inner(value):
        return klass(function(value))

    return _inner


def packet_length(data):
    _str_bad_length = 'cloudflare already found that invalid max-packet length for for you ..'
    number = int(data)
    if number > MAX_PACKET_LENGTH:
        raise ValueError(_str_bad_length)
    return number


def port_value(data):
    _str_bad_port = 'you tried to set an invalid port number ..'
    try:
        number = Port.named(data)
    except ValueError:
        raise ValueError(_str_bad_port) from None
    return number


def dscp_value(data):
    _str_bad_dscp = 'you tried to filter a flow using an invalid dscp for a component ..'
    number = int(data)
    if number < 0 or number > MAX_DSCP_VALUE:  # 0b00111111
        raise ValueError(_str_bad_dscp)
    return number


def class_value(data):
    _str_bad_class = 'you tried to filter a flow using an invalid traffic class for a component ..'
    number = int(data)
    if number < 0 or number > MAX_TRAFFIC_CLASS:
        raise ValueError(_str_bad_class)
    return number


def label_value(data):
    _str_bad_label = 'you tried to filter a flow using an invalid traffic label for a component ..'
    number = int(data)
    if number < 0 or number > MAX_FLOW_LABEL:  # 20 bits 5 bytes
        raise ValueError(_str_bad_label)
    return number


# Protocol Shared


class FlowDestination:
    ID = 0x01
    NAME = 'destination'


class FlowSource:
    ID = 0x02
    NAME = 'source'


# Prefix
class Flow4Destination(IPrefix4, FlowDestination):
    NAME = 'destination-ipv4'


# Prefix
class Flow4Source(IPrefix4, FlowSource):
    NAME = 'source-ipv4'


# Prefix
class Flow6Destination(IPrefix6, FlowDestination):
    NAME = 'destination-ipv6'


# Prefix
class Flow6Source(IPrefix6, FlowSource):
    NAME = 'source-ipv6'


class FlowIPProtocol(IOperationByte, NumericString, IPv4):
    ID = 0x03
    NAME = 'protocol'
    converter = staticmethod(converter(Protocol.named, Protocol))
    decoder = staticmethod(decoder(ord, Protocol))


class FlowNextHeader(IOperationByte, NumericString, IPv6):
    ID = 0x03
    NAME = 'next-header'
    converter = staticmethod(converter(Protocol.named, Protocol))
    decoder = staticmethod(decoder(ord, Protocol))


class FlowAnyPort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID = 0x04
    NAME = 'port'
    converter = staticmethod(converter(port_value))
    decoder = staticmethod(_number)


class FlowDestinationPort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID = 0x05
    NAME = 'destination-port'
    converter = staticmethod(converter(port_value))
    decoder = staticmethod(_number)


class FlowSourcePort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID = 0x06
    NAME = 'source-port'
    converter = staticmethod(converter(port_value))
    decoder = staticmethod(_number)


class FlowICMPType(IOperationByte, NumericString, IPv4, IPv6):
    ID = 0x07
    NAME = 'icmp-type'
    converter = staticmethod(converter(ICMPType.named, ICMPType))
    decoder = staticmethod(decoder(_number, ICMPType))


class FlowICMPCode(IOperationByte, NumericString, IPv4, IPv6):
    ID = 0x08
    NAME = 'icmp-code'
    converter = staticmethod(converter(ICMPCode.named, ICMPCode))
    decoder = staticmethod(decoder(_number, ICMPCode))


class FlowTCPFlag(IOperationByteShort, BinaryString, IPv4, IPv6):
    ID = 0x09
    NAME = 'tcp-flags'
    FLAG = True
    converter = staticmethod(converter(TCPFlag.named))
    decoder = staticmethod(decoder(_number, TCPFlag))


class FlowPacketLength(IOperationByteShort, NumericString, IPv4, IPv6):
    ID = 0x0A
    NAME = 'packet-length'
    converter = staticmethod(converter(packet_length))
    decoder = staticmethod(_number)


# RFC2474
class FlowDSCP(IOperationByte, NumericString, IPv4):
    ID = 0x0B
    NAME = 'dscp'
    converter = staticmethod(converter(dscp_value))
    decoder = staticmethod(_number)


# RFC2460
class FlowTrafficClass(IOperationByte, NumericString, IPv6):
    ID = 0x0B
    NAME = 'traffic-class'
    converter = staticmethod(converter(class_value))
    decoder = staticmethod(_number)


# RFC 8955 section 4.2.2.12 lays the fragment bitmask out as | 0 0 0 0 | LF FF IsF DF |,
# RFC 8956 section 3.6 as | 0 0 0 0 | LF FF IsF 0 |: IPv6 has no Don't Fragment header
# field, so the bit RFC 8955 gives to DF is a reserved zero for AFI 2.  Both documents say
# of their reserved bits "MUST be set to 0 on NLRI encoding and MUST be ignored during
# decoding", so what a family does not define is dropped as the value is read.  Kept, a
# bitmask of 0xF5 was rendered "dont-fragment+first-fragment+unknown fragment type 245",
# and an IPv6 bitmask of 0x01 was published as a match on a field IPv6 does not have.
FRAGMENT_BITS_IPV4 = Fragment.DONT | Fragment.IS | Fragment.FIRST | Fragment.LAST
FRAGMENT_BITS_IPV6 = Fragment.IS | Fragment.FIRST | Fragment.LAST


def _fragment(defined_bits):
    """Build the fragment value decoder of one family, dropping the bits it reserves."""

    def _masked(value):
        return Fragment(_number(value) & defined_bits)

    return _masked


# BinaryOperator
class FlowFragment(IOperationByteShort, BinaryString, IPv4):
    ID = 0x0C
    NAME = 'fragment'
    FLAG = True
    converter = staticmethod(converter(Fragment.named))
    # the value is one or two bytes, so ord() would raise on the two byte form
    decoder = staticmethod(_fragment(FRAGMENT_BITS_IPV4))


class FlowFragmentIPv6(IOperationByteShort, BinaryString, IPv6):
    """Type 12 for AFI 2, split from FlowFragment the way type 11 is already split between
    FlowDSCP and FlowTrafficClass: the component is the same on the wire but the set of
    bits the family defines is not, and the decoder is the only place that difference can
    be applied.
    """

    ID = 0x0C
    NAME = 'fragment'
    FLAG = True
    converter = staticmethod(converter(Fragment.named))
    decoder = staticmethod(_fragment(FRAGMENT_BITS_IPV6))


# draft-raszuk-idr-flow-spec-v6-01
class FlowFlowLabel(IOperationByteShortLong, NumericString, IPv6):
    ID = 0x0D
    NAME = 'flow-label'
    converter = staticmethod(converter(label_value))
    decoder = staticmethod(_number)


# ..........................................................

# Flow NLRI encoding constants
FLOW_LENGTH_EXTENDED_MASK = 0xF0  # Mask for extended length (upper 4 bits)
FLOW_LENGTH_EXTENDED_VALUE = 0xF0  # Value indicating extended length (240)
FLOW_LENGTH_LOWER_MASK = 0x0F  # Mask for lower 4 bits in extended length
# RFC 8955 section 4.1: an extended length is "encoded using 3 hex digits (0xfnnn)", so
# the low nibble of the first octet holds bits 8 to 11 of the length and the second octet
# holds bits 0 to 7.  This was 16, which read 0xf12c as 65580 rather than 300, so every
# Flow NLRI of 256 octets or more was refused with Notify(3, 10) - and that raise happens
# before the try in unpack_nlri, so a legal UPDATE from a conforming peer closed the
# session rather than invalidating one NLRI.  pack_nlri has always written the correct
# 12 bit form, so exabgp could not read back what it had just written.  Lengths 240 to
# 255 worked, because the nibble is zero there, which is why this lasted.
FLOW_LENGTH_EXTENDED_SHIFT = 8  # Shift for extended length calculation
FLOW_LENGTH_COMPACT_MAX = 0xF0  # Maximum length for compact encoding (240)
FLOW_LENGTH_EXTENDED_MAX = 0x0FFF  # Maximum length for extended encoding (4095)

decode = {AFI.ipv4: {}, AFI.ipv6: {}}
factory = {AFI.ipv4: {}, AFI.ipv6: {}}

for content in dir():
    kls = globals().get(content, None)
    if not isinstance(kls, type(IComponent)):
        continue
    if not issubclass(kls, IComponent):
        continue

    _ID = getattr(kls, 'ID', None)
    if not _ID:
        continue

    _afis = []
    if issubclass(kls, IPv4):
        _afis.append(AFI.ipv4)
    if issubclass(kls, IPv6):
        _afis.append(AFI.ipv6)

    for _afi in _afis:
        factory[_afi][_ID] = kls
        name = getattr(kls, 'NAME')

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


@NLRI.register(AFI.ipv4, SAFI.flow_ip)
@NLRI.register(AFI.ipv6, SAFI.flow_ip)
@NLRI.register(AFI.ipv4, SAFI.flow_vpn)
@NLRI.register(AFI.ipv6, SAFI.flow_vpn)
class Flow(NLRI):
    def __init__(self, afi=AFI.ipv4, safi=SAFI.flow_ip, action=Action.UNSET):
        NLRI.__init__(self, afi, safi, action)
        self.rules = {}
        self.nexthop = NoNextHop
        self.rd = RouteDistinguisher.NORD

    def feedback(self, action):
        if self.nexthop is None and action == Action.ANNOUNCE:
            return 'flow nlri next-hop missing'
        return ''

    def __len__(self):
        return len(self.pack())

    def add(self, rule):
        ID = rule.ID
        if ID in (FlowDestination.ID, FlowSource.ID):
            # re-enabled multiple source/destination as it is allowed by some vendor
            # if ID in self.rules:
            # 	return False
            if ID == FlowDestination.ID:
                pair = self.rules.get(FlowSource.ID, [])
            else:
                pair = self.rules.get(FlowDestination.ID, [])
            if pair:
                if rule.afi != pair[0].afi:
                    return False
            # TODO: verify if this is correct - why reset the afi of the NLRI object after initialisation?
            if rule.NAME.endswith('ipv6'):  # better way to check this ?
                self.afi = AFI.ipv6
        self.rules.setdefault(ID, []).append(rule)
        return True

    # The API requires addpath, but it is irrelevant here.
    def pack_nlri(self, negotiated=None):
        ordered_rules = []
        # the order is a RFC requirement
        for ID in sorted(self.rules.keys()):
            rules = self.rules[ID]
            # for each component get all the operation to do
            # the format use does not prevent two opposing rules meaning that no packet can ever match
            for rule in rules:
                rule.operations &= CommonOperator.EOL ^ 0xFF
            rules[-1].operations |= CommonOperator.EOL
            # and add it to the last rule
            if ID not in (FlowDestination.ID, FlowSource.ID):
                ordered_rules.append(bytes([ID]))
            ordered_rules.append(b''.join(rule.pack() for rule in rules))

        components = self.rd.pack() + b''.join(ordered_rules)

        lc = len(components)
        if lc < FLOW_LENGTH_COMPACT_MAX:
            return bytes([lc]) + components
        if lc < FLOW_LENGTH_EXTENDED_MAX:
            return pack('!H', lc | (FLOW_LENGTH_EXTENDED_VALUE << 8)) + components
        raise Notify(
            3,
            0,
            'my administrator attempted to announce a Flow Spec rule larger than encoding allows, protecting the innocent the only way I can',
        )

    def _rules(self):
        string = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            r_str = []
            for idx, rule in enumerate(rules):
                # only add ' ' after the first element
                if idx and not rule.operations & NumericOperator.AND:
                    r_str.append(' ')
                # ugly hack as dynamic languages are what they are and use used __str__ in the past
                r_str.append(rule.short() if hasattr(rule, 'short') else str(rule))
            line = ''.join(r_str)
            if len(r_str) > 1:
                line = '[ {} ]'.format(line)
            string.append(' {} {}'.format(rules[0].NAME, line))
        return ''.join(string)

    def extensive(self):
        nexthop = ' next-hop {}'.format(self.nexthop) if self.nexthop is not NoNextHop else ''
        rd = '' if self.rd is RouteDistinguisher.NORD else str(self.rd)
        return 'flow' + self._rules() + rd + nexthop

    def __str__(self):
        return self.extensive()

    def as_dict(self):
        family = self.family().afi_safi()
        r = {}
        for index in sorted(self.rules):
            rules = self.rules[index]
            s = []
            for idx, rule in enumerate(rules):
                if idx and rule.operations & NumericOperator.AND:
                    s[-1] = f'{s[-1]}{rule}'
                else:
                    s.append(f'{rule}')
            r[rules[0].NAME] = s

        flow = {
            'rules': r,
            'nexthop': None if self.nexthop is NoNextHop else str(self.nexthop),
            'rd': None if self.rd is RouteDistinguisher.NORD else self.rd._str(),
            'family': {'afi': f'{family[0]}', 'safi': f'{family[1]}'},
        }
        return flow

    def json(self, compact=None):
        # build the members and join them, a flow with no rule used to emit '{, ...'
        members = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            # rules joined by AND belong to one value, the rest are separate ones.
            # This used to be built from quoted fragments and then repaired with
            # .replace('""', ''), which ate the quotes of any rule rendering empty
            # and left '[ , "is-fragment" ]' behind.
            values = []
            for idx, rule in enumerate(rules):
                if idx and rule.operations & NumericOperator.AND:
                    values[-1] += str(rule)
                else:
                    values.append(str(rule))
            members.append('"{}": [ {} ]'.format(rules[0].NAME, ', '.join(json.dumps(_) for _ in values)))
        # an RD which is not NORD can still render empty, and an empty member breaks the join
        rd = '' if self.rd is RouteDistinguisher.NORD else self.rd.json()
        if rd:
            members.append(rd)
        if self.nexthop is not NoNextHop:
            members.append('"next-hop": {}'.format(json.dumps(str(self.nexthop))))
        members.append('"string": {}'.format(json.dumps(self.extensive())))
        return '{ ' + ', '.join(members) + ' }'

    @classmethod
    def unpack_nlri(cls, afi, safi, bgp, action, addpath):
        # RFC 7911 section 3: with ADD-PATH negotiated the peer puts a four byte Path
        # Identifier in front of every NLRI of this family, and it has to come off
        # before the NLRI is read.
        path_info, bgp = NLRI.consume_path_information(bgp, addpath)
        if not bgp:
            raise Notify(3, 10, 'not enough data to extract the length of the flow NLRI')

        length, bgp = bgp[0], bgp[1:]

        if length & FLOW_LENGTH_EXTENDED_MASK == FLOW_LENGTH_EXTENDED_VALUE:  # bigger than 240
            if not bgp:
                raise Notify(3, 10, 'not enough data to extract the extended length of the flow NLRI')
            extra, bgp = bgp[0], bgp[1:]
            length = ((length & FLOW_LENGTH_LOWER_MASK) << FLOW_LENGTH_EXTENDED_SHIFT) + extra

        if length > len(bgp):
            raise Notify(3, 10, 'invalid length at the start of the the flow')

        over = bgp[length:]

        bgp = bgp[:length]
        nlri = cls(afi, safi, action)
        nlri.addpath = path_info

        try:
            if safi == SAFI.flow_vpn:
                if len(bgp) < RouteDistinguisher.LENGTH:
                    raise Notify(3, 10, 'not enough data to extract the route distinguisher of the flow NLRI')
                nlri.rd = RouteDistinguisher(bgp[: RouteDistinguisher.LENGTH])
                bgp = bgp[RouteDistinguisher.LENGTH :]

            bgp = cls._unpack_components(afi, bgp, nlri)

            return nlri, bgp + over
        except Notify:
            return None, over
        except ValueError:
            return None, over
        except IndexError:
            return None, over

    @classmethod
    def _unpack_components(cls, afi, bgp, nlri):
        """Read the components of one flow NLRI into `nlri`, in the order they arrive.

        RFC 8955 section 10 defers to RFC 7606, so every refusal here is a
        treat-as-withdraw: the Notify is caught by `unpack_nlri`.
        """
        seen = []

        while bgp:
            what, bgp = bgp[0], bgp[1:]

            if what not in decode.get(afi, {}):
                raise Notify(3, 10, 'unknown flowspec component received for address family %d' % what)

            seen.append(what)
            if sorted(seen) != seen:
                raise Notify(3, 10, 'components are not sent in the right order {}'.format(seen))
            # RFC 8955 section 4.2: "a given component type MAY (exactly once) be present".
            # A packet matches the intersection of every component, so two type 3
            # components can never both hold, yet the second one's operations were appended
            # to the first one's list with its AND bit clear: "protocol tcp AND protocol
            # udp", which matches nothing, was reported as "protocol [ =tcp =udp ]", which
            # matches both.  A repeated destination or source prefix is the one relaxation,
            # because `add` has taken one from the configuration for years: some vendors
            # send it, and what exabgp will encode it has to be able to read back.
            if len(seen) > 1 and seen[-2] == what and what not in (FlowDestination.ID, FlowSource.ID):
                raise Notify(3, 10, 'flow component %d is present more than once' % what)

            decoded = decode[afi][what]
            klass = factory[afi][what]

            if decoded == 'prefix':
                adding, bgp = klass.make(bgp)
                if not nlri.add(adding):
                    raise Notify(
                        3,
                        10,
                        'components are incompatible (two sources, two destinations, mix ipv4/ipv6) {}'.format(seen),
                    )
            else:
                bgp = cls._unpack_operations(what, decoded, klass, bgp, nlri)

        # RFC 8955 section 4.2 encodes the value as <[component]+>, one component or more.
        # A filter with no component at all is the intersection of nothing, which matches
        # every packet, so a zero length NLRI reached the API as the bare string `flow` and
        # a controller acting on it would have rate limited or discarded all traffic on the
        # box.
        if not nlri.rules:
            raise Notify(3, 10, 'flow NLRI carries no component, which would match every packet')

        return bgp

    @staticmethod
    def _unpack_operations(what, decoded, klass, bgp, nlri):
        """Read the operator and value pairs of one component, up to its end of list.

        Returns what is left of the payload.
        """
        # RFC 8955 sections 4.2.1.1 and 4.2.1.2 reserve a different part of the operator
        # octet for each flavour, so the mask has to come from the component's own kind.
        operator_class = BinaryOperator if decoded == 'binary' else NumericOperator
        end = False
        first = True
        while not end:
            byte, bgp = bgp[0], bgp[1:]
            end = CommonOperator.eol(byte)
            operator = operator_class.operator(byte)
            if first:
                # RFC 8955 section 4.2.1.1: in the first operator octet of a sequence the
                # AND bit MUST be treated as always unset. Kept, it rendered as `&=tcp`,
                # an AND against a pair which does not exist.
                operator &= CommonOperator.AND ^ 0xFF
                first = False
            size = CommonOperator.length(byte)
            # the operator says how many bytes the value takes. If they are not there the
            # slice is short or empty, and the decoder either raises out of the reactor,
            # or worse invents a value and the filter carries a match the peer never sent.
            if len(bgp) < size:
                raise Notify(3, 10, 'flow component %d announces a %d byte value with %d left' % (what, size, len(bgp)))
            value, bgp = bgp[:size], bgp[size:]
            nlri.add(klass(operator, klass.decoder(value)))
        return bgp
