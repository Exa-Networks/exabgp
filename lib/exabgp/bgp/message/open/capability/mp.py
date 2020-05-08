# encoding: utf-8
"""
mp.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================ MultiProtocol
#


@Capability.register()
class MultiProtocol(Capability, list):
    ID = Capability.CODE.MULTIPROTOCOL

    def __str__(self):
        return 'Multiprotocol(' + ','.join(["%s %s" % (str(afi), str(safi)) for (afi, safi) in self]) + ')'

    def json(self):
        return '{ "name": "multiprotocol", "families": [%s ] }' % ','.join(
            [' "%s/%s"' % (str(afi), str(safi)) for (afi, safi) in self]
        )

    def extract(self):
        rs = []
        for v in self:
            rs.append(pack('!H', v[0]) + pack('!H', v[1]))
        return rs

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: we should raise if we have twice the same AFI/SAFI
        afi = AFI.unpack(data[:2])
        safi = SAFI.unpack(data[3])
        instance.append((afi, safi))
        return instance
