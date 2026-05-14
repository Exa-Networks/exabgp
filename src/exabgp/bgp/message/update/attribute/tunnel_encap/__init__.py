"""tunnel_encap/__init__.py

Tunnel Encapsulation Attribute (type 23, RFC 9012).

Attribute flags: OPTIONAL | TRANSITIVE

Wire format (attribute value):
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     Tunnel Type (2 octets)    |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     Length (2 octets)         |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 |     Value (variable)          |
 +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
 ...  (repeated for each tunnel type)

Registered tunnel types:
  15  SR Policy (RFC 9012 / RFC 9256)

Created by Manoharan Sundaramoorthy 2026-05-01.
"""

from __future__ import annotations

from struct import unpack
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

import exabgp.bgp.message.update.attribute.tunnel_encap.sr_policy  # noqa: F401,E402 (triggers tunnel type 15 registration)
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.tunnel_encap.tlv import TunnelTypeTLV

# Type alias for buffer (bytes or bytearray)
Buffer = bytes | bytearray

_TUNNEL_TLV_HEADER = 4  # type(2) + length(2)


@Attribute.register()
class TunnelEncap(Attribute):
    """Tunnel Encapsulation Attribute (RFC 9012, code 23)."""

    ID: int = Attribute.CODE.TUNNEL_ENCAP
    FLAG: int = Attribute.Flag.OPTIONAL | Attribute.Flag.TRANSITIVE
    CACHING: ClassVar[bool] = True

    def __init__(self, tunnel_tlvs: list[Any]) -> None:
        self.tunnel_tlvs = tunnel_tlvs

    # ExaBGP's Attributes.pack() calls attribute.pack(negotiated), so we
    # provide a thin wrapper that reuses the pack_attribute implementation.
    def pack(self, negotiated: 'Negotiated') -> Buffer:  # pragma: no cover - simple delegation
        return self.pack_attribute(negotiated)

    def pack_attribute(self, negotiated: Negotiated) -> Buffer:
        value = b''.join(tlv.pack() for tlv in self.tunnel_tlvs)
        return self._attribute(value)

    def json(self, compact: bool | None = None) -> str:
        parts = ', '.join(tlv.json() for tlv in self.tunnel_tlvs)
        return '{' + parts + '}'

    def __str__(self) -> str:
        return 'tunnel-encap [' + ', '.join(str(t) for t in self.tunnel_tlvs) + ']'

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TunnelEncap):
            return False
        return str(self) == str(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> TunnelEncap:
        tunnel_tlvs: list[Any] = []
        while data:
            if len(data) < _TUNNEL_TLV_HEADER:
                raise Notify(3, 1, f'Tunnel Encap TLV header truncated: need {_TUNNEL_TLV_HEADER}, got {len(data)}')
            tunnel_type: int = unpack('!H', data[0:2])[0]
            length: int = unpack('!H', data[2:4])[0]
            if len(data) < _TUNNEL_TLV_HEADER + length:
                raise Notify(3, 1, f'Tunnel Encap TLV truncated: need {_TUNNEL_TLV_HEADER + length}')
            value = data[_TUNNEL_TLV_HEADER : _TUNNEL_TLV_HEADER + length]
            tlv = TunnelTypeTLV.unpack_tunnel(tunnel_type, value)
            tunnel_tlvs.append(tlv)
            data = data[_TUNNEL_TLV_HEADER + length :]
        return cls(tunnel_tlvs=tunnel_tlvs)
