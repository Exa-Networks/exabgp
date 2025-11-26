"""l2info.py

Created by Thomas Mangin on 2014-06-20.
Copyright (c) 2014-2017 Orange. All rights reserved.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar, TYPE_CHECKING

from struct import pack
from struct import unpack

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

# ============================================================ Layer2Information
# RFC 4761


@ExtendedCommunity.register
class L2Info(ExtendedCommunity):
    COMMUNITY_TYPE: ClassVar[int] = 0x80
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x0A

    def __init__(self, encaps: int, control: int, mtu: int, reserved: int, community: bytes | None = None) -> None:
        self.encaps: int = encaps
        self.control: int = control
        self.mtu: int = mtu
        self.reserved: int = reserved
        # reserved is called preference in draft-ietf-l2vpn-vpls-multihoming-07
        ExtendedCommunity.__init__(
            self,
            community if community is not None else pack('!2sBBHH', self._subtype(), encaps, control, mtu, reserved),
        )

    def __repr__(self) -> str:
        return 'l2info:{}:{}:{}:{}'.format(self.encaps, self.control, self.mtu, self.reserved)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> L2Info:
        encaps, control, mtu, reserved = unpack('!BBHH', data[2:8])
        return L2Info(encaps, control, mtu, reserved, data[:8])
