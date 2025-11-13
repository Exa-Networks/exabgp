"""nexthop.py

Created by Thomas Mangin on 2019-05-23.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar, List, Optional, Tuple

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode

# ================================================================ NextHop
#


@Capability.register()
class NextHop(Capability, list):
    ID: ClassVar[int] = Capability.CODE.NEXTHOP

    def __init__(self, data: Tuple[Tuple[AFI, SAFI, AFI], ...] = ()) -> None:
        super().__init__()
        for afi, safi, nhafi in data:
            self.add_nexthop(afi, safi, nhafi)

    def add_nexthop(self, afi: AFI, safi: SAFI, nhafi: AFI) -> None:
        if (afi, safi, nhafi) not in self:
            self.append((afi, safi, nhafi))

    def __str__(self) -> str:
        families = ','.join([f'{afi!s} {safi!s} {nhafi!s}' for (afi, safi, nhafi) in self])
        return f'NextHop({families})'

    def json(self) -> str:
        conversions = ','.join(
            [f' "{afi!s}/{safi!s}/{nhafi!s}"' for (afi, safi, nhafi) in self],
        )
        return f'{{ "name": "nexthop", "conversion": [{conversions} ] }}'

    def extract(self) -> List[bytes]:
        rs = b''
        for afi, safi, nhafi in self:
            rs += afi.pack() + pack('!B', 0) + safi.pack() + nhafi.pack()
        return [
            rs,
        ]

    @staticmethod
    def unpack_capability(instance: NextHop, data: bytes, capability: Optional[CapabilityCode] = None) -> NextHop:  # pylint: disable=W0613
        # XXX: FIXME: we should complain if we have twice the same AFI/SAFI
        # XXX: FIXME: should check that we have not yet seen the capability
        while data:
            afi = AFI.unpack(data[:2])
            safi = SAFI.unpack(data[3:4])
            nexthop = AFI.unpack(data[4:6])
            instance.add_nexthop(afi, safi, nexthop)
            data = data[6:]
        return instance
