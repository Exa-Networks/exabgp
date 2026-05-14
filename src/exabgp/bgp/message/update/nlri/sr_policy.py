"""nlri/sr_policy.py

SR Policy NLRI (RFC 9830).

NLRI format for AFI 1 (IPv4):
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                     Distinguisher (4 octets)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                      Policy Color (4 octets)                   |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                  Endpoint Address (4 or 16 octets)             |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

For IPv6 (AFI 2), endpoint is 16 bytes. Total: 24 bytes.
For IPv4 (AFI 1), endpoint is 4 bytes. Total: 12 bytes.

The SR Policy NLRI is carried in MP_REACH_NLRI / MP_UNREACH_NLRI (RFC 4760)
for SAFI 73. There is no NLRI length prefix in the MP_REACH wire format
because the NLRI size is fixed per AFI.

Created by Manoharan Sundaramoorthy 2026-05-01.
"""

from __future__ import annotations

import socket
from struct import pack, unpack
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI, Family

# Type alias for buffer (bytes or bytearray)
Buffer = bytes | bytearray

# IPv4 NLRI body: distinguisher(4) + color(4) + endpoint(4) = 12
_IPV4_NLRI_SIZE = 12
# IPv6 NLRI body: distinguisher(4) + color(4) + endpoint(16) = 24
_IPV6_NLRI_SIZE = 24


@NLRI.register(AFI.ipv4, SAFI.sr_policy)
@NLRI.register(AFI.ipv6, SAFI.sr_policy)
class SRPolicyNLRI(NLRI):
    """SR Policy NLRI (RFC 9830) using packed-bytes-first pattern.

    _packed stores: distinguisher(4) + color(4) + endpoint(4 or 16)
    AFI determines endpoint size (4=IPv4, 16=IPv6).
    """

    __slots__ = ()

    def __init__(self, afi: AFI, packed: Buffer, action: Action = Action.UNSET) -> None:
        NLRI.__init__(self, afi, SAFI.sr_policy, action)
        self._packed = bytes(packed)

    @property
    def distinguisher(self) -> int:
        value: int = unpack('!I', self._packed[0:4])[0]
        return value

    @property
    def color(self) -> int:
        value: int = unpack('!I', self._packed[4:8])[0]
        return value

    @property
    def endpoint(self) -> str:
        if self.afi == AFI.ipv6:
            return socket.inet_ntop(socket.AF_INET6, self._packed[8:24])
        return socket.inet_ntop(socket.AF_INET, self._packed[8:12])

    @classmethod
    def create(
        cls, afi: AFI, distinguisher: int, color: int, endpoint: str, action: Action = Action.ANNOUNCE
    ) -> 'SRPolicyNLRI':
        """Create from semantic values."""
        packed = pack('!II', distinguisher, color)
        if afi == AFI.ipv6:
            packed += socket.inet_pton(socket.AF_INET6, endpoint)
        else:
            packed += socket.inet_pton(socket.AF_INET, endpoint)
        return cls(afi, packed, action)

    def feedback(self, action: Action) -> str:
        return ''

    def pack_nlri(self, negotiated: Negotiated) -> Buffer:
        """Pack NLRI with 1-byte length prefix per RFC 9830 Section 3.

        Wire format: Length(1) + Distinguisher(4) + Color(4) + Endpoint(4 or 16)
        Length = bit count of Distinguisher + Color + Endpoint (96 for IPv4, 192 for IPv6)
        """
        return bytes([len(self._packed) * 8]) + self._packed

    def index(self) -> bytes:
        return bytes(Family.index(self)) + self._packed

    def __hash__(self) -> int:
        return hash('{}:{}:{}'.format(self.afi, self.safi, self._packed.hex()))

    def __len__(self) -> int:
        """Return length including the 1-byte length prefix."""
        return 1 + len(self._packed)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SRPolicyNLRI):
            return False
        return NLRI.__eq__(self, other)

    def __str__(self) -> str:
        return 'sr-policy distinguisher {} color {} endpoint {}'.format(
            self.distinguisher,
            self.color,
            self.endpoint,
        )

    def __repr__(self) -> str:
        return str(self)

    def json(self, announced: bool = True, compact: bool | None = None) -> str:
        return '{{"distinguisher": {}, "color": {}, "endpoint": "{}"}}'.format(
            self.distinguisher,
            self.color,
            self.endpoint,
        )

    @classmethod
    def unpack_nlri(
        cls, afi: AFI, safi: SAFI, data: Buffer, action: Action, addpath: Any, negotiated: Any = None
    ) -> tuple[NLRI, Buffer]:
        """Unpack SR-Policy NLRI with 1-byte length prefix per RFC 9830 Section 3."""
        if len(data) < 1:
            raise Notify(3, 10, 'SR Policy NLRI missing length byte')

        # Read length byte (in bits per RFC 9830: 96 for IPv4, 192 for IPv6)
        nlri_len_bits = data[0]
        expected_bits = (_IPV6_NLRI_SIZE if afi == AFI.ipv6 else _IPV4_NLRI_SIZE) * 8

        # Validate length
        if nlri_len_bits != expected_bits:
            raise Notify(
                3,
                10,
                f'SR Policy NLRI invalid length: got {nlri_len_bits} bits, expected {expected_bits} for AFI {afi}',
            )

        nlri_bytes = nlri_len_bits // 8

        # Check we have enough data
        if len(data) < 1 + nlri_bytes:
            raise Notify(3, 10, f'SR Policy NLRI too short: need {1 + nlri_bytes} bytes, got {len(data)}')

        # Skip length byte, extract NLRI data
        nlri = cls(afi, data[1 : 1 + nlri_bytes], action)
        nlri.addpath = addpath
        return nlri, data[1 + nlri_bytes :]
