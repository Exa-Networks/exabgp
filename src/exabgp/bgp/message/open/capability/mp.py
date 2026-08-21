"""mp.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from exabgp.bgp.message.notification import Notify
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================ MultiProtocol
#


@Capability.register()
class MultiProtocol(Capability, list):
    ENTRY_SIZE = 4  # AFI(2) + reserved(1) + SAFI(1)
    ID = Capability.CODE.MULTIPROTOCOL

    def __str__(self):
        families = ','.join([f'{afi!s} {safi!s}' for (afi, safi) in self])
        return f'Multiprotocol({families})'

    def json(self):
        families = ','.join([f' "{afi!s}/{safi!s}"' for (afi, safi) in self])
        return f'{{ "name": "multiprotocol", "families": [{families} ] }}'

    def extract(self):
        rs = []
        for v in self:
            rs.append(pack('!H', v[0]) + pack('!H', v[1]))
        return rs

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: we should raise if we have twice the same AFI/SAFI
        if len(data) < MultiProtocol.ENTRY_SIZE:
            raise Notify(
                2,
                0,
                'invalid multiprotocol capability, expected %d bytes, got %d' % (MultiProtocol.ENTRY_SIZE, len(data)),
            )
        afi = AFI.unpack(data[:2])
        safi = SAFI.unpack(data[3])
        instance.append((afi, safi))
        return instance
