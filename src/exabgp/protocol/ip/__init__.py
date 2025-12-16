"""ip/__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import builtins
import socket
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, Protocol

from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip.netmask import NetMask
from exabgp.util.types import Buffer

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


class IPFactory(Protocol):
    """Protocol for IP subclass constructors that accept packed data.

    Used for type hints where we need a class callable with packed bytes.
    IPv4 and IPv6 implement this via their __init__(packed) signature.
    """

    def __call__(self, packed: Buffer) -> 'IP': ...


class IPBase:
    SELF: ClassVar[bool]
    RESOLVED: ClassVar[bool] = True
    afi: AFI

    def resolve(self, ip: 'IP | None' = None) -> None:
        """Resolve address. For regular IPs, this is a no-op.

        IPSelf subclass overrides to accept a concrete IP and resolves in-place.
        The parameter is optional for base compatibility.
        """
        pass

    @property
    def resolved(self) -> bool:
        """True if resolve() has been called with a concrete IP."""
        return self.RESOLVED

    def __init__(self, afi: AFI) -> None:
        self.afi = afi


# =========================================================================== IP
#


class IP(IPBase):
    SELF = False

    afi: AFI  # here for the API, changed in init (subclasses override as ClassVar)
    # BITS and BYTES are defined as ClassVar in subclasses (IPv4/IPv6)
    # Not annotated here to allow proper ClassVar override

    _known: ClassVar[dict[AFI, IPFactory]] = dict()

    _UNICAST: ClassVar[SAFI] = SAFI.unicast
    _MULTICAST: ClassVar[SAFI] = SAFI.multicast

    _multicast_range: ClassVar[set[int]] = set(range(224, 240))  # 239

    _packed: Buffer

    # deprecate the string API in favor of top()

    def __init__(self) -> None:
        raise RuntimeError('You should use IP.from_string() to use IP')

    def init(self, packed: Buffer) -> IP:
        self._packed = packed
        self.afi = IP.toafi(IP.ntop(packed))
        return self

    def __iter__(self) -> Iterator[str]:
        for letter in IP.ntop(self._packed):
            yield letter

    @staticmethod
    def pton(ip: str) -> bytes:
        return socket.inet_pton(IP.toaf(ip), ip)

    @staticmethod
    def ntop(data: Buffer) -> str:
        return socket.inet_ntop(socket.AF_INET if len(data) == IPv4.BYTES else socket.AF_INET6, data)

    def top(self, negotiated: Negotiated | None = None, afi: AFI = AFI.undefined) -> str:
        return IP.ntop(self._packed)

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
            # Check for IPv4-mapped IPv6 (::ffff:x.x.x.x)
            ip_lower = ip.lower()
            if '::ffff:' in ip_lower and '.' in ip:
                # Extract IPv4 part after ::ffff:
                ipv4_part = ip.split(':')[-1]
                if int(ipv4_part.split('.')[0]) in IP._multicast_range:
                    return SAFI.multicast
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

    def __len__(self) -> int:
        return IP.length(self.afi)

    @staticmethod
    def length(afi: AFI) -> int:
        return 4 if afi == AFI.ipv4 else 16

    def index(self) -> Buffer:
        return self._packed

    def pack_ip(self) -> Buffer:
        return self._packed

    def __str__(self) -> str:
        return 'no-nexthop' if not self._packed else IP.ntop(self._packed)

    def __repr__(self) -> str:
        return 'no-nexthop' if not self._packed else IP.ntop(self._packed)

    def decode(self, encoding: str = 'utf-8', errors: str = 'strict') -> str:
        assert encoding in ('utf-8', 'ascii')
        return 'no-nexthop' if not self._packed else IP.ntop(self._packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IP):
            return False
        return self._packed == other._packed

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: IP) -> bool:
        return bytes(self._packed) < bytes(other._packed)

    def __le__(self, other: IP) -> bool:
        return bytes(self._packed) <= bytes(other._packed)

    def __gt__(self, other: IP) -> bool:
        return bytes(self._packed) > bytes(other._packed)

    def __ge__(self, other: IP) -> bool:
        return bytes(self._packed) >= bytes(other._packed)

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self._packed))

    @classmethod
    def klass(cls, ip: str) -> IPFactory | None:
        # the orders matters as ::FFFF:<ipv4> is an IPv6 address
        afi: AFI | None
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
    def from_string(cls, string: str, klass: IPFactory | None = None) -> 'IP':
        data = IP.pton(string)
        if klass:
            return klass(data)
        factory = cls.klass(string)
        if factory is None:
            raise ValueError(f'Unknown IP address format: {string}')
        return factory(data)

    @classmethod
    def register(cls) -> None:
        # Only concrete IP subclasses (IPv4, IPv6) should register
        if cls is IP:
            raise RuntimeError('IP.register() should not be called directly')
        # cls is IPv4 or IPv6, both implement __init__(packed) -> satisfies IPFactory
        from typing import cast

        cls._known[cls.afi] = cast(IPFactory, cls)

    # Singleton for no next-hop (initialized after class definition)
    NoNextHop: ClassVar[IP]

    @classmethod
    def _create_no_nexthop(cls) -> IP:
        """Create the no-nexthop singleton. Called once at module load."""
        # Bypass __init__ which raises RuntimeError
        instance = object.__new__(cls)
        instance._packed = b''
        instance.afi = AFI.undefined
        return instance

    def __copy__(self) -> 'IP':
        """Preserve singleton identity for NoNextHop."""
        if self is IP.NoNextHop:
            return self
        # For subclasses that may not have all attributes (e.g., NextHopSelf),
        # use default copy behavior
        new = IP.__new__(type(self))
        new.__dict__.update(self.__dict__)
        return new

    def __deepcopy__(self, memo: dict[Any, Any]) -> 'IP':
        """Preserve singleton identity for NoNextHop."""
        if self is IP.NoNextHop:
            return self
        # For subclasses that may not have all attributes (e.g., NextHopSelf),
        # use default copy behavior
        new = IP.__new__(type(self))
        new.__dict__.update(self.__dict__)
        memo[id(self)] = new
        return new

    @classmethod
    def create_ip(cls, data: Buffer) -> IP:
        # Always use concrete IPv4/IPv6 classes based on data length
        # This avoids calling cls(data) when cls might be IP itself
        factory: IPFactory = IPv4 if len(data) == 4 else IPv6
        return factory(data)


# ======================================================================== Range
#


class IPRange(IP):
    mask: NetMask

    def __init__(self, packed: Buffer, mask: int) -> None:
        IP.init(self, packed)
        self.mask = NetMask.make_netmask(mask, self.afi)

    @classmethod
    def from_string(cls, string: str, klass: IPFactory | None = None) -> 'IP':
        raise NotImplementedError(f'{cls.__name__}.from_string() not implemented')

    def __repr__(self) -> str:
        if (self.ipv4() and self.mask == IPv4.HOST_MASK) or (self.ipv6() and self.mask == IPv6.HOST_MASK):
            return super(IPRange, self).__repr__()
        return f'{self.top()}/{int(self.mask)}'


# ==================================================================== NoNextHop
# Initialize the class-level singleton
IP.NoNextHop = IP._create_no_nexthop()


# ======================================================================= IPSelf
#


class IPSelf(IP):
    """Special IP that starts unresolved and is resolved in-place via resolve().

    Inherits from IP so return type can simply be `IP` for functions that
    may return either a concrete IP or a "self" sentinel.
    """

    SELF: ClassVar[bool] = True
    RESOLVED: ClassVar[bool] = False  # Override: unresolved by default

    def __init__(self, afi: AFI) -> None:
        # Bypass IP.__init__ which raises RuntimeError
        # Set up IPSelf-specific state
        self._packed = b''  # Empty = unresolved
        self.afi = afi

    @property
    def resolved(self) -> bool:
        """True if resolve() has been called with a concrete IP."""
        return self._packed != b''

    def resolve(self, ip: IP | None = None) -> None:
        """Resolve sentinel to concrete IP. Mutates in-place.

        Args:
            ip: The concrete IP to resolve to. Required for IPSelf.
        """
        if ip is None:
            raise ValueError('IPSelf.resolve() requires an ip argument')
        if self.resolved:
            raise ValueError('IPSelf already resolved')
        self._packed = ip.pack_ip()

    def pack_ip(self) -> Buffer:
        """Get packed bytes (IP interface compatibility)."""
        if not self.resolved:
            raise ValueError('IPSelf.pack_ip() called before resolve()')
        return self._packed

    def __repr__(self) -> str:
        if not self.resolved:
            return 'self'
        return IP.ntop(self._packed)

    def __str__(self) -> str:
        return self.__repr__()

    def index(self) -> bytes:
        if not self.resolved:
            return b'self-' + self.afi.name().encode()
        return bytes(self._packed)


# ========================================================================= IPv4
#


class IPv4(IP):
    # Class attribute shadows base class instance variable (same pattern as Family)
    afi = AFI.ipv4

    # lowercase to match the Address API (used in configuration code)
    bits: ClassVar[int] = 32
    bytes: ClassVar[int] = 4  # shadows builtin, but required for compatibility

    # IPv4-specific constants
    BITS: ClassVar[int] = 32  # IPv4 address bit length
    BYTES: ClassVar[int] = 4  # IPv4 address byte length
    DOT_COUNT: ClassVar[int] = 3  # Number of dots in IPv4 address format (e.g., 192.168.1.1)
    HOST_MASK: ClassVar[int] = 32  # IPv4 host prefix length (/32)

    def __init__(self, packed: Buffer) -> None:
        self.init(packed)

    def __len__(self) -> int:
        return 4

    def unicast(self) -> bool:
        return not self.multicast()

    def multicast(self) -> bool:
        return self._packed[0] in range(224, 240)  # 239 is last

    def ipv4(self) -> bool:
        return True

    def ipv6(self) -> bool:
        return False

    @staticmethod
    def pton(ip: str) -> builtins.bytes:
        return socket.inet_pton(socket.AF_INET, ip)

    @staticmethod
    def ntop(data: Buffer) -> str:
        return socket.inet_ntop(socket.AF_INET, data)

    # klass is a trick for subclasses of IP/IPv4 such as NextHop / OriginatorID
    @classmethod
    def unpack_ipv4(cls, data: Buffer) -> IPv4:
        return cls(data)


IPv4.register()


# ========================================================================= IPv6
#


class IPv6(IP):
    # Class attribute shadows base class instance variable (same pattern as Family)
    afi = AFI.ipv6

    # lowercase to match the Address API (used in configuration code)
    bits: ClassVar[int] = 128
    bytes: ClassVar[int] = 16  # shadows builtin, but required for compatibility

    # IPv6-specific constants
    BITS: ClassVar[int] = 128  # IPv6 address bit length
    BYTES: ClassVar[int] = 16  # IPv6 address byte length
    COLON_MIN: ClassVar[int] = 2  # Minimum number of colons in IPv6 address format
    HOST_MASK: ClassVar[int] = 128  # IPv6 host prefix length (/128)

    def __init__(self, packed: Buffer) -> None:
        self.init(packed)

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
    def ntop(data: Buffer) -> str:
        return socket.inet_ntop(socket.AF_INET6, data)

    @classmethod
    def unpack_ipv6(cls, data: Buffer) -> IPv6:
        return cls(data)


IPv6.register()
