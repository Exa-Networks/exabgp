"""flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections.abc import Buffer
from struct import pack
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    ClassVar,
    Protocol as TypingProtocol,
    Type,
)

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.protocol.ip import IP
from exabgp.protocol.ip.port import Port
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import Family
from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.cidr import CIDR

from exabgp.protocol import Protocol
from exabgp.protocol.resource import BaseValue, NumericValue
from exabgp.protocol.ip.icmp import ICMPType
from exabgp.protocol.ip.icmp import ICMPCode
from exabgp.protocol.ip.fragment import Fragment
from exabgp.protocol.ip.tcp.flag import TCPFlag

from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher


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
    # all have ID
    # should have an interface for serialisation and put it here
    FLAG: ClassVar[bool] = False

    def pack(self) -> bytes:
        """Pack the component to wire format. Must be overridden by subclasses."""
        raise NotImplementedError(f'{self.__class__.__name__} must implement pack()')


class CommonOperator:
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


def _number(string: bytes) -> NumericValue:
    value = 0
    for c in string:
        value = (value << 8) + c
    return NumericValue(value)


# Interface ..................


class IPv4:
    afi: ClassVar[AFI] = AFI.ipv4


class IPv6:
    afi: ClassVar[AFI] = AFI.ipv6


class IPrefix:
    pass


# Prococol


class IPrefix4(IPrefix, IComponent, IPv4):
    """IPv4 FlowSpec prefix using packed-bytes-first pattern.

    Wire format stored in _packed: [mask][truncated_ip...]
    CIDR unpacked on demand via property.
    """

    # Must be defined in subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = ''
    ID: ClassVar[int]

    # not used, just present for simplying the nlri generation
    operations: int = 0x0

    def __init__(self, packed: bytes) -> None:
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
    def make_prefix4(cls, raw: bytes, netmask: int) -> 'IPrefix4':
        """Factory to create from full IP bytes and mask (for config parsing).

        Args:
            raw: Full IP address bytes (4 bytes for IPv4)
            netmask: Prefix length

        Returns:
            New IPrefix4 instance with packed wire format
        """
        packed = bytes([netmask]) + raw[: CIDR.size(netmask)]
        return cls(packed)

    def pack(self) -> bytes:
        """Pack to wire format: [ID][mask][truncated_ip...]"""
        return bytes([self.ID]) + self._packed

    def pack_prefix(self) -> bytes:
        """Alias for pack() - backwards compatibility."""
        return self.pack()

    def short(self) -> str:
        return str(self.cidr)

    def __str__(self) -> str:
        return str(self.cidr)

    @classmethod
    def make(cls, bgp: bytes) -> tuple[IPrefix4, bytes]:
        """Unpack from wire format, storing raw bytes."""
        cidr = CIDR.from_ipv4(bgp)
        packed = bgp[: len(cidr)]  # mask byte + truncated IP bytes
        return cls(packed), bgp[len(cidr) :]


class IPrefix6(IPrefix, IComponent, IPv6):
    """IPv6 FlowSpec prefix using packed-bytes-first pattern.

    Wire format stored in _packed: [mask][truncated_ip...]
    Offset stored separately (IPv6 FlowSpec specific).
    CIDR unpacked on demand via property.
    """

    # Must be defined in subclasses
    CODE: ClassVar[int] = -1
    NAME: ClassVar[str] = ''
    ID: ClassVar[int]

    # not used, just present for simplying the nlri generation
    operations: int = 0x0

    def __init__(self, packed: bytes, offset: int) -> None:
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
    def make_prefix6(cls, raw: bytes, netmask: int, offset: int) -> 'IPrefix6':
        """Factory to create from full IP bytes, mask and offset (for config parsing).

        Args:
            raw: Full IP address bytes (16 bytes for IPv6)
            netmask: Prefix length
            offset: IPv6 FlowSpec offset value

        Returns:
            New IPrefix6 instance with packed wire format
        """
        packed = bytes([netmask]) + raw[: CIDR.size(netmask)]
        return cls(packed, offset)

    def pack(self) -> bytes:
        """Pack to wire format: [ID][mask][offset][ip...]"""
        return bytes([self.ID, self.cidr.mask, self._offset]) + self.cidr.pack_ip()

    def pack_prefix(self) -> bytes:
        """Alias for pack() - backwards compatibility."""
        return self.pack()

    def short(self) -> str:
        return '{}/{}'.format(self.cidr, self._offset)

    def __str__(self) -> str:
        return '{}/{}'.format(self.cidr, self._offset)

    @classmethod
    def make(cls, bgp: bytes) -> tuple[IPrefix6, bytes]:
        """Unpack from wire format, storing raw bytes and offset."""
        offset = bgp[1]
        # IPv6 FlowSpec has offset byte between mask and prefix
        # Wire format: [mask][offset][ip...], we store [mask][ip...] in _packed
        cidr = CIDR.from_ipv6(bgp[0:1] + bgp[2:])
        packed = bgp[0:1] + bgp[2 : 2 + CIDR.size(cidr.mask)]
        return cls(packed, offset), bgp[CIDR.size(cidr.mask) + 2 :]


class IOperation(IComponent):
    # need to implement encode which encode the value of the operator
    operations: int
    value: BaseValue
    first: bool | None

    def __init__(self, operations: int, value: BaseValue) -> None:
        self.operations = operations
        self.value = value
        self.first = None  # handled by pack/str

    def pack(self) -> bytes:
        """Pack to wire format: [operator][value...]"""
        length, value = self.encode(self.value)
        op = self.operations | _len_to_bit(length)
        return bytes([op]) + value

    def pack_operation(self) -> bytes:
        """Alias for pack() - backwards compatibility."""
        return self.pack()

    def encode(self, value: BaseValue) -> tuple[int, bytes]:
        raise NotImplementedError('this method must be implemented by subclasses')

    # def decode (self, value):
    # 	raise NotImplementedError('this method must be implemented by subclasses')


# class IOperationIPv4 (IOperation):
# 	def encode (self, value):
# 		return 4, socket.pton(socket.AF_INET,value)


class IOperationByte(IOperation):
    def encode(self, value: BaseValue) -> tuple[int, bytes]:
        return 1, bytes([value])

    # def decode (self, bgp):
    # 	return bgp[0],bgp[1:]


class IOperationByteShort(IOperation):
    def encode(self, value: BaseValue) -> tuple[int, bytes]:
        if value < (1 << 8):
            return 1, bytes([value])
        return 2, pack('!H', value)


class IOperationByteShortLong(IOperation):
    def encode(self, value: BaseValue) -> tuple[int, bytes]:
        if value < (1 << 8):
            return 1, bytes([value])
        if value < (1 << 16):
            return 2, pack('!H', value)
        return 4, pack('!L', value)


# String representation for Numeric and Binary Tests


class NumericString:
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


def decoder(function: Callable[[bytes], int], klass: Type = NumericValue) -> Callable[[bytes], BaseValue]:
    def _inner(value: bytes) -> BaseValue:
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


class FlowIPProtocol(IOperationByte, NumericString, IPv4):
    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'protocol'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(Protocol.from_string, Protocol)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(ord, Protocol)


class FlowNextHeader(IOperationByte, NumericString, IPv6):
    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'next-header'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(Protocol.from_string, Protocol)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(ord, Protocol)


class FlowAnyPort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x04
    NAME: ClassVar[str] = 'port'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(port_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


class FlowDestinationPort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x05
    NAME: ClassVar[str] = 'destination-port'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(port_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


class FlowSourcePort(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x06
    NAME: ClassVar[str] = 'source-port'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(port_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


class FlowICMPType(IOperationByte, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x07
    NAME: ClassVar[str] = 'icmp-type'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(ICMPType.from_string, ICMPType)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, ICMPType)


class FlowICMPCode(IOperationByte, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x08
    NAME: ClassVar[str] = 'icmp-code'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(ICMPCode.from_string, ICMPCode)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, ICMPCode)


class FlowTCPFlag(IOperationByteShort, BinaryString, IPv4, IPv6):
    ID: ClassVar[int] = 0x09
    NAME: ClassVar[str] = 'tcp-flags'
    FLAG: ClassVar[bool] = True
    converter: ClassVar[Callable[[str], BaseValue]] = converter(TCPFlag.named, TCPFlag)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(_number, TCPFlag)


class FlowPacketLength(IOperationByteShort, NumericString, IPv4, IPv6):
    ID: ClassVar[int] = 0x0A
    NAME: ClassVar[str] = 'packet-length'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(packet_length, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# RFC2474
class FlowDSCP(IOperationByte, NumericString, IPv4):
    ID: ClassVar[int] = 0x0B
    NAME: ClassVar[str] = 'dscp'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(dscp_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# RFC2460
class FlowTrafficClass(IOperationByte, NumericString, IPv6):
    ID: ClassVar[int] = 0x0B
    NAME: ClassVar[str] = 'traffic-class'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(class_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# BinaryOperator
class FlowFragment(IOperationByteShort, BinaryString, IPv4, IPv6):
    ID: ClassVar[int] = 0x0C
    NAME: ClassVar[str] = 'fragment'
    FLAG: ClassVar[bool] = True
    converter: ClassVar[Callable[[str], BaseValue]] = converter(Fragment.named, Fragment)
    decoder: ClassVar[Callable[[bytes], BaseValue]] = decoder(ord, Fragment)


# draft-raszuk-idr-flow-spec-v6-01
class FlowFlowLabel(IOperationByteShortLong, NumericString, IPv6):
    ID: ClassVar[int] = 0x0D
    NAME: ClassVar[str] = 'flow-label'
    converter: ClassVar[Callable[[str], BaseValue]] = converter(label_value, NumericValue)
    decoder: ClassVar[Callable[[bytes], NumericValue]] = _number


# ..........................................................

# Flow NLRI encoding constants
FLOW_LENGTH_EXTENDED_MASK: int = 0xF0  # Mask for extended length (upper 4 bits)
FLOW_LENGTH_EXTENDED_VALUE: int = 0xF0  # Value indicating extended length (240)
FLOW_LENGTH_LOWER_MASK: int = 0x0F  # Mask for lower 4 bits in extended length
FLOW_LENGTH_EXTENDED_SHIFT: int = 16  # Shift for extended length calculation
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

    def __init__(self, packed: bytes, afi: AFI, safi: SAFI, action: Action = Action.UNSET) -> None:
        """Create a Flow NLRI from wire format bytes.

        Args:
            packed: Wire format bytes (excluding length prefix) - RD + rules for flow_vpn, just rules for flow_ip
            afi: Address Family Identifier (ipv4 or ipv6)
            safi: Subsequent Address Family Identifier (flow_ip or flow_vpn)
            action: Route action (ANNOUNCE/WITHDRAW)
        """
        NLRI.__init__(self, afi, safi, action)
        self._packed = packed
        self._rules_cache: dict[int, list[FlowRule]] | None = None
        self._packed_stale = False
        self._rd_override: RouteDistinguisher | None = None
        self.nexthop = IP.NoNextHop

    @classmethod
    def make_flow(
        cls,
        afi: AFI = AFI.ipv4,
        safi: SAFI = SAFI.flow_ip,
        action: Action = Action.ANNOUNCE,
    ) -> 'Flow':
        """Factory method to create an empty Flow NLRI for building rules.

        This is the preferred way to create a Flow for configuration.
        After creation, use add() to add rules.

        Args:
            afi: Address Family Identifier (ipv4 or ipv6)
            safi: Subsequent Address Family Identifier (flow_ip or flow_vpn)
            action: Route action (ANNOUNCE/WITHDRAW)

        Returns:
            New Flow instance ready for adding rules via add()
        """
        # Start with empty packed - will be computed when needed
        packed = RouteDistinguisher.NORD.pack_rd() if safi in (SAFI.flow_vpn,) else b''
        instance = cls(packed, afi, safi, action)
        instance._rules_cache = {}  # Enable builder mode with empty rules
        return instance

    @property
    def rules(self) -> dict[int, list[FlowRule]]:
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

    def _parse_rules(self) -> dict[int, list[FlowRule]]:
        """Parse rules from _packed bytes."""
        rules: dict[int, list[FlowRule]] = {}
        bgp = self._packed

        # Skip RD for flow_vpn
        if self.safi in (SAFI.flow_vpn,) and len(bgp) >= 8:
            bgp = bgp[8:]

        try:
            while bgp:
                what, bgp = bgp[0], bgp[1:]

                if what not in decode.get(self.afi, {}):
                    break  # Unknown component, stop parsing

                decoded = decode[self.afi][what]
                klass = factory[self.afi][what]

                if decoded == 'prefix':
                    adding, bgp = klass.make(bgp)  # type: ignore[attr-defined]
                    rules.setdefault(adding.ID, []).append(adding)
                else:
                    end: int = 0
                    while not end:
                        byte, bgp = bgp[0], bgp[1:]
                        end = CommonOperator.eol(byte)
                        operator = CommonOperator.operator(byte)
                        length = CommonOperator.length(byte)
                        value, bgp = bgp[:length], bgp[length:]
                        adding_val = klass.decoder(value)  # type: ignore[attr-defined]
                        rules.setdefault(what, []).append(klass(operator, adding_val))  # type: ignore[arg-type,call-arg]
        except (IndexError, KeyError):
            pass  # Incomplete data, return what we have

        return rules

    def feedback(self, action: Action) -> str:  # type: ignore[override]
        if self.nexthop is IP.NoNextHop and action == Action.ANNOUNCE:
            return 'flow nlri next-hop missing'
        return ''

    def __len__(self) -> int:
        return len(self._pack_nlri_simple())

    def add(self, rule: FlowRule) -> bool:
        """Add a rule to the Flow NLRI.

        Adding rules marks _packed as stale, requiring recomputation on next pack.
        """
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
            if rule.NAME.endswith('ipv6'):
                self.afi = AFI.ipv6
        self.rules.setdefault(ID, []).append(rule)
        self._packed_stale = True  # Mark packed as stale after modification
        return True

    def _pack_nlri_simple(self) -> bytes:
        """Pack NLRI without negotiated-dependent data (no addpath).

        Returns stored _packed bytes with length prefix if not stale,
        otherwise recomputes from rules.
        """
        # If packed is valid (not stale), return with length prefix
        if not self._packed_stale and self._packed:
            return self._encode_length(self._packed)

        # Recompute from rules
        return self._pack_from_rules()

    def _encode_length(self, components: bytes) -> bytes:
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

    def _pack_from_rules(self) -> bytes:
        """Recompute wire format from rules dict."""
        ordered_rules: list[bytes] = []
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
        components = rd_to_use.pack_rd() + b''.join(ordered_rules)

        # Update _packed and clear stale flag
        self._packed = components
        self._packed_stale = False

        return self._encode_length(components)

    def pack_nlri(self, negotiated: Negotiated) -> bytes:
        # RFC 7911 ADD-PATH is possible for FlowSpec but not yet implemented
        # TODO: implement addpath support when negotiated.addpath.send(self.afi, self.safi)
        return self._pack_nlri_simple()

    def index(self) -> bytes:
        return Family.index(self) + self._pack_nlri_simple()

    def _rules(self) -> str:
        string: list[str] = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            r_str: list[str] = []
            for idx, rule in enumerate(rules):
                # only add ' ' after the first element
                if idx and not rule.operations & NumericOperator.AND:
                    r_str.append(' ')
                r_str.append(rule.short())
            line = ''.join(r_str)
            if len(r_str) > 1:
                line = '[ {} ]'.format(line)
            string.append(' {} {}'.format(rules[0].NAME, line))
        return ''.join(string)

    def extensive(self) -> str:
        nexthop = ' next-hop {}'.format(self.nexthop) if self.nexthop is not IP.NoNextHop else ''
        rd = '' if self.rd is RouteDistinguisher.NORD else str(self.rd)
        return 'flow' + self._rules() + rd + nexthop

    def __str__(self) -> str:
        return self.extensive()

    def __copy__(self) -> 'Flow':
        new = self.__class__.__new__(self.__class__)
        # Family slots (afi/safi)
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
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
        # Family slots (afi/safi) - immutable enums
        new.afi = self.afi
        new.safi = self.safi
        # NLRI slots
        self._deepcopy_nlri_slots(new, memo)
        # Flow slots
        new._rules_cache = deepcopy(self._rules_cache, memo)
        new._packed_stale = self._packed_stale
        new._rd_override = deepcopy(self._rd_override, memo) if self._rd_override else None
        return new

    def json(self, compact: bool = False) -> str:
        string: list[str] = []
        for index in sorted(self.rules):
            rules = self.rules[index]
            s: list[str] = []
            for idx, rule in enumerate(rules):
                # only add ' ' after the first element
                if idx and not rule.operations & NumericOperator.AND:
                    s.append(', ')
                s.append('"{}"'.format(rule))
            string.append(' "{}": [ {} ]'.format(rules[0].NAME, ''.join(str(_) for _ in s).replace('""', '')))
        nexthop = ', "next-hop": "{}"'.format(self.nexthop) if self.nexthop is not IP.NoNextHop else ''
        rd = '' if self.rd is RouteDistinguisher.NORD else ', {}'.format(self.rd.json())
        compatibility = ', "string": "{}"'.format(self.extensive())
        return '{' + ','.join(string) + rd + nexthop + compatibility + ' }'

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, bgp: Buffer, action: Action, addpath: Any, negotiated: Negotiated
    ) -> tuple[Flow | NLRI, Buffer]:
        """Unpack Flow NLRI from wire format, storing raw bytes."""
        data = memoryview(bgp) if not isinstance(bgp, memoryview) else bgp
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
        nlri = cls(packed, afi, safi, action)

        # Validate by parsing (this populates _rules_cache)
        try:
            seen: list[int] = []
            rules = nlri.rules  # Trigger lazy parsing

            # Validate rule order
            for rule_id in sorted(rules.keys()):
                for rule in rules[rule_id]:
                    if rule_id in (FlowDestination.ID, FlowSource.ID):
                        seen.append(rule.ID)
                    else:
                        seen.append(rule_id)
                        break  # Only add ID once per rule type for non-prefix

            # Check AFI compatibility for source/destination
            src_rules = rules.get(FlowSource.ID, [])
            dst_rules = rules.get(FlowDestination.ID, [])
            if src_rules and dst_rules:
                if src_rules[0].afi != dst_rules[0].afi:
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
