"""encapsulation.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

# ================================================================ Encapsulation
# RFC 5512


@ExtendedCommunity.register
class Encapsulation(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x03
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0C

    # https://www.iana.org/assignments/bgp-parameters/bgp-parameters.xhtml#tunnel-types
    class Type:
        DEFAULT: ClassVar[int] = 0x00
        L2TPv3: ClassVar[int] = 0x01
        GRE: ClassVar[int] = 0x02
        IPIP: ClassVar[int] = 0x07
        VXLAN: ClassVar[int] = 0x08
        NVGRE: ClassVar[int] = 0x09
        MPLS: ClassVar[int] = 0x0A
        VXLAN_GPE: ClassVar[int] = 0x0C
        MPLS_UDP: ClassVar[int] = 0x0D

    _string: ClassVar[dict[int, str]] = {
        Type.DEFAULT: 'Default',
        Type.L2TPv3: 'L2TPv3',
        Type.GRE: 'GRE',
        Type.IPIP: 'IP-in-IP',
        Type.VXLAN: 'VXLAN',
        Type.NVGRE: 'NVGRE',
        Type.MPLS: 'MPLS',
        Type.VXLAN_GPE: 'VXLAN-GPE',
        Type.MPLS_UDP: 'MPLS-in-UDP',
    }

    def __init__(self, tunnel_type: int, community: bytes | None = None) -> None:
        self.tunnel_type: int = tunnel_type
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sLH', self._subtype(), 0, self.tunnel_type),
        )

    def __repr__(self) -> str:
        return 'encap:{}'.format(Encapsulation._string.get(self.tunnel_type, 'encap:UNKNOWN-%d' % self.tunnel_type))

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> Encapsulation:
        (tunnel,) = unpack('!H', data[6:8])
        return Encapsulation(tunnel, data[:8])

        # type_  = data[0] & 0x0F
        # stype = data[1]

        # assert(type_==Encapsulation.COMMUNITY_TYPE)
        # assert(stype==Encapsulation.COMMUNITY_SUBTYPE)
        # assert(len(data)==6)
