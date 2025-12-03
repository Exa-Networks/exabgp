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

    def __init__(self, packed: bytes) -> None:
        ExtendedCommunity.__init__(self, packed)

    @classmethod
    def make_l2info(cls, encaps: int, control: int, mtu: int, reserved: int) -> L2Info:
        """Create L2Info from semantic values.

        reserved is called preference in draft-ietf-l2vpn-vpls-multihoming-07
        """
        packed = pack('!BBBBHH', cls.COMMUNITY_TYPE, cls.COMMUNITY_SUBTYPE, encaps, control, mtu, reserved)
        return cls(packed)

    @property
    def encaps(self) -> int:
        return self._packed[2]

    @property
    def control(self) -> int:
        return self._packed[3]

    @property
    def mtu(self) -> int:
        return unpack('!H', self._packed[4:6])[0]

    @property
    def reserved(self) -> int:
        return unpack('!H', self._packed[6:8])[0]

    def __repr__(self) -> str:
        return 'l2info:{}:{}:{}:{}'.format(self.encaps, self.control, self.mtu, self.reserved)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated | None = None) -> L2Info:
        return cls(data[:8])
