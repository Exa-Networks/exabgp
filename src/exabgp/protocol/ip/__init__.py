"""ip/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import builtins
import socket
from typing import Dict, Optional, Set, Type, ClassVar, Iterator, Any, TYPE_CHECKING

from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip.netmask import NetMask

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# XXX: The IP,Range and CIDR class API are totally broken, fix it.
# XXX: many of the NLRI classes constructor also need correct @classmethods


# =========================================================================== IP
#


class IPSelf:
    SELF: ClassVar[bool] = True
    afi: AFI

    def __init__(self, afi: AFI) -> None:
        self.afi = afi

    def __repr__(self) -> str:
        return 'self'

    def top(self, negotiated: Negotiated, afi: AFI = AFI.undefined) -> str:
        return negotiated.nexthopself(afi).top()  # type: ignore[no-any-return]

    def ton(self, negotiated: Negotiated, afi: AFI = AFI.undefined) -> bytes:
        return negotiated.nexthopself(afi).ton()  # type: ignore[no-any-return]

    def pack(self, negotiated: Negotiated) -> bytes:
        return negotiated.nexthopself(self.afi).ton()  # type: ignore[no-any-return]

    def index(self) -> str:
        return 'self-' + AFI.names[self.afi]


class IP:
    SELF: ClassVar[bool] = False

    afi: AFI  # here for the API, changed in init (subclasses override as ClassVar)
    # BITS and BYTES are defined as ClassVar in subclasses (IPv4/IPv6)
    # Not annotated here to allow proper ClassVar override

    _known: ClassVar[Dict[AFI, Type[IP]]] = dict()

    _UNICAST: ClassVar[SAFI] = SAFI.unicast
    _MULTICAST: ClassVar[SAFI] = SAFI.multicast

    _multicast_range: ClassVar[Set[int]] = set(range(224, 240))  # 239

    _string: str
    _packed: bytes

    # deprecate the string API in favor of top()

    def __init__(self) -> None:
        raise RuntimeError('You should use IP.create() to use IP')

    def init(self, string: str, packed: Optional[bytes] = None) -> IP:
        # XXX: the str should not be needed
        self._string = string
        self._packed = IP.pton(string) if packed is None else packed
        self.afi = IP.toafi(string)
        return self

    def __iter__(self) -> Iterator[str]:
        for letter in self._string:
            yield letter

    @staticmethod
    def pton(ip: str) -> bytes:
        return socket.inet_pton(IP.toaf(ip), ip)

    @staticmethod
    def ntop(data: bytes) -> str:
        return socket.inet_ntop(socket.AF_INET if len(data) == IPv4.BYTES else socket.AF_INET6, data)

    def top(self, negotiated: Optional[Negotiated] = None, afi: AFI = AFI.undefined) -> str:
        return self._string

    @staticmethod
    def toaf(ip: str) -> int:
        # the orders matters as ::FFFF:<ipv4> is an IPv6 address
        if ':' in ip:
            return socket.AF_INET6
        if '.' in ip:
            return socket.AF_INET
        raise ValueError(f'unrecognised ip address {ip}')

    @staticmethod
    def toafi(ip: str) -> AFI:
        # the orders matters as ::FFFF:<ipv4> is an IPv6 address
        if ':' in ip:
            return AFI.ipv6
        if '.' in ip:
            return AFI.ipv4
        raise ValueError(f'unrecognised ip address {ip}')

    @staticmethod
    def tosafi(ip: str) -> SAFI:
        if ':' in ip:
            # XXX: FIXME: I assume that ::FFFF:<ip> must be treated unicast
            # if int(ip.split(':')[-1].split('.')[0]) in IP._multicast_range:
            return SAFI.unicast
        if '.' in ip:
            if int(ip.split('.')[0]) in IP._multicast_range:
                return SAFI.multicast
            return SAFI.unicast
        raise ValueError(f'unrecognised ip address {ip}')

    def ipv4(self) -> bool:
        return len(self._packed) == IPv4.BYTES

    def ipv6(self) -> bool:
        return len(self._packed) != IPv4.BYTES

    def address(self) -> int:
        value = 0
        for char in self._packed:
            value <<= 8
            value += char
        return value

    @staticmethod
    def length(afi: AFI) -> int:
        return 4 if afi == AFI.ipv4 else 16

    def index(self) -> bytes:
        return self._packed

    def pack_ip(self) -> bytes:
        return self._packed

    def ton(self, negotiated: Optional[Negotiated] = None, afi: AFI = AFI.undefined) -> bytes:
        return self._packed

    def __repr__(self) -> str:
        return self._string

    def decode(self, encoding: str = 'utf-8', errors: str = 'strict') -> str:
        assert encoding in ('utf-8', 'ascii')
        return self._string

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IP):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: IP) -> bool:
        return self._packed < other._packed

    def __le__(self, other: IP) -> bool:
        return self._packed <= other._packed

    def __gt__(self, other: IP) -> bool:
        return self._packed > other._packed

    def __ge__(self, other: IP) -> bool:
        return self._packed >= other._packed

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self._packed))

    @classmethod
    def klass(cls, ip: str) -> Optional[Type[IP]]:
        # the orders matters as ::FFFF:<ipv4> is an IPv6 address
        afi: Optional[AFI]
        if ':' in ip:
            afi = IPv6.afi
        elif '.' in ip:
            afi = IPv4.afi
        else:
            raise ValueError(f'can not decode this ip address : {ip}')
        if afi in cls._known:
            return cls._known[afi]
        return None

    @classmethod
    def create(cls, string: str, packed: Optional[bytes] = None, klass: Optional[Type[IP]] = None) -> IP:
        if klass:
            return klass(string, packed)  # type: ignore[call-arg]
        return cls.klass(string)(string, packed)  # type: ignore[call-arg,misc]

    @classmethod
    def register(cls) -> None:
        cls._known[cls.afi] = cls

    @classmethod
    def unpack_ip(cls, data: bytes, klass: Optional[Type[IP]] = None) -> IP:
        return cls.create(IP.ntop(data), data, klass)


# ======================================================================== Range
#


class IPRange(IP):
    mask: NetMask

    def __init__(self, ip: str, mask: int) -> None:
        IP.init(self, ip)
        self.mask = NetMask.create(mask, IP.toafi(ip))

    @classmethod
    def create(klass: Type[IPRange], ip: str, mask: int) -> IPRange:  # type: ignore[override]
        return klass(ip, mask)

    def __repr__(self) -> str:
        if (self.ipv4() and self.mask == IPv4.HOST_MASK) or (self.ipv6() and self.mask == IPv6.HOST_MASK):
            return super(IPRange, self).__repr__()
        return f'{self.top()}/{int(self.mask)}'


# ==================================================================== NoNextHop
#


class _NoNextHop:
    SELF: ClassVar[bool] = False

    packed: ClassVar[str] = ''

    afi: ClassVar[AFI] = AFI.undefined
    safi: ClassVar[SAFI] = SAFI.undefined

    def pack(self, data: Any, negotiated: Optional[Negotiated] = None) -> str:
        return ''

    def index(self) -> str:
        return ''

    def ton(self, negotiated: Optional[Negotiated] = None, afi: AFI = AFI.undefined) -> str:
        return ''

    def __str__(self) -> str:
        return 'no-nexthop'

    def __deepcopy__(self, _: Any) -> _NoNextHop:
        return self

    def __copy__(self, _: Any) -> _NoNextHop:
        return self


NoNextHop: _NoNextHop = _NoNextHop()


# ========================================================================= IPv4
#


class IPv4(IP):
    # Override afi as ClassVar (base class has it as instance variable)
    afi: ClassVar[AFI] = AFI.ipv4  # type: ignore[misc]

    # lowercase to match the Address API (used in configuration code)
    bits: ClassVar[int] = 32
    bytes: ClassVar[int] = 4  # shadows builtin, but required for compatibility

    # IPv4-specific constants
    BITS: ClassVar[int] = 32  # IPv4 address bit length
    BYTES: ClassVar[int] = 4  # IPv4 address byte length
    DOT_COUNT: ClassVar[int] = 3  # Number of dots in IPv4 address format (e.g., 192.168.1.1)
    HOST_MASK: ClassVar[int] = 32  # IPv4 host prefix length (/32)

    def __init__(self, string: str, packed: Optional[builtins.bytes] = None) -> None:
        self.init(string, packed if packed else IP.pton(string))

    def __len__(self) -> int:
        return 4

    def unicast(self) -> bool:
        return not self.multicast()

    def multicast(self) -> bool:
        return self._packed[0] in set(range(224, 240))  # 239 is last

    def ipv4(self) -> bool:
        return True

    def ipv6(self) -> bool:
        return False

    @staticmethod
    def pton(ip: str) -> builtins.bytes:
        return socket.inet_pton(socket.AF_INET, ip)

    @staticmethod
    def ntop(data: builtins.bytes) -> str:
        return socket.inet_ntop(socket.AF_INET, data)

    # klass is a trick for subclasses of IP/IPv4 such as NextHop / OriginatorID
    @classmethod
    def unpack_ipv4(cls, data: builtins.bytes, klass: Optional[Type[IPv4]] = None) -> IPv4:
        ip = socket.inet_ntop(socket.AF_INET, data)
        if klass:
            return klass(ip, data)
        return cls(ip, data)


IPv4.register()


# ========================================================================= IPv6
#


class IPv6(IP):
    # Override afi as ClassVar (base class has it as instance variable)
    afi: ClassVar[AFI] = AFI.ipv6  # type: ignore[misc]

    # lowercase to match the Address API (used in configuration code)
    bits: ClassVar[int] = 128
    bytes: ClassVar[int] = 16  # shadows builtin, but required for compatibility

    # IPv6-specific constants
    BITS: ClassVar[int] = 128  # IPv6 address bit length
    BYTES: ClassVar[int] = 16  # IPv6 address byte length
    COLON_MIN: ClassVar[int] = 2  # Minimum number of colons in IPv6 address format
    HOST_MASK: ClassVar[int] = 128  # IPv6 host prefix length (/128)

    def __init__(self, string: str, packed: Optional[builtins.bytes] = None) -> None:
        self.init(string, packed if packed else socket.inet_pton(socket.AF_INET6, string))

    def __len__(self) -> int:
        return 16

    def ipv4(self) -> bool:
        return False

    def ipv6(self) -> bool:
        return True

    def unicast(self) -> bool:
        return True

    def multicast(self) -> bool:
        return False

    @staticmethod
    def pton(ip: str) -> builtins.bytes:
        return socket.inet_pton(socket.AF_INET6, ip)

    @staticmethod
    def ntop(data: builtins.bytes) -> str:
        return socket.inet_ntop(socket.AF_INET6, data)

    @classmethod
    def unpack_ipv6(cls, data: builtins.bytes, klass: Optional[Type[IPv6]] = None) -> IPv6:
        ip6 = socket.inet_ntop(socket.AF_INET6, data)
        if klass:
            return klass(ip6)
        return cls(ip6)


IPv6.register()
