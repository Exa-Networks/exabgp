"""FlowSpec NLRI implementation (RFC 5575, RFC 8955).

This module implements BGP FlowSpec for traffic filtering rules.
FlowSpec allows BGP to distribute traffic filter rules that can be
used for DDoS mitigation, traffic engineering, and access control.

Key classes:
    Flow: The main NLRI class for FlowSpec rules
    IPrefix4/IPrefix6: Source/destination prefix components
    IOperation subclasses: Port, protocol, DSCP, TCP flag filters

Wire format:
    FlowSpec NLRI consists of a length prefix followed by ordered
    filter components. Each component has a type ID and encoded value.

Component types (RFC 5575 Section 4):
    ID 1: Destination prefix
    ID 2: Source prefix
    ID 3: IP protocol (IPv4) / Next header (IPv6)
    ID 4: Port (any)
    ID 5: Destination port
    ID 6: Source port
    ID 7: ICMP type
    ID 8: ICMP code
    ID 9: TCP flags
    ID 10: Packet length
    ID 11: DSCP (IPv4) / Traffic class (IPv6)
    ID 12: Fragment flags
    ID 13: Flow label (IPv6 only)

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from struct import pack
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Protocol as TypingProtocol,
    Self,
    Type,
)

from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    from exabgp.bgp.message.update.nlri.settings import FlowSettings

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.protocol import Protocol
from exabgp.protocol.family import AFI, SAFI, Family
from exabgp.protocol.ip import IP
from exabgp.protocol.ip.fragment import Fragment
from exabgp.protocol.ip.icmp import ICMPCode, ICMPType
from exabgp.protocol.ip.port import Port
from exabgp.protocol.ip.tcp.flag import TCPFlag
from exabgp.protocol.resource import BaseValue, NumericValue

# =================================================================== Flow Components


class FlowRule(TypingProtocol):
    """Protocol defining the common interface for flow rules (IPrefix and IOperation subclasses).

    Both IPrefix4/IPrefix6 and IOperation subclasses implement these attributes,
    allowing them to be used interchangeably in Flow NLRI rules collections.
    """

    ID: ClassVar[int]
    NAME: ClassVar[str]
    operations: int
    afi: ClassVar[AFI]

    def pack(self) -> bytes: ...

    def short(self) -> str: ...


# Flow validation constants
MAX_PACKET_LENGTH: int = 0xFFFF  # Maximum packet length (16-bit value)
MAX_DSCP_VALUE: int = 0x3F  # Maximum DSCP value (6 bits, 0b00111111)
MAX_TRAFFIC_CLASS: int = 0xFFFF  # Maximum traffic class value (16-bit)
MAX_FLOW_LABEL: int = 0xFFFFF  # Maximum flow label value (20 bits)


class IComponent:
    """Base interface for FlowSpec filter components.

    All FlowSpec components (prefixes, ports, protocols, etc.) inherit from this.
    Components must define ID (component type) and implement pack()/make().

    Attributes:
        ID: Component type identifier (set by subclasses)
        NAME: Human-readable component name (set by subclasses)
        FLAG: Component flag (default False)
        operations: Operator byte for non-prefix components (default 0 for prefixes)
        decoder: Value decoder function (set by subclasses)
    """

    ID: ClassVar[int]  # Component type identifier, set by subclasses
    NAME: ClassVar[str] = ''  # Human-readable name, set by subclasses
    FLAG: ClassVar[bool] = False
    decoder: ClassVar[Callable[[bytes], object]]  # Value decoder, set by subclasses

    # Operator byte - 0 for prefix types, set by IOperation subclasses
    operations: int = 0

    def pack(self) -> Buffer:
        """Pack the component to wire format. Must be overridden by subclasses."""
        raise NotImplementedError(f'{self.__class__.__name__} must implement pack()')

    @classmethod
    def make(cls, bgp: Buffer) -> tuple['IComponent', Buffer]:
        """Unpack component from wire format. Must be overridden by subclasses."""
        raise NotImplementedError(f'{cls.__name__} must implement make()')


class CommonOperator:
    """Base class for FlowSpec operator byte encoding (RFC 5575 Section 4).

    The operator byte format: [EOL][AND][LEN(2 bits)][OP(4 bits)]
    - EOL: End of list marker
    - AND: Logical AND with previous (vs OR)
    - LEN: Value length encoding (1, 2, 4, or 8 bytes)
    - OP: Operation-specific bits (numeric or binary)
    """

    # power (2,x) is the same as 1 << x which is what the RFC say the len is
    power: ClassVar[dict[int, int]] = {
        0: 1,
        1: 2,
        2: 4,
        3: 8,
    }
    rewop: ClassVar[dict[int, int]] = {
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

    # The AND bit and the comparison bits, with the reserved bits left out. Each flavour of
    # operator reserves a different part of the low nibble, so the subclasses narrow this.
    OPERATOR: ClassVar[int] = 0xFF ^ (EOL | LEN)

    @staticmethod
    def eol(data: int) -> int:
        return data & CommonOperator.EOL

    @classmethod
    def operator(cls, data: int) -> int:
        return data & cls.OPERATOR

    @staticmethod
    def length(data: int) -> int:
        return 1 << ((data & CommonOperator.LEN) >> 4)


class NumericOperator(CommonOperator):
    """Numeric comparison operators for FlowSpec (RFC 5575 Section 4.2.2).

    Used for port, length, DSCP comparisons. Supports <, >, =, !=, <=, >=.
    """

    # reserved= 0x08  # 0b00001000
    LT: ClassVar[int] = 0x04  # 0b00000100
    GT: ClassVar[int] = 0x02  # 0b00000010
    EQ: ClassVar[int] = 0x01  # 0b00000001
    NEQ: ClassVar[int] = LT | GT
    TRUE: ClassVar[int] = LT | GT | EQ
    FALSE: ClassVar[int] = 0x00
    # RFC 8955 section 4.2.1.1 lays the octet out as | e | a | len | 0 | lt | gt | eq |, so
    # bit 0x08 is reserved and MUST be ignored on decoding. Keeping it left NumericString
    # unable to find 0x09 in its table, and a match on TCP reached the API as `protocol
    # 09tcp`.
    OPERATOR: ClassVar[int] = CommonOperator.AND | TRUE


class BinaryOperator(CommonOperator):
    """Binary/bitmask operators for FlowSpec (RFC 5575 Section 4.2.2).

    Used for TCP flags and fragment flags. Supports include, match, not.
    """

    # reserved= 0x0C  # 0b00001100
    INCLUDE: ClassVar[int] = 0x00  # 0b00000000
    NOT: ClassVar[int] = 0x02  # 0b00000010
    MATCH: ClassVar[int] = 0x01  # 0b00000001
    DIFF: ClassVar[int] = NOT | MATCH
    # RFC 8955 section 4.2.1.2 lays the octet out as | e | a | len | 0 | 0 | not | m |, so
    # the two bits 0x0C are reserved and MUST be ignored on decoding, one more than the
    # numeric operator reserves.
    OPERATOR: ClassVar[int] = CommonOperator.AND | DIFF


def _len_to_bit(value: int) -> int:
    return NumericOperator.rewop[value] << 4


def _bit_to_len(value: int) -> int:
    return NumericOperator.power[(value & CommonOperator.len_position) >> 4]


# RFC 8955 section 4.2.1.1: the two length bits encode one, two, four or eight bytes
_VALUE_WIDTHS: tuple[int, ...] = (1, 2, 4, 8)


def _number(string: bytes) -> NumericValue:
    value = 0
    for c in string:
        value = (value << 8) + c
    return NumericValue(value)


# Interface ..................


class FlowIPv4:
    """Marker class for FlowSpec components valid for IPv4."""

    afi: ClassVar[AFI] = AFI.ipv4


class FlowIPv6:
    """Marker class for FlowSpec components valid for IPv6."""

    afi: ClassVar[AFI] = AFI.ipv6


class IPrefix:
    pass


# Prococol


class IPrefix4(IPrefix, IComponent, FlowIPv4):
    """IPv4 FlowSpec prefix using packed-bytes-first pattern.

    Wire format stored in _packed: [mask][truncated_ip...]
    CIDR unpacked on demand via property.
    """

    # Must be defined in subclasses (NAME and operations inherited from IComponent)
    CODE: ClassVar[int] = -1
    ID: ClassVar[int]

    def __init__(self, packed: Buffer) -> None:
        """Create from wire format bytes [mask][truncated_ip...].

        Args:
            packed: NLRI wire format bytes (mask byte + truncated IP)
        """
        self._packed = packed

    @property
    def cidr(self) -> CIDR:
        """CIDR - unpacked from wire bytes on demand."""
        return CIDR.from_ipv4(self._packed)

    @classmethod
    def make_prefix4(cls, raw: bytes, netmask: int) -> Self:
        """Factory to create from full IP bytes and mask (for config parsing).

        Args:
            raw: Full IP address bytes (4 bytes for IPv4)
            netmask: Prefix length

        Returns:
            New instance of cls with packed wire format
        """
        packed = bytes([netmask]) + raw[: CIDR.size(netmask)]
        return cls(packed)

    def pack(self) -> Buffer:
        """Pack to wire format: [ID][mask][truncated_ip...]"""
        return bytes([self.ID]) + self._packed

    def pack_prefix(self) -> Buffer:
        """Alias for pack() - backwards compatibility."""
        return self.pack()

    def short(self) -> str:
        return str(self.cidr)

    def __str__(self) -> str:
        return str(self.cidr)

    @classmethod
    def make(cls, bgp: Buffer) -> tuple[IComponent, Buffer]:
        """Unpack from wire format, storing raw bytes."""
        cidr = CIDR.from_ipv4(bgp)
        packed = bgp[: len(cidr)]  # mask byte + truncated IP bytes
        return cls(packed), bgp[len(cidr) :]


IPV6_ADDRESS_BITS: int = 128
IPV6_ADDRESS_BYTES: int = IPV6_ADDRESS_BITS // 8


def _pattern_size_bytes(length: int, offset: int) -> int:
    """How many octets the pattern of an IPv6 FlowSpec prefix takes.

    RFC 8956 section 3.1: "The encoded pattern contains enough octets for the bits used in
    matching (length minus offset bits)", not the ceil(length / 8) octets a plain prefix
    carries.  The two only agree when the offset is zero.
    """
    return (length - offset + 7) // 8


def _address_from_pattern(pattern: bytes, length: int, offset: int) -> bytes:
    """The sixteen octet address a pattern stands for: the pattern shifted right by offset.

    The padding is dropped rather than carried into the address.  RFC 8956 section 3.1
    says it "MUST be ignored on decoding", and two components describing the same match
    have to render alike and hash to the same RIB index.
    """
    bits = length - offset
    matched = int.from_bytes(pattern, 'big') >> (len(pattern) * 8 - bits) if bits > 0 else 0
    return (matched << (IPV6_ADDRESS_BITS - length)).to_bytes(IPV6_ADDRESS_BYTES, 'big')


def _pattern_from_address(address: bytes, length: int, offset: int) -> bytes:
    """The bits of an address between offset and length, left aligned and zero padded."""
    bits = length - offset
    if bits <= 0:
        return b''
    size = _pattern_size_bytes(length, offset)
    value = int.from_bytes(address.ljust(IPV6_ADDRESS_BYTES, b'\x00'), 'big')
    matched = (value >> (IPV6_ADDRESS_BITS - length)) & ((1 << bits) - 1)
    return (matched << (size * 8 - bits)).to_bytes(size, 'big')


class IPrefix6(IPrefix, IComponent, FlowIPv6):
    """IPv6 FlowSpec prefix using packed-bytes-first pattern.

    Wire format stored in _packed: [mask][truncated_ip...]
    Offset stored separately (IPv6 FlowSpec specific).
    CIDR unpacked on demand via property.
    """

    # Must be defined in subclasses (NAME and operations inherited from IComponent)
    CODE: ClassVar[int] = -1
    ID: ClassVar[int]

    def __init__(self, packed: Buffer, offset: int) -> None:
        """Create from wire format bytes [mask][truncated_ip...] and offset.

        Args:
            packed: NLRI wire format bytes (mask byte + truncated IP)
            offset: IPv6 FlowSpec offset value
        """
        self._packed = packed
        self._offset = offset

    @property
    def cidr(self) -> CIDR:
        """CIDR - unpacked from wire bytes on demand."""
        return CIDR.from_ipv6(self._packed)

    @property
    def offset(self) -> int:
        """IPv6 FlowSpec offset value."""
        return self._offset

    @classmethod
    def make_prefix6(cls, raw: bytes, netmask: int, offset: int) -> Self:
        """Factory to create from full IP bytes, mask and offset (for config parsing).

        Args:
            raw: Full IP address bytes (16 bytes for IPv6)
            netmask: Prefix length
            offset: IPv6 FlowSpec offset value

        Returns:
            New instance of cls with packed wire format
        """
        packed = bytes([netmask]) + raw[: CIDR.size(netmask)]
        return cls(packed, offset)

    def pack(self) -> bytes:
        """Pack to wire format: [ID][length][offset][pattern...]

        The pattern is the length-minus-offset bits of the address, left aligned, and not
        the whole prefix: a /64-104 goes out as the five octets RFC 8956 section 3.8.1
        writes rather than as thirteen no other implementation could read.
        """
        length = self.cidr.mask
        pattern = _pattern_from_address(bytes(self.cidr.pack_ip()), length, self._offset)
        return bytes([self.ID, length, self._offset]) + pattern

    def pack_prefix(self) -> bytes:
        """Alias for pack() - backwards compatibility."""
        return self.pack()

    def short(self) -> str:
        return '{}/{}'.format(self.cidr, self._offset)

    def __str__(self) -> str:
        return '{}/{}'.format(self.cidr, self._offset)

    @classmethod
    def make(cls, bgp: Buffer) -> tuple[IComponent, Buffer]:
        """Unpack from wire format [length][offset][pattern...], storing [length][ip...].

        Sizing the pattern from the length alone, as a plain prefix is sized, read
        ceil(length / 8) octets where RFC 8956 section 3.1 writes
        ceil((length - offset) / 8).  The RFC's own first example then ran off the end of
        its NLRI and came back as NLRI.INVALID: no IPv6 flow specification carrying an
        offset could be read at all, and none exabgp sent could be read by anybody else.
        """
        if len(bgp) < 2:
            raise Notify(3, 10, 'not enough data to extract the length and offset of a flow ipv6 prefix')
        length, offset = bgp[0], bgp[1]
        # RFC 8956 section 3.1: "If length = 0 and offset = 0, this component matches every
        # address; otherwise, length MUST be in the range offset < length < 129 or the
        # component is malformed."  The offset half was never compared to anything, so a
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
        address = _address_from_pattern(pattern, length, offset)
        return cls(bytes([length]) + address[: CIDR.size(length)], offset), bgp[2 + size :]


class IOperation(IComponent):
    """Base class for FlowSpec operation components (ports, protocols, etc.).

    Operation components consist of operator byte(s) and value(s).
    Subclasses define how values are encoded (1, 2, or 4 bytes).

    Attributes:
        operations: Operator bits (AND, comparison operators, EOL)
        value: The numeric value being compared
    """

    operations: int
    value: BaseValue

    # the value sizes this component can hold, in bytes: the operator byte can announce
    # 1, 2, 4 or 8, but each component only encodes some of them (RFC 8955 section 4)
    VALUE_SIZES: ClassVar[tuple[int, ...]] = (1, 2, 4, 8)
    first: bool | None

    def __init__(self, operations: int, value: BaseValue) -> None:
        self.operations = operations
        self.value = value
        self.first = None  # handled by pack/str

    def pack(self) -> Buffer:
        """Pack to wire format: [operator][value...]"""
        length, value = self.encode(self.value)
        op = self.operations | _len_to_bit(length)
        return bytes([op]) + value

    def pack_operation(self) -> Buffer:
        """Alias for pack() - backwards compatibility."""
        return self.pack()

    def encode(self, value: BaseValue) -> tuple[int, Buffer]:
        raise NotImplementedError('this method must be implemented by subclasses')

    # def decode (self, value):
    # 	raise NotImplementedError('this method must be implemented by subclasses')


# class IOperationIPv4 (IOperation):
# 	def encode (self, value):
#       return 4, socket.pton(socket.AF_INET,value)


class IOperationByte(IOperation):
    VALUE_SIZES: ClassVar[tuple[int, ...]] = (1,)

    def encode(self, value: BaseValue) -> tuple[int, bytes]:
        return 1, bytes([value])

    # def decode (self, bgp):
    # 	return bgp[0],bgp[1:]


class IOperationByteShort(IOperation):
    VALUE_SIZES: ClassVar[tuple[int, ...]] = (1, 2)

    def encode(self, value: BaseValue) -> tuple[int, bytes]:
        if value < (1 << 8):
            return 1, bytes([value])
        return 2, pack('!H', value)


class IOperationByteShortLong(IOperation):
    VALUE_SIZES: ClassVar[tuple[int, ...]] = (1, 2, 4)

    def encode(self, value: BaseValue) -> tuple[int, bytes]:
        if value < (1 << 8):
            return 1, bytes([value])
        if value < (1 << 16):
            return 2, pack('!H', value)
        return 4, pack('!L', value)


# String representation for Numeric and Binary Tests


class NumericString:
    """Mixin providing string representation for numeric operations."""

    OPERATION: ClassVar[str] = 'numeric'
    # Set by subclasses - always present when short() is called
    operations: int
    value: BaseValue

    _string: ClassVar[dict[int, str]] = {
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
        op = self.operations & (CommonOperator.EOL ^ 0xFF)
        if op in [NumericOperator.TRUE, NumericOperator.FALSE]:
            return self._string[op]
        value = self.value.short()
        return '{}{}'.format(self._string.get(op, '{:02X}'.format(op)), value)

    def __str__(self) -> str:
        return self.short()


class BinaryString:
    """Mixin providing string representation for binary/bitmask operations."""

    OPERATION: ClassVar[str] = 'binary'
    # Set by subclasses - always present when short() is called
    operations: int
    value: BaseValue

    _string: ClassVar[dict[int, str]] = {
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
        op = self.operations & (CommonOperator.EOL ^ 0xFF)
        return '{}{}'.format(self._string.get(op, '{:02X}'.format(op)), self.value)

    def __str__(self) -> str:
        return self.short()


# Components ..............................


def converter(
    function: Callable[[str], int | 'Protocol' | 'ICMPType' | 'ICMPCode' | 'TCPFlag'], klass: Type[BaseValue]
) -> Callable[[str], BaseValue]:
    def _integer(value: str) -> BaseValue:
        return klass(function(value))

    return _integer


def decoder(function: Callable[[bytes], int], klass: Type[BaseValue] = NumericValue) -> Callable[[bytes], BaseValue]:
    def _inner(value: bytes) -> BaseValue:
        # klass is always a BaseValue subclass, return type is guaranteed
        result: BaseValue = klass(function(value))
        return result

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
        number = Port.from_string(data)
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


FLOW_PREFIX_IDS: tuple[int, ...] = (FlowDestination.ID, FlowSource.ID)


def prefix_family_conflict(rules: dict[int, list[Any]], rule: Any, afi: AFI | None = None) -> str:
    """Why the prefix `rule` cannot join `rules`, or '' when it can.

    RFC 8955 and RFC 8956 give IPv4 and IPv6 flow routes an AFI each, so every source and
    destination prefix of one rule is of the same family. `afi`, when given, is the family the
    route was announced in. Anything which is not a prefix has no family of its own to clash.
    """
    if rule.ID not in FLOW_PREFIX_IDS:
        return ''
    if afi is not None and rule.afi != afi:
        return f'{rule.NAME} {rule} cannot be used in an {afi} flow route, a flow route matches one address family'
    for rule_id in FLOW_PREFIX_IDS:
        for existing in rules.get(rule_id, []):
            if existing.afi != rule.afi:
                return (
                    f'{rule.NAME} {rule} cannot be combined with {existing.NAME} {existing}, '
                    'a flow route matches one address family'
                )
    return ''


class FlowIPProtocol(IOperationByte, NumericString, FlowIPv4):
    """IPv4 IP protocol filter (e.g., TCP=6, UDP=17, ICMP=1)."""

    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'protocol'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(Protocol.from_string, Protocol)
    # _number, not ord: RFC 8955 lets the operator announce any of the four widths, and
    # ord() reads exactly one byte. The width is checked against the RFC, not against
    # what this component encodes, so the decoder has to read whatever arrives.
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, Protocol)


class FlowNextHeader(IOperationByte, NumericString, FlowIPv6):
    """IPv6 next header filter (equivalent to IPv4 protocol)."""

    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'next-header'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(Protocol.from_string, Protocol)
    # _number, not ord: RFC 8955 lets the operator announce any of the four widths, and
    # ord() reads exactly one byte. The width is checked against the RFC, not against
    # what this component encodes, so the decoder has to read whatever arrives.
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, Protocol)


class FlowAnyPort(IOperationByteShort, NumericString, FlowIPv4, FlowIPv6):
    """Filter on source OR destination port (matches either)."""

    ID: ClassVar[int] = 0x04
    NAME: ClassVar[str] = 'port'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(port_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


class FlowDestinationPort(IOperationByteShort, NumericString, FlowIPv4, FlowIPv6):
    ID: ClassVar[int] = 0x05
    NAME: ClassVar[str] = 'destination-port'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(port_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


class FlowSourcePort(IOperationByteShort, NumericString, FlowIPv4, FlowIPv6):
    ID: ClassVar[int] = 0x06
    NAME: ClassVar[str] = 'source-port'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(port_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


class FlowICMPType(IOperationByte, NumericString, FlowIPv4, FlowIPv6):
    ID: ClassVar[int] = 0x07
    NAME: ClassVar[str] = 'icmp-type'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(ICMPType.from_string, ICMPType)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, ICMPType)


class FlowICMPCode(IOperationByte, NumericString, FlowIPv4, FlowIPv6):
    ID: ClassVar[int] = 0x08
    NAME: ClassVar[str] = 'icmp-code'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(ICMPCode.from_string, ICMPCode)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, ICMPCode)


class FlowTCPFlag(IOperationByteShort, BinaryString, FlowIPv4, FlowIPv6):
    """TCP flags bitmask filter (SYN, ACK, FIN, RST, etc.)."""

    ID: ClassVar[int] = 0x09
    NAME: ClassVar[str] = 'tcp-flags'
    FLAG: ClassVar[bool] = True
    converter: ClassVar[Callable[[str], BaseValue]] = converter(TCPFlag.named, TCPFlag)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, TCPFlag)


class FlowPacketLength(IOperationByteShort, NumericString, FlowIPv4, FlowIPv6):
    ID: ClassVar[int] = 0x0A
    NAME: ClassVar[str] = 'packet-length'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(packet_length, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# RFC2474
class FlowDSCP(IOperationByte, NumericString, FlowIPv4):
    ID: ClassVar[int] = 0x0B
    NAME: ClassVar[str] = 'dscp'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(dscp_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# RFC2460
class FlowTrafficClass(IOperationByte, NumericString, FlowIPv6):
    ID: ClassVar[int] = 0x0B
    NAME: ClassVar[str] = 'traffic-class'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(class_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# RFC 8955 section 4.2.2.12 lays the fragment bitmask out as | 0 0 0 0 | LF FF IsF DF |,
# RFC 8956 section 3.6 as | 0 0 0 0 | LF FF IsF 0 |: IPv6 has no Don't Fragment header
# field, so the bit RFC 8955 gives to DF is a reserved zero for AFI 2.  Both documents say
# of their reserved bits "MUST be set to 0 on NLRI encoding and MUST be ignored during
# decoding", so what a family does not define is dropped as the value is read.  Kept, a
# bitmask of 0xF5 was rendered "dont-fragment+first-fragment+unknown fragment type 245",
# and an IPv6 bitmask of 0x01 was published as a match on a field IPv6 does not have.
FRAGMENT_BITS_IPV4: int = Fragment.DONT | Fragment.IS | Fragment.FIRST | Fragment.LAST
FRAGMENT_BITS_IPV6: int = Fragment.IS | Fragment.FIRST | Fragment.LAST


def _fragment(defined_bits: int) -> Callable[[bytes], BaseValue]:
    """Build the fragment value decoder of one family, dropping the bits it reserves."""

    def _masked(value: bytes) -> BaseValue:
        return Fragment(_number(value) & defined_bits)

    return _masked


class FlowFragment(IOperationByteShort, BinaryString, FlowIPv4):
    """IPv4 fragmentation flags filter (DF, IsFragment, First, Last)."""

    ID: ClassVar[int] = 0x0C
    NAME: ClassVar[str] = 'fragment'
    FLAG: ClassVar[bool] = True
    converter: ClassVar[Callable[[str], BaseValue]] = converter(Fragment.named, Fragment)
    # IOperationByteShort, so the operator byte may announce a two byte value: decode with
    # _number rather than ord, which takes a single byte and raised TypeError on the rest
    decoder: ClassVar[Callable[[bytes], BaseValue]] = _fragment(FRAGMENT_BITS_IPV4)


class FlowFragmentIPv6(IOperationByteShort, BinaryString, FlowIPv6):
    """IPv6 fragmentation flags filter (IsFragment, First, Last).

    Type 12 for AFI 2, split from `FlowFragment` the way type 11 is already split between
    `FlowDSCP` and `FlowTrafficClass`: the component is the same on the wire but the set of
    bits the family defines is not, and the decoder is the only place that difference can
    be applied.
    """

    ID: ClassVar[int] = 0x0C
    NAME: ClassVar[str] = 'fragment'
    FLAG: ClassVar[bool] = True
    converter: ClassVar[Callable[[str], BaseValue]] = converter(Fragment.named, Fragment)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = _fragment(FRAGMENT_BITS_IPV6)


# draft-raszuk-idr-flow-spec-v6-01
class FlowFlowLabel(IOperationByteShortLong, NumericString, FlowIPv6):
    ID: ClassVar[int] = 0x0D
    NAME: ClassVar[str] = 'flow-label'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(label_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# ..........................................................

# Flow NLRI encoding constants
FLOW_LENGTH_EXTENDED_MASK: int = 0xF0  # Mask for extended length (upper 4 bits)
FLOW_LENGTH_EXTENDED_VALUE: int = 0xF0  # Value indicating extended length (240)
FLOW_LENGTH_LOWER_MASK: int = 0x0F  # Mask for lower 4 bits in extended length
# RFC 8955 4.1: an extended length is "encoded using 3 hex digits (0xfnnn)", so the low
# nibble of the first octet holds bits 8 to 11 of the length and the second octet holds
# bits 0 to 7.  This was 16, which read 0xf12c as 65580 rather than 300, so every Flow
# NLRI of 256 octets or more was refused with Notify(3, 10) - and that raise happens
# before the try/except in unpack_nlri, so a legal UPDATE from a conforming peer closed
# the session rather than invalidating one NLRI.  pack_nlri has always written the
# correct 12 bit form, so exabgp could not read back what it had just written.
# Lengths 240 to 255 worked, because the nibble is zero there, which is why this lasted.
FLOW_LENGTH_EXTENDED_SHIFT: int = 8  # Shift for extended length calculation
FLOW_LENGTH_COMPACT_MAX: int = 0xF0  # Maximum length for compact encoding (240)
FLOW_LENGTH_EXTENDED_MAX: int = 0x0FFF  # Maximum length for extended encoding (4095)

decode: dict[AFI, dict[int, str]] = {AFI.ipv4: {}, AFI.ipv6: {}}
factory: dict[AFI, dict[int, Type[IComponent]]] = {AFI.ipv4: {}, AFI.ipv6: {}}

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
    if issubclass(kls, FlowIPv4):
        _afis.append(AFI.ipv4)
    if issubclass(kls, FlowIPv6):
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
    """FlowSpec NLRI for traffic filtering rules (RFC 5575) using packed-bytes-first pattern.

    Wire format stored in _packed (excluding length prefix).
    Rules parsed lazily on access via rules property.
    When rules are modified via add(), _packed is marked stale and recomputed on next pack.

    Two modes:
    - Packed mode: created from wire bytes, rules parsed lazily
    - Builder mode: created empty for config, rules added via add()
    """

    __slots__ = ('_rules_cache', '_packed_stale', '_rd_override')

    nexthop: Any

    def __init__(self, packed: Buffer, afi: AFI, safi: SAFI) -> None:
        """Create a Flow NLRI from wire format bytes.

        Args:
            packed: Wire format bytes (excluding length prefix) - RD + rules for flow_vpn, just rules for flow_ip
            afi: Address Family Identifier (ipv4 or ipv6)
            safi: Subsequent Address Family Identifier (flow_ip or flow_vpn)
        """
        NLRI.__init__(self, afi, safi)
        self._packed = packed
        self._rules_cache: dict[int, list[IComponent]] | None = None
        self._packed_stale = False
        self._rd_override: RouteDistinguisher | None = None

    @classmethod
    def make_flow(
        cls,
        afi: AFI = AFI.ipv4,
        safi: SAFI = SAFI.flow_ip,
    ) -> 'Flow':
        """Factory method to create an empty Flow NLRI for building rules.

        This is the preferred way to create a Flow for configuration.
        After creation, use add() to add rules.

        Args:
            afi: Address Family Identifier (ipv4 or ipv6)
            safi: Subsequent Address Family Identifier (flow_ip or flow_vpn)

        Returns:
            New Flow instance ready for adding rules via add()
        """
        # Start with empty packed - will be computed when needed
        packed = RouteDistinguisher.NORD.pack_rd() if safi in (SAFI.flow_vpn,) else b''
        instance = cls(packed, afi, safi)
        instance._rules_cache = {}  # Enable builder mode with empty rules
        return instance

    @classmethod
    def from_settings(cls, settings: 'FlowSettings') -> 'Flow':
        """Create Flow NLRI from validated settings.

        This factory method validates settings and creates an immutable Flow
        instance. Use this for deferred construction where all values are
        collected during parsing, then validated and used to create the NLRI.

        Args:
            settings: FlowSettings with all required fields set

        Returns:
            Immutable Flow NLRI instance

        Raises:
            ValueError: If settings validation fails
        """
        error = settings.validate()
        if error:
            raise ValueError(error)

        # Assertions for type narrowing after validation
        assert settings.afi is not None
        assert settings.safi is not None

        instance = cls.make_flow(
            afi=settings.afi,
            safi=settings.safi,
        )
        # Note: settings.nexthop is now passed to Route, not stored in NLRI

        # Set rules if provided
        if settings.rules:
            instance._rules_cache = settings.rules.copy()
            instance._packed_stale = True  # Mark for recomputation

        # Set rd if provided
        if settings.rd is not None:
            instance._rd_override = settings.rd
            instance._packed_stale = True

        return instance

    @property
    def rules(self) -> dict[int, list[IComponent]]:
        """Rules dict - parsed lazily from _packed on first access."""
        if self._rules_cache is not None:
            return self._rules_cache
        self._rules_cache = self._parse_rules()
        return self._rules_cache

    @property
    def rd(self) -> RouteDistinguisher:
        """Route Distinguisher - from _rd_override if set, else from _packed for flow_vpn."""
        # Check override first (set via setter)
        if self._rd_override is not None:
            return self._rd_override
        # Extract from packed bytes if flow_vpn
        if self.safi in (SAFI.flow_vpn,) and len(self._packed) >= 8:
            return RouteDistinguisher(self._packed[:8])
        return RouteDistinguisher.NORD

    @rd.setter
    def rd(self, value: RouteDistinguisher) -> None:
        """Set RD - triggers packed recomputation."""
        # Parse rules first if needed
        _ = self.rules
        # Update the RD in packed by rebuilding
        self._packed_stale = True
        # Store the new RD value - it will be used when repacking
        self._rd_override = value

    def _parse_rules(self) -> dict[int, list[IComponent]]:
        """Parse rules from _packed bytes."""
        rules: dict[int, list[IComponent]] = {}
        bgp = self._packed

        # flow_vpn carries a mandatory 8-byte Route Distinguisher before any rule bytes.
        # A payload shorter than that has no RD to strip: reject it here, before the rule
        # loop below gets a chance to read what should have been RD bytes as a rule.
        if self.safi in (SAFI.flow_vpn,):
            if len(bgp) < 8:
                raise Notify(3, 10, 'flow-vpn NLRI too short for its route distinguisher')
            bgp = bgp[8:]

        try:
            previous = 0  # no component type is zero, so the first one always passes
            while bgp:
                what, bgp = bgp[0], bgp[1:]

                if what not in decode.get(self.afi, {}):
                    # not `break`: keeping the rules parsed so far turns the peer's filter
                    # into a shorter one, and a flow with no component at all matches
                    # everything, so a controller reading it would rate limit or discard
                    # all traffic. RFC 8955 section 4.3 treats a malformed FlowSpec NLRI
                    # as a withdraw, which is what returning INVALID does here.
                    raise Notify(3, 10, 'flow component %d is not one this family defines' % what)

                self._check_component_order(what, previous)
                previous = what

                decoded = decode[self.afi][what]
                # decode and factory are filled in the same loop, so a component in one and
                # not the other is our own tables disagreeing, not the peer's doing
                assert what in factory.get(self.afi, {}), 'every flow component has a decoder'
                klass = factory[self.afi][what]

                if decoded == 'prefix':
                    adding, bgp = klass.make(bgp)
                    rules.setdefault(adding.ID, []).append(adding)
                else:
                    bgp = self._parse_operations(what, klass, bgp, rules)
        except IndexError:
            # every read above is now bounded, so this is our own bug and not the peer's:
            # tell the caller rather than announcing a route which is not what was sent
            raise Notify(3, 10, 'flow NLRI ran past the end of its own payload') from None

        # RFC 8955 section 4.2 encodes the value as <[component]+>, one component or more.
        # A filter with no component at all is the intersection of nothing, which matches
        # every packet, so a zero length NLRI reached the API as the bare string `flow` and
        # a controller acting on it would have rate limited or discarded all traffic on the
        # box. Section 10 defers to RFC 7606, so this is a treat-as-withdraw like the order
        # and duplicate rules above: the Notify is caught in `unpack_nlri`.
        if not rules:
            raise Notify(3, 10, 'flow NLRI carries no component, which would match every packet')

        return rules

    @staticmethod
    def _check_component_order(what: int, previous: int) -> None:
        """RFC 8955 section 4.2, the two rules the wire order has to obey.

        "Components MUST follow strict type ordering by increasing numerical order", and
        "a given component type MAY (exactly once) be present".  Neither was checked: the
        rules are kept in a dict keyed by type, so a filter which arrived as port then
        destination was re-rendered in the RFC's order and the API reported something the
        peer never sent.  The duplicate is worse than the reorder.  A packet matches the
        intersection of every component, so two type 3 components can never both hold, yet
        the second one's operations were appended to the first one's list with its AND bit
        clear: "protocol tcp AND protocol udp", which matches nothing, was reported as
        "protocol [ =tcp =udp ]", which matches both.

        Section 10 defers to RFC 7606, so this is a treat-as-withdraw: the Notify raised
        here is caught in `unpack_nlri` and turned into `NLRI.INVALID`.

        The one relaxation is a repeated destination or source prefix, which `Flow.add`
        has accepted from the configuration for years because some vendors send it.  What
        exabgp is willing to encode it has to be able to read back.
        """
        if what < previous:
            raise Notify(
                3,
                10,
                'flow component %d follows component %d, which is not the increasing type order required'
                % (what, previous),
            )
        if what == previous and what not in (FlowDestination.ID, FlowSource.ID):
            raise Notify(3, 10, 'flow component %d is present more than once' % what)

    @staticmethod
    def _parse_operations(
        what: int,
        klass: Any,
        bgp: Buffer,
        rules: dict[int, list[IComponent]],
    ) -> Buffer:
        """Read the operator and value pairs of one component, up to its end of list.

        Returns what is left of the payload.
        """
        # RFC 8955 sections 4.2.1.1 and 4.2.1.2 reserve a different part of the operator
        # octet for each flavour, so the mask has to come from the component's own class.
        operator_class = BinaryOperator if issubclass(klass, BinaryString) else NumericOperator
        end: int = 0
        first = True
        while not end:
            if not bgp:
                raise Notify(3, 10, 'flow component %d ends without its end of list operator' % what)
            byte, bgp = bgp[0], bgp[1:]
            end = CommonOperator.eol(byte)
            operator = operator_class.operator(byte)
            if first:
                # RFC 8955 section 4.2.1.1: in the first operator octet of a sequence the
                # AND bit MUST be treated as always unset. Kept, it rendered as `&=tcp`,
                # an AND against a pair which does not exist.
                operator &= CommonOperator.AND ^ 0xFF
                first = False
            length = CommonOperator.length(byte)
            # RFC 8955 section 4.2.1.1: the operator's length field says how many bytes the
            # value takes, and a sender may use any of the four. VALUE_SIZES says what this
            # component *encodes*, which is a different question: refusing a wider encoding
            # dropped a destination port of 80 sent in four bytes, silently, as an INVALID
            # NLRI. The decoders read whatever width is announced, so what has to be checked
            # is that the bytes are actually there.
            if length not in _VALUE_WIDTHS:
                raise Notify(
                    3,
                    10,
                    'flow component %d announces a %d byte value, which is not a width RFC 8955 defines'
                    % (what, length),
                )
            value_bytes, bgp = bytes(bgp[:length]), bgp[length:]
            if len(value_bytes) != length:
                raise Notify(
                    3,
                    10,
                    'flow component %d announces a %d byte value but only %d are left'
                    % (what, length, len(value_bytes)),
                )
            adding_val = klass.decoder(value_bytes)
            # klass is an IOperation subclass taking (operator, value); the decoder is typed
            # as returning object, so the value is narrowed before it is used
            if issubclass(klass, IOperation) and isinstance(adding_val, BaseValue):
                rules.setdefault(what, []).append(klass(operator, adding_val))
        return bgp

    def feedback(self, action: Action) -> str:
        # Nexthop validation handled by Route.feedback()
        return ''

    def __len__(self) -> int:
        # If packed is valid (not stale), use it; otherwise recompute
        if not self._packed_stale and self._packed:
            packed = self._encode_length(self._packed)
        else:
            packed = self._pack_from_rules()
        return len(packed)

    def family_conflict(self, rule: Any) -> str:  # Any is FlowRule
        """Why `rule` cannot be added to this flow route, or '' when it can."""
        return prefix_family_conflict(self.rules, rule)

    def add(self, rule: Any) -> bool:  # Any is FlowRule
        """Add a rule to the Flow NLRI, False when its prefix clashes with the family of another.

        Several sources or destinations are allowed, as some vendors accept them, but all of one
        family: family_conflict() says why a refused rule was refused.
        Adding rules marks _packed as stale, requiring recomputation on next pack.
        """
        ID = rule.ID
        if self.family_conflict(rule):
            return False
        # TODO: verify if this is correct - why reset the afi of the NLRI object after initialisation?
        if ID in FLOW_PREFIX_IDS and rule.afi == AFI.ipv6:
            self._afi = AFI.ipv6
        self.rules.setdefault(ID, []).append(rule)
        self._packed_stale = True  # Mark packed as stale after modification
        return True

    def _encode_length(self, components: Buffer) -> Buffer:
        """Encode length prefix for wire format."""
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

    def _pack_from_rules(self) -> Buffer:
        """Recompute wire format from rules dict.

        TODO: REFACTOR - This method modifies rule operations in-place (EOL bits)
        and does computation in addition to serialization. Flow already uses the
        Settings pattern (FlowSettings) for construction. Should adopt the Collection
        pattern (like AttributeCollection) where a FlowRuleCollection handles rule
        preparation, and _pack_from_rules() becomes pure serialization.
        """
        ordered_rules: list[Buffer] = []
        # the order is a RFC requirement
        for ID in sorted(self.rules.keys()):
            rules = self.rules[ID]
            # for each component get all the operation to do
            # the format use does not prevent two opposing rules meaning that no packet can ever match
            for rule in rules:
                rule.operations &= CommonOperator.EOL ^ 0xFF
            if rules:
                rules[-1].operations |= CommonOperator.EOL
            # and add it to the last rule
            if ID not in (FlowDestination.ID, FlowSource.ID):
                ordered_rules.append(bytes([ID]))
            ordered_rules.append(b''.join(rule.pack() for rule in rules))

        # Use rd_override if set (from rd setter), otherwise use rd property
        rd_to_use = self._rd_override or self.rd
        components = bytes(rd_to_use.pack_rd()) + b''.join(ordered_rules)

        # Update _packed and clear stale flag
        self._packed = components
        self._packed_stale = False

        return self._encode_length(components)

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        # RFC 7911 ADD-PATH is possible for FlowSpec but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(self.afi, self.safi)
        if not self._packed_stale and self._packed:
            return self._encode_length(self._packed)
        return self._pack_from_rules()

    def index(self) -> bytes:
        if not self._packed_stale and self._packed:
            packed = self._encode_length(self._packed)
        else:
            packed = self._pack_from_rules()
        return bytes(Family.index(self)) + packed

    def _rules(self) -> str:
        string: list[str] = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            r_str: list[str] = []
            for idx, rule in enumerate(rules):
                # only add ' ' after the first element
                if idx and not rule.operations & NumericOperator.AND:
                    r_str.append(' ')
                # All concrete IComponent subclasses (IPrefix, IOperation) have short()
                # via direct definition or mixins (NumericString, BinaryString)
                short_fn = getattr(rule, 'short', None)
                r_str.append(short_fn() if short_fn else str(rule))
            line = ''.join(r_str)
            if len(r_str) > 1:
                line = '[ {} ]'.format(line)
            string.append(' {} {}'.format(rules[0].NAME, line))
        return ''.join(string)

    def extensive(self) -> str:
        rd = '' if self.rd is RouteDistinguisher.NORD else str(self.rd)
        return 'flow' + self._rules() + rd

    def __str__(self) -> str:
        return self.extensive()

    def __copy__(self) -> 'Flow':
        new = self.__class__.__new__(self.__class__)
        # NLRI slots (includes Family slots: _afi, _safi)
        self._copy_nlri_slots(new)
        # Flow slots
        new._rules_cache = self._rules_cache
        new._packed_stale = self._packed_stale
        new._rd_override = self._rd_override
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'Flow':
        from copy import deepcopy

        new = self.__class__.__new__(self.__class__)
        memo[id(self)] = new
        # NLRI slots (includes Family slots: _afi, _safi)
        self._deepcopy_nlri_slots(new, memo)
        # Flow slots
        new._rules_cache = deepcopy(self._rules_cache, memo)
        new._packed_stale = self._packed_stale
        new._rd_override = deepcopy(self._rd_override, memo) if self._rd_override else None
        return new

    def _json_members(self, compact: bool = False) -> list[str]:
        """Build the JSON members of this flow, each one complete on its own.

        A flow which parsed no rule contributes no rule member, and one without a route
        distinguisher contributes no rd member, so the members are returned as a list and
        joined by the caller.  Concatenating pre-separated fragments used to leave the
        separator of the first surviving one at the front, and `{, "string": "flow" }` is
        a line no API consumer can parse.
        """
        members: list[str] = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            # rules joined by AND belong to one element, the rest are separate elements
            elements: list[str] = []
            for idx, rule in enumerate(rules):
                if idx and rule.operations & NumericOperator.AND:
                    elements[-1] += str(rule)
                else:
                    elements.append(str(rule))
            # an element is quoted once, by json.dumps, rather than being assembled out of
            # quoted pieces and then repaired with .replace('""', ''): a rule which renders
            # as the empty string had its quotes deleted and left `[ , "is-fragment" ]`,
            # which is the same unreadable line the leading comma used to produce
            members.append('"{}": [ {} ]'.format(rules[0].NAME, ', '.join(json.dumps(e) for e in elements)))
        if self.rd is not RouteDistinguisher.NORD:
            members.append(self.rd.json())
        return members

    def json(self, announced: bool = True, compact: bool = False) -> str:
        """Serialize Flow NLRI to JSON (v6 format - no nexthop)."""
        members = self._json_members(compact)
        members.append('"string": {}'.format(json.dumps(self.extensive())))
        return '{' + ', '.join(members) + ' }'

    def v4_json(self, compact: bool = False, nexthop: IP | None = None) -> str:
        """Serialize Flow NLRI to JSON for API v4 backward compatibility (includes nexthop)."""
        members = self._json_members(compact)
        nh = nexthop if nexthop is not None else IP.NoNextHop
        if nh is not IP.NoNextHop:
            members.append('"next-hop": "{}"'.format(nh))
        members.append('"string": {}'.format(json.dumps(self.extensive())))
        return '{' + ', '.join(members) + ' }'

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: bool, negotiated: Negotiated
    ) -> tuple[NLRI, Buffer]:
        """Unpack Flow NLRI from wire format, storing raw bytes."""
        # RFC 7911 3: with ADD-PATH negotiated the peer puts a four byte Path
        # Identifier in front of every NLRI of this family, and it has to come off
        # before the NLRI is read.
        path_info, data = NLRI.consume_path_information(data, addpath)
        if len(data) < 1:
            raise Notify(3, 10, 'Flow NLRI too short: need at least 1 byte for length')
        length, data = data[0], data[1:]

        if length & FLOW_LENGTH_EXTENDED_MASK == FLOW_LENGTH_EXTENDED_VALUE:  # bigger than 240
            if len(data) < 1:
                raise Notify(3, 10, 'Flow NLRI extended length truncated: need 1 more byte')
            extra, data = data[0], data[1:]
            length = ((length & FLOW_LENGTH_LOWER_MASK) << FLOW_LENGTH_EXTENDED_SHIFT) + extra

        if length > len(data):
            raise Notify(3, 10, f'Flow NLRI truncated: need {length} bytes, got {len(data)}')

        over = data[length:]
        packed = bytes(data[:length])

        # Create Flow with packed bytes - rules will be parsed lazily
        nlri = cls(packed, afi, safi)
        nlri.addpath = path_info

        # Validate by parsing (this populates _rules_cache)
        try:
            # the wire order and the "exactly once" rule are checked as the components are
            # read, in _check_component_order: a dict keyed by type cannot show either.
            rules = nlri.rules  # Trigger lazy parsing

            # Check AFI compatibility for source/destination
            src_rules = rules.get(FlowSource.ID, [])
            dst_rules = rules.get(FlowDestination.ID, [])
            if src_rules and dst_rules:
                # src_rules[0] and dst_rules[0] are IPrefix subclasses with afi
                src_afi = getattr(src_rules[0], 'afi', None)
                dst_afi = getattr(dst_rules[0], 'afi', None)
                if src_afi is not None and dst_afi is not None and src_afi != dst_afi:
                    raise Notify(
                        3,
                        10,
                        'components are incompatible (mix ipv4/ipv6)',
                    )

            return nlri, over
        except Notify:
            return NLRI.INVALID, over
        except ValueError:
            return NLRI.INVALID, over
        except IndexError:
            return NLRI.INVALID, over
