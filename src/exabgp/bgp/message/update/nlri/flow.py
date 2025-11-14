"""flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Dict, List, Optional, Tuple, Type, Union

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

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
MAX_PACKET_LENGTH: int = 0xFFFF  # Maximum packet length (16-bit value)
MAX_DSCP_VALUE: int = 0x3F  # Maximum DSCP value (6 bits, 0b00111111)
MAX_TRAFFIC_CLASS: int = 0xFFFF  # Maximum traffic class value (16-bit)
MAX_FLOW_LABEL: int = 0xFFFFF  # Maximum flow label value (20 bits)


class IComponent:
    # all have ID
    # should have an interface for serialisation and put it here
    FLAG: ClassVar[bool] = False


class CommonOperator:
    # power (2,x) is the same as 1 << x which is what the RFC say the len is
    power: ClassVar[Dict[int, int]] = {
        0: 1,
        1: 2,
        2: 4,
        3: 8,
    }
    rewop: ClassVar[Dict[int, int]] = {
        1: 0,
        2: 1,
        4: 2,
        8: 3,
    }
    len_position: ClassVar[int] = 0x30

    EOL: ClassVar[int] = 0x80  # 0b10000000
    AND: ClassVar[int] = 0x40  # 0b01000000
    LEN: ClassVar[int] = 0x30  # 0b00110000
    NOP: ClassVar[int] = 0x00

    OPERATOR: ClassVar[int] = 0xFF ^ (EOL | LEN)

    @staticmethod
    def eol(data: int) -> int:
        return data & CommonOperator.EOL

    @staticmethod
    def operator(data: int) -> int:
        return data & CommonOperator.OPERATOR

    @staticmethod
    def length(data: int) -> int:
        return 1 << ((data & CommonOperator.LEN) >> 4)


class NumericOperator(CommonOperator):
    # reserved= 0x08  # 0b00001000
    LT: ClassVar[int] = 0x04  # 0b00000100
    GT: ClassVar[int] = 0x02  # 0b00000010
    EQ: ClassVar[int] = 0x01  # 0b00000001
    NEQ: ClassVar[int] = LT | GT
    TRUE: ClassVar[int] = LT | GT | EQ
    FALSE: ClassVar[int] = 0x00


class BinaryOperator(CommonOperator):
    # reserved= 0x0C  # 0b00001100
    INCLUDE: ClassVar[int] = 0x00  # 0b00000000
    NOT: ClassVar[int] = 0x02  # 0b00000010
    MATCH: ClassVar[int] = 0x01  # 0b00000001
    DIFF: ClassVar[int] = NOT | MATCH


def _len_to_bit(value: int) -> int:
    return NumericOperator.rewop[value] << 4


def _bit_to_len(value: int) -> int:
    return NumericOperator.power[(value & CommonOperator.len_position) >> 4]


def _number(string: bytes) -> int:
    value = 0
    for c in string:
        value = (value << 8) + c
    return value


# Interface ..................


class IPv4:
    afi: ClassVar[AFI] = AFI.ipv4


class IPv6:
    afi: ClassVar[AFI] = AFI.ipv6


class IPrefix:
    pass


# Prococol


class IPrefix4(IPrefix, IComponent, IPv4):
    # Must be defined in subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = ''
    ID: ClassVar[int]

    # not used, just present for simplying the nlri generation
    operations: int = 0x0
    cidr: CIDR

    def __init__(self, raw: bytes, netmask: int) -> None:
        self.cidr = CIDR(raw, netmask)

    def pack(self) -> bytes:
        raw = self.cidr.pack_nlri()
        # ID is defined in subclasses
        return bytes([self.ID]) + raw  # type: ignore[no-any-return]  # pylint: disable=E1101

    def short(self) -> str:
        return str(self.cidr)

    def __str__(self) -> str:
        return str(self.cidr)

    @classmethod
    def make(cls, bgp: bytes) -> Tuple[IPrefix4, bytes]:
        prefix, mask = CIDR.decode(AFI.ipv4, bgp)
        return cls(prefix, mask), bgp[CIDR.size(mask) + 1 :]


class IPrefix6(IPrefix, IComponent, IPv6):
    # Must be defined in subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = ''
    ID: ClassVar[int]

    # not used, just present for simplying the nlri generation
    operations: int = 0x0
    cidr: CIDR
    offset: int

    def __init__(self, raw: bytes, netmask: int, offset: int) -> None:
        self.cidr = CIDR(raw, netmask)
        self.offset = offset

    def pack(self) -> bytes:
        # ID is defined in subclasses
        return bytes([self.ID, self.cidr.mask, self.offset]) + self.cidr.pack_ip()  # type: ignore[no-any-return]  # pylint: disable=E1101

    def short(self) -> str:
        return '{}/{}'.format(self.cidr, self.offset)

    def __str__(self) -> str:
        return '{}/{}'.format(self.cidr, self.offset)

    @classmethod
    def make(cls, bgp: bytes) -> Tuple[IPrefix6, bytes]:
        offset = bgp[1]
        prefix, mask = CIDR.decode(AFI.ipv6, bgp[0:1] + bgp[2:])
        return cls(prefix, mask, offset), bgp[CIDR.size(mask) + 2 :]


class IOperation(IComponent):
    # need to implement encode which encode the value of the operator
    operations: int
    value: Union[int, 'Protocol', 'Port', 'ICMPType', 'ICMPCode', 'TCPFlag', 'Fragment']
    first: Optional[bool]

    def __init__(
        self, operations: int, value: Union[int, 'Protocol', 'Port', 'ICMPType', 'ICMPCode', 'TCPFlag', 'Fragment']
    ) -> None:
        self.operations = operations
        self.value = value
        self.first = None  # handled by pack/str

    def pack(self) -> bytes:
        length, value = self.encode(self.value)
        op = self.operations | _len_to_bit(length)
        return bytes([op]) + value

    def encode(
        self, value: Union[int, 'Protocol', 'Port', 'ICMPType', 'ICMPCode', 'TCPFlag', 'Fragment']
    ) -> Tuple[int, bytes]:
        raise NotImplementedError('this method must be implemented by subclasses')

    # def decode (self, value):
    # 	raise NotImplementedError('this method must be implemented by subclasses')


# class IOperationIPv4 (IOperation):
# 	def encode (self, value):
# 		return 4, socket.pton(socket.AF_INET,value)


class IOperationByte(IOperation):
    def encode(self, value: int) -> Tuple[int, bytes]:
        return 1, bytes([value])

    # def decode (self, bgp):
    # 	return bgp[0],bgp[1:]


class IOperationByteShort(IOperation):
    def encode(self, value: int) -> Tuple[int, bytes]:
        if value < (1 << 8):
            return 1, bytes([value])
        return 2, pack('!H', value)


class IOperationByteShortLong(IOperation):
    def encode(self, value: int) -> Tuple[int, bytes]:
        if value < (1 << 8):
            return 1, bytes([value])
        if value < (1 << 16):
            return 2, pack('!H', value)
        return 4, pack('!L', value)


# String representation for Numeric and Binary Tests


class NumericString:
    OPERATION: ClassVar[str] = 'numeric'
    operations: Optional[int] = None
    value: Optional[Union[int, 'Protocol', 'ICMPType', 'ICMPCode']] = None

    _string: ClassVar[Dict[int, str]] = {
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

    def short(self) -> str:
        op = self.operations & (CommonOperator.EOL ^ 0xFF)  # type: ignore[operator]
        if op in [NumericOperator.TRUE, NumericOperator.FALSE]:
            return self._string[op]
        # ugly hack as dynamic languages are what they are and use used __str__ in the past
        value = self.value.short() if hasattr(self.value, 'short') else str(self.value)  # type: ignore[union-attr]
        return '{}{}'.format(self._string.get(op, '{:02X}'.format(op)), value)

    def __str__(self) -> str:
        return self.short()


class BinaryString:
    OPERATION: ClassVar[str] = 'binary'
    operations: Optional[int] = None
    value: Optional[Union[int, 'TCPFlag', 'Fragment']] = None

    _string: ClassVar[Dict[int, str]] = {
        BinaryOperator.INCLUDE: '',
        BinaryOperator.NOT: '!',
        BinaryOperator.MATCH: '=',
        BinaryOperator.NOT | BinaryOperator.MATCH: '!=',
        BinaryOperator.AND | BinaryOperator.INCLUDE: '&',
        BinaryOperator.AND | BinaryOperator.NOT: '&!',
        BinaryOperator.AND | BinaryOperator.MATCH: '&=',
        BinaryOperator.AND | BinaryOperator.NOT | BinaryOperator.MATCH: '&!=',
    }

    def short(self) -> str:
        op = self.operations & (CommonOperator.EOL ^ 0xFF)  # type: ignore[operator]
        return '{}{}'.format(self._string.get(op, '{:02X}'.format(op)), self.value)

    def __str__(self) -> str:
        return self.short()


# Components ..............................


def converter(
    function: Callable[[str], Union[int, 'Protocol', 'ICMPType', 'ICMPCode', 'TCPFlag']], klass: Optional[Type] = None
) -> Callable[[str], Union[int, 'Protocol', 'ICMPType', 'ICMPCode', 'TCPFlag']]:
    def _integer(value: str) -> Union[int, 'Protocol', 'ICMPType', 'ICMPCode', 'TCPFlag']:
        if klass is None:
            return function(value)
        try:
            return klass(value)  # type: ignore[no-any-return]
        except ValueError:
            return function(value)

    return _integer


def decoder(
    function: Callable[[bytes], int], klass: Type = int
) -> Callable[[bytes], Union[int, 'Protocol', 'ICMPType', 'ICMPCode', 'TCPFlag']]:
    def _inner(value: bytes) -> Union[int, 'Protocol', 'ICMPType', 'ICMPCode', 'TCPFlag']:
        return klass(function(value))  # type: ignore[no-any-return]

    return _inner


def packet_length(data: str) -> int:
    _str_bad_length = 'cloudflare already found that invalid max-packet length for for you ..'
    number = int(data)
    if number > MAX_PACKET_LENGTH:
        raise ValueError(_str_bad_length)
    return number


def port_value(data: str) -> int:
    _str_bad_port = 'you tried to set an invalid port number ..'
    try:
        number = Port.named(data)
    except ValueError:
        raise ValueError(_str_bad_port) from None
    return number


def dscp_value(data: str) -> int:
    _str_bad_dscp = 'you tried to filter a flow using an invalid dscp for a component ..'
    number = int(data)
    if number < 0 or number > MAX_DSCP_VALUE:  # 0b00111111
        raise ValueError(_str_bad_dscp)
    return number


def class_value(data: str) -> int:
    _str_bad_class = 'you tried to filter a flow using an invalid traffic class for a component ..'
    number = int(data)
    if number < 0 or number > MAX_TRAFFIC_CLASS:
        raise ValueError(_str_bad_class)
    return number


def label_value(data: str) -> int:
    _str_bad_label = 'you tried to filter a flow using an invalid traffic label for a component ..'
    number = int(data)
    if number < 0 or number > MAX_FLOW_LABEL:  # 20 bits 5 bytes
        raise ValueError(_str_bad_label)
    return number


# Protocol Shared


class FlowDestination:
    ID: ClassVar[int] = 0x01
    NAME: ClassVar[str] = 'destination'


class FlowSource:
    ID: ClassVar[int] = 0x02
    NAME: ClassVar[str] = 'source'


# Prefix
class Flow4Destination(IPrefix4, FlowDestination):
    NAME: ClassVar[str] = 'destination-ipv4'


# Prefix
class Flow4Source(IPrefix4, FlowSource):
    NAME: ClassVar[str] = 'source-ipv4'


# Prefix
class Flow6Destination(IPrefix6, FlowDestination):
    NAME: ClassVar[str] = 'destination-ipv6'


# Prefix
class Flow6Source(IPrefix6, FlowSource):
    NAME: ClassVar[str] = 'source-ipv6'


class FlowIPProtocol(IOperationByte, NumericString, IPv4):
    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'protocol'
    converter: ClassVar[Callable[[str], Union[int, Protocol]]] = staticmethod(converter(Protocol.named, Protocol))
    decoder: ClassVar[Callable[[bytes], Union[int, Protocol]]] = staticmethod(decoder(ord, Protocol))


class FlowNextHeader(IOperationByte, NumericString, IPv6):
    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'next-header'
    converter: ClassVar[Callable[[str], Union[int, Protocol]]] = staticmethod(converter(Protocol.named, Protocol))
    decoder: ClassVar[Callable[[bytes], Union[int, Protocol]]] = staticmethod(decoder(ord, Protocol))


class FlowAnyPort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x04
    NAME: ClassVar[str] = 'port'
    converter: ClassVar[Callable[[str], int]] = staticmethod(converter(port_value))
    decoder: ClassVar[Callable[[bytes], int]] = staticmethod(_number)


class FlowDestinationPort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x05
    NAME: ClassVar[str] = 'destination-port'
    converter: ClassVar[Callable[[str], int]] = staticmethod(converter(port_value))
    decoder: ClassVar[Callable[[bytes], int]] = staticmethod(_number)


class FlowSourcePort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x06
    NAME: ClassVar[str] = 'source-port'
    converter: ClassVar[Callable[[str], int]] = staticmethod(converter(port_value))
    decoder: ClassVar[Callable[[bytes], int]] = staticmethod(_number)


class FlowICMPType(IOperationByte, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x07
    NAME: ClassVar[str] = 'icmp-type'
    converter: ClassVar[Callable[[str], Union[int, ICMPType]]] = staticmethod(converter(ICMPType.named, ICMPType))
    decoder: ClassVar[Callable[[bytes], Union[int, ICMPType]]] = staticmethod(decoder(_number, ICMPType))


class FlowICMPCode(IOperationByte, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x08
    NAME: ClassVar[str] = 'icmp-code'
    converter: ClassVar[Callable[[str], Union[int, ICMPCode]]] = staticmethod(converter(ICMPCode.named, ICMPCode))
    decoder: ClassVar[Callable[[bytes], Union[int, ICMPCode]]] = staticmethod(decoder(_number, ICMPCode))


class FlowTCPFlag(IOperationByteShort, BinaryString, IPv4, IPv6):
    ID: ClassVar[int] = 0x09
    NAME: ClassVar[str] = 'tcp-flags'
    FLAG: ClassVar[bool] = True
    converter: ClassVar[Callable[[str], Union[int, TCPFlag]]] = staticmethod(converter(TCPFlag.named))
    decoder: ClassVar[Callable[[bytes], Union[int, TCPFlag]]] = staticmethod(decoder(_number, TCPFlag))


class FlowPacketLength(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x0A
    NAME: ClassVar[str] = 'packet-length'
    converter: ClassVar[Callable[[str], int]] = staticmethod(converter(packet_length))
    decoder: ClassVar[Callable[[bytes], int]] = staticmethod(_number)


# RFC2474
class FlowDSCP(IOperationByte, NumericString, IPv4):
    ID: ClassVar[int] = 0x0B
    NAME: ClassVar[str] = 'dscp'
    converter: ClassVar[Callable[[str], int]] = staticmethod(converter(dscp_value))
    decoder: ClassVar[Callable[[bytes], int]] = staticmethod(_number)


# RFC2460
class FlowTrafficClass(IOperationByte, NumericString, IPv6):
    ID: ClassVar[int] = 0x0B
    NAME: ClassVar[str] = 'traffic-class'
    converter: ClassVar[Callable[[str], int]] = staticmethod(converter(class_value))
    decoder: ClassVar[Callable[[bytes], int]] = staticmethod(_number)


# BinaryOperator
class FlowFragment(IOperationByteShort, BinaryString, IPv4, IPv6):
    ID: ClassVar[int] = 0x0C
    NAME: ClassVar[str] = 'fragment'
    FLAG: ClassVar[bool] = True
    converter: ClassVar[Callable[[str], Union[int, Fragment]]] = staticmethod(converter(Fragment.named))
    decoder: ClassVar[Callable[[bytes], Union[int, Fragment]]] = staticmethod(decoder(ord, Fragment))


# draft-raszuk-idr-flow-spec-v6-01
class FlowFlowLabel(IOperationByteShortLong, NumericString, IPv6):
    ID: ClassVar[int] = 0x0D
    NAME: ClassVar[str] = 'flow-label'
    converter: ClassVar[Callable[[str], int]] = staticmethod(converter(label_value))
    decoder: ClassVar[Callable[[bytes], int]] = staticmethod(_number)


# ..........................................................

# Flow NLRI encoding constants
FLOW_LENGTH_EXTENDED_MASK: int = 0xF0  # Mask for extended length (upper 4 bits)
FLOW_LENGTH_EXTENDED_VALUE: int = 0xF0  # Value indicating extended length (240)
FLOW_LENGTH_LOWER_MASK: int = 0x0F  # Mask for lower 4 bits in extended length
FLOW_LENGTH_EXTENDED_SHIFT: int = 16  # Shift for extended length calculation
FLOW_LENGTH_COMPACT_MAX: int = 0xF0  # Maximum length for compact encoding (240)
FLOW_LENGTH_EXTENDED_MAX: int = 0x0FFF  # Maximum length for extended encoding (4095)

decode: Dict[AFI, Dict[int, str]] = {AFI.ipv4: {}, AFI.ipv6: {}}
factory: Dict[AFI, Dict[int, Type[IComponent]]] = {AFI.ipv4: {}, AFI.ipv6: {}}

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
    rules: Dict[int, List[Union[IPrefix, IOperation]]]
    nexthop: Any
    rd: RouteDistinguisher

    def __init__(self, afi: AFI = AFI.ipv4, safi: SAFI = SAFI.flow_ip, action: Action = Action.UNSET) -> None:
        NLRI.__init__(self, afi, safi, action)
        self.rules = {}
        self.nexthop = NoNextHop
        self.rd = RouteDistinguisher.NORD

    def feedback(self, action: Action) -> str:
        if self.nexthop is None and action == Action.ANNOUNCE:
            return 'flow nlri next-hop missing'
        return ''

    def __len__(self) -> int:
        return len(self.pack())

    def add(self, rule: Union[IPrefix, IOperation]) -> bool:
        ID = rule.ID  # type: ignore[union-attr]
        if ID in (FlowDestination.ID, FlowSource.ID):
            # re-enabled multiple source/destination as it is allowed by some vendor
            # if ID in self.rules:
            # 	return False
            if ID == FlowDestination.ID:
                pair = self.rules.get(FlowSource.ID, [])
            else:
                pair = self.rules.get(FlowDestination.ID, [])
            if pair:
                if rule.afi != pair[0].afi:  # type: ignore[union-attr]
                    return False
            # TODO: verify if this is correct - why reset the afi of the NLRI object after initialisation?
            if rule.NAME.endswith('ipv6'):  # type: ignore[union-attr]
                self.afi = AFI.ipv6
        self.rules.setdefault(ID, []).append(rule)
        return True

    # The API requires addpath, but it is irrelevant here.
    def pack_nlri(self, negotiated: Negotiated = None) -> bytes:  # type: ignore[assignment]
        ordered_rules: List[bytes] = []
        # the order is a RFC requirement
        for ID in sorted(self.rules.keys()):
            rules = self.rules[ID]
            # for each component get all the operation to do
            # the format use does not prevent two opposing rules meaning that no packet can ever match
            for rule in rules:
                rule.operations &= CommonOperator.EOL ^ 0xFF  # type: ignore[union-attr]
            rules[-1].operations |= CommonOperator.EOL  # type: ignore[union-attr]
            # and add it to the last rule
            if ID not in (FlowDestination.ID, FlowSource.ID):
                ordered_rules.append(bytes([ID]))
            ordered_rules.append(b''.join(rule.pack() for rule in rules))  # type: ignore[union-attr]

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

    def _rules(self) -> str:
        string: List[str] = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            r_str: List[str] = []
            for idx, rule in enumerate(rules):
                # only add ' ' after the first element
                if idx and not rule.operations & NumericOperator.AND:  # type: ignore[union-attr]
                    r_str.append(' ')
                # ugly hack as dynamic languages are what they are and use used __str__ in the past
                r_str.append(rule.short() if hasattr(rule, 'short') else str(rule))
            line = ''.join(r_str)
            if len(r_str) > 1:
                line = '[ {} ]'.format(line)
            string.append(' {} {}'.format(rules[0].NAME, line))  # type: ignore[union-attr]
        return ''.join(string)

    def extensive(self) -> str:
        nexthop = ' next-hop {}'.format(self.nexthop) if self.nexthop is not NoNextHop else ''
        rd = '' if self.rd is RouteDistinguisher.NORD else str(self.rd)
        return 'flow' + self._rules() + rd + nexthop

    def __str__(self) -> str:
        return self.extensive()

    def json(self, compact: Optional[Any] = None) -> str:
        string: List[str] = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            s: List[str] = []
            for idx, rule in enumerate(rules):
                # only add ' ' after the first element
                if idx and not rule.operations & NumericOperator.AND:  # type: ignore[union-attr]
                    s.append(', ')
                s.append('"{}"'.format(rule))
            string.append(' "{}": [ {} ]'.format(rules[0].NAME, ''.join(str(_) for _ in s).replace('""', '')))  # type: ignore[union-attr]
        nexthop = ', "next-hop": "{}"'.format(self.nexthop) if self.nexthop is not NoNextHop else ''
        rd = '' if self.rd is RouteDistinguisher.NORD else ', {}'.format(self.rd.json())
        compatibility = ', "string": "{}"'.format(self.extensive())
        return '{' + ','.join(string) + rd + nexthop + compatibility + ' }'

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: bytes, action: Action, addpath: Any
    ) -> Tuple[Optional[Flow], bytes]:
        length, bgp = bgp[0], bgp[1:]

        if length & FLOW_LENGTH_EXTENDED_MASK == FLOW_LENGTH_EXTENDED_VALUE:  # bigger than 240
            extra, bgp = bgp[0], bgp[1:]
            length = ((length & FLOW_LENGTH_LOWER_MASK) << FLOW_LENGTH_EXTENDED_SHIFT) + extra

        if length > len(bgp):
            raise Notify(3, 10, 'invalid length at the start of the the flow')

        over = bgp[length:]

        bgp = bgp[:length]
        nlri = cls(afi, safi, action)

        try:
            if safi == SAFI.flow_vpn:
                nlri.rd = RouteDistinguisher(bgp[:8])
                bgp = bgp[8:]

            seen: List[int] = []

            while bgp:
                what, bgp = bgp[0], bgp[1:]

                if what not in decode.get(afi, {}):
                    raise Notify(3, 10, 'unknown flowspec component received for address family %d' % what)

                seen.append(what)
                if sorted(seen) != seen:
                    raise Notify(3, 10, 'components are not sent in the right order {}'.format(seen))

                decoded = decode[afi][what]
                klass = factory[afi][what]

                if decoded == 'prefix':
                    adding, bgp = klass.make(bgp)
                    if not nlri.add(adding):
                        raise Notify(
                            3,
                            10,
                            'components are incompatible (two sources, two destinations, mix ipv4/ipv6) {}'.format(
                                seen
                            ),
                        )
                else:
                    end = False
                    while not end:
                        byte, bgp = bgp[0], bgp[1:]
                        end = CommonOperator.eol(byte)
                        operator = CommonOperator.operator(byte)
                        length = CommonOperator.length(byte)
                        value, bgp = bgp[:length], bgp[length:]
                        adding = klass.decoder(value)
                        nlri.add(klass(operator, adding))  # type: ignore[arg-type]

            return nlri, bgp + over
        except Notify:
            return None, over
        except ValueError:
            return None, over
        except IndexError:
            return None, over
