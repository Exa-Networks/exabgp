"""tunnel_encap/tlv.py

Base classes for Tunnel Encapsulation Attribute TLVs (RFC 9012).

Outer TLV (Tunnel Type TLV):
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     Tunnel Type (2 octets)    |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     Length (2 octets)         |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     Value (variable)          |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

Sub-TLV (within tunnel type Value):
 For types 0-127:
 +-+-+-+-+-+-+-+-+
 | Type (1 octet)|
 +-+-+-+-+-+-+-+-+
 | Length (1 octet)              |  <- length of Value only
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |    Value (variable)           |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

 For types 128-255:
 +-+-+-+-+-+-+-+-+
 | Type (1 octet)|
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |    Length (2 octets)          |  <- length of Value only
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |    Value (variable)           |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
"""

from __future__ import annotations

from struct import pack, unpack
from typing import Any, ClassVar, Type

from exabgp.bgp.message.notification import Notify
from exabgp.util import hexstring

# Type alias for buffer (bytes or bytearray)
Buffer = bytes | bytearray


class TunnelTypeTLV:
    """Base class for a Tunnel Type TLV within the Tunnel Encap attribute.

    Subclasses register themselves by tunnel type number via register().
    Each subclass handles the Value portion of one tunnel type.
    """

    TUNNEL_TYPE: ClassVar[int] = -1

    registered_tunnel_types: ClassVar[dict[int, Type[TunnelTypeTLV]]] = {}

    def __init__(self, packed: Buffer) -> None:
        self._packed: bytes = bytes(packed)

    @classmethod
    def register(cls, tunnel_type: int | None = None) -> Any:
        def decorator(klass: Type[TunnelTypeTLV]) -> Type[TunnelTypeTLV]:
            ttype = tunnel_type if tunnel_type is not None else klass.TUNNEL_TYPE
            if ttype in cls.registered_tunnel_types:
                raise RuntimeError(f'Tunnel type {ttype} already registered')
            cls.registered_tunnel_types[ttype] = klass
            klass.TUNNEL_TYPE = ttype
            return klass

        return decorator

    @classmethod
    def unpack_tunnel(cls, tunnel_type: int, data: Buffer) -> TunnelTypeTLV:
        if tunnel_type in cls.registered_tunnel_types:
            return cls.registered_tunnel_types[tunnel_type].unpack(data)
        return GenericTunnelTLV(tunnel_type, data)

    def pack(self) -> bytes:
        """Pack this tunnel TLV including outer type(2) + length(2) header."""
        value = self.pack_value()
        return pack('!HH', self.TUNNEL_TYPE, len(value)) + value

    def pack_value(self) -> bytes:
        return self._packed

    def json(self) -> str:
        return f'"tunnel-type-{self.TUNNEL_TYPE}": "{hexstring(self._packed)}"'

    def __str__(self) -> str:
        return f'tunnel-type:{self.TUNNEL_TYPE}'

    @classmethod
    def unpack(cls, data: Buffer) -> TunnelTypeTLV:
        raise NotImplementedError


class GenericTunnelTLV(TunnelTypeTLV):
    """Unknown tunnel type — store raw bytes."""

    def __init__(self, tunnel_type: int, data: Buffer) -> None:
        self._tunnel_type = tunnel_type
        self._packed = bytes(data)

    def pack(self) -> bytes:
        return pack('!HH', self._tunnel_type, len(self._packed)) + self._packed

    def __str__(self) -> str:
        return f'tunnel-type:{self._tunnel_type}'

    @classmethod
    def unpack(cls, data: Buffer) -> GenericTunnelTLV:
        raise NotImplementedError('GenericTunnelTLV is constructed directly, not via unpack()')

    def json(self) -> str:
        return f'"tunnel-type-{self._tunnel_type}": "{hexstring(self._packed)}"'


class SubTLV:
    """Base class for Sub-TLVs within a Tunnel Type value.

    Wire format per RFC 9012:
    - Types 0-127: type(1) + length(1) + value(variable)
    - Types 128-255: type(1) + length(2) + value(variable)
    """

    SUBTYPE: ClassVar[int] = -1

    registered_subtypes: ClassVar[dict[int, Type[SubTLV]]] = {}

    def __init__(self, packed: Buffer) -> None:
        self._packed: bytes = bytes(packed)

    @classmethod
    def register(cls, subtype: int | None = None) -> Any:
        def decorator(klass: Type[SubTLV]) -> Type[SubTLV]:
            stype = subtype if subtype is not None else klass.SUBTYPE
            if stype in cls.registered_subtypes:
                raise RuntimeError(f'SubTLV subtype {stype} already registered')
            cls.registered_subtypes[stype] = klass
            klass.SUBTYPE = stype
            return klass

        return decorator

    @classmethod
    def unpack_subtlvs(cls, data: Buffer) -> list[SubTLV]:
        result: list[SubTLV] = []
        while data:
            if len(data) < 1:
                raise Notify(3, 1, f'Sub-TLV header truncated: need at least 1 byte, got {len(data)}')
            subtype = data[0]

            # Determine length field size based on type value per RFC 9012
            if subtype < 128:
                if len(data) < 2:
                    raise Notify(3, 1, f'Sub-TLV header truncated: need 2 bytes for type {subtype}, got {len(data)}')
                length = data[1]
                header_size = 2
            else:
                if len(data) < 3:
                    raise Notify(3, 1, f'Sub-TLV header truncated: need 3 bytes for type {subtype}, got {len(data)}')
                length: int = unpack('!H', data[1:3])[0]
                header_size = 3

            if len(data) < header_size + length:
                raise Notify(3, 1, f'Sub-TLV truncated: need {header_size + length}, got {len(data)}')
            value = data[header_size : header_size + length]
            if subtype in cls.registered_subtypes:
                subtlv = cls.registered_subtypes[subtype].unpack(value)
            else:
                subtlv = GenericSubTLV(subtype, value)
            result.append(subtlv)
            data = data[header_size + length :]
        return result

    def pack(self) -> bytes:
        """Pack sub-TLV with type + length + value header per RFC 9012."""
        value = self.pack_value()
        if self.SUBTYPE < 128:
            return pack('!BB', self.SUBTYPE, len(value)) + value
        else:
            return pack('!BH', self.SUBTYPE, len(value)) + value

    def pack_value(self) -> bytes:
        return self._packed

    def json(self) -> str:
        raise NotImplementedError

    @classmethod
    def unpack(cls, data: Buffer) -> SubTLV:
        raise NotImplementedError


class GenericSubTLV(SubTLV):
    """Unknown sub-TLV type — store raw bytes."""

    def __init__(self, subtype: int, data: Buffer) -> None:
        self._subtype = subtype
        self._packed = bytes(data)

    def pack(self) -> bytes:
        """Pack with proper length encoding per RFC 9012."""
        if self._subtype < 128:
            return pack('!BB', self._subtype, len(self._packed)) + self._packed
        else:
            return pack('!BH', self._subtype, len(self._packed)) + self._packed

    @classmethod
    def unpack(cls, data: Buffer) -> GenericSubTLV:
        raise NotImplementedError('GenericSubTLV is constructed directly')

    def json(self) -> str:
        return f'"unknown-subtlv-{self._subtype}": "{hexstring(self._packed)}"'
