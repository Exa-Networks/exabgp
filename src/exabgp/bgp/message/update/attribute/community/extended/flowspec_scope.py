"""flowspec_scope.py

Created by Stephane Litkowski on 2017-02-24.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from struct import pack
from struct import unpack

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.util.types import Buffer


# ============================================================== InterfaceSet
# draft-ietf-idr-flowspsec-interfaceset


@ExtendedCommunity.register
class InterfaceSet(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x07
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x02

    # Group ID is 14-bit field (direction uses top 2 bits of 16-bit field)
    GROUP_ID_BITS: ClassVar[int] = 14
    GROUP_ID_MAX: ClassVar[int] = (1 << 14) - 1  # 16383

    names: ClassVar[dict[int, str]] = {
        1: 'input',
        2: 'output',
        3: 'input-output',
    }

    @classmethod
    def validate_group_id(cls, value: int) -> bool:
        """Validate group-id is within 14-bit range.

        Args:
            value: Integer group-id value

        Returns:
            True if valid, False otherwise
        """
        return 0 <= value <= cls.GROUP_ID_MAX

    def __init__(self, packed: Buffer) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_interface_set(cls, asn: ASN, target: int, direction: int, transitive: bool = True) -> InterfaceSet:
        """Create InterfaceSet from semantic values."""
        type_byte = cls.COMMUNITY_TYPE if transitive else cls.COMMUNITY_TYPE | cls.NON_TRANSITIVE
        new_target = (direction << 14) + target
        packed = pack('!BBLH', type_byte, cls.COMMUNITY_SUBTYPE, asn, new_target)
        return cls(packed)

    @property
    def asn(self) -> ASN:
        return ASN(unpack('!L', self._packed[2:6])[0])

    @property
    def target(self) -> int:
        raw_target: int = unpack('!H', self._packed[6:8])[0]
        return raw_target & 0x3FFF

    @property
    def direction(self) -> int:
        raw_target: int = unpack('!H', self._packed[6:8])[0]
        return raw_target >> 14

    def __repr__(self) -> str:
        str_direction = self.names.get(self.direction, str(self.direction))
        return 'interface-set:{}:{}:{}'.format(str_direction, str(self.asn), str(self.target))

    def json(self) -> str:
        h = 0x00
        for byte in self._packed:
            h <<= 8
            h += byte
        trans = 'true' if self.transitive() else 'false'
        return '{{ "value": {}, "string": "{}", "transitive": {} }}'.format(h, repr(self), trans)

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated | None = None) -> InterfaceSet:
        return cls(data[:8])
