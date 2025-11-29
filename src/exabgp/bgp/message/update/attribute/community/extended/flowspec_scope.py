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
    from exabgp.bgp.message.open.negotiated import Negotiated


# ============================================================== InterfaceSet
# draft-ietf-idr-flowspsec-interfaceset


@ExtendedCommunity.register
class InterfaceSet(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x07
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x02

    names: ClassVar[dict[int, str]] = {
        1: 'input',
        2: 'output',
        3: 'input-output',
    }

    def __init__(self, trans: bool, asn: ASN, target: int, direction: int, community: bytes | None = None) -> None:
        self.asn: ASN = asn
        self.target: int = target
        self.direction: int = direction
        self._transitive: bool = trans
        new_target = (direction << 14) + target
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sLH', self._subtype(self._transitive), asn, new_target),
        )

    def __repr__(self) -> str:
        str_direction = self.names.get(self.direction, str(self.direction))
        return 'interface-set:{}:{}:{}'.format(str_direction, str(self.asn), str(self.target))

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> InterfaceSet:
        asn, target = unpack('!LH', data[2:8])
        direction = target >> 14
        target = target & 0x1FFF
        return cls(False, ASN(asn), target, direction, data[:8])
