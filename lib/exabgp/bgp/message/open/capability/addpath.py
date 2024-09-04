# encoding: utf-8
"""
addpath.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.util import ordinal
from exabgp.bgp.message.open.capability.capability import Capability

# ====================================================================== AddPath
#


@Capability.register()
class AddPath(Capability, dict):
    ID = Capability.CODE.ADD_PATH

    string = {
        0: 'disabled',
        1: 'receive',
        2: 'send',
        3: 'send/receive',
    }

    def __init__(self, families=(), send_receive=0):
        for afi, safi in families:
            self.add_path(afi, safi, send_receive)

    def add_path(self, afi, safi, send_receive):
        self[(afi, safi)] = send_receive

    def __str__(self):
        return (
            'AddPath('
            + ','.join(
                [
                    "%s %s %s" % (self.string[self[aafi]], xafi, xsafi)
                    for (aafi, xafi, xsafi) in [((afi, safi), str(afi), str(safi)) for (afi, safi) in self]
                ]
            )
            + ')'
        )

    def json(self):
        families = ','.join(
            '"%s/%s": "%s"' % (xafi, xsafi, self.string[self[aafi]])
            for (aafi, xafi, xsafi) in (((afi, safi), str(afi), str(safi)) for (afi, safi) in self)
        )
        return '{ "name": "addpath"%s%s }' % (', ' if families else '', families)

    def extract(self):
        rs = b''
        for v in self:
            if self[v]:
                rs += v[0].pack() + v[1].pack() + pack('!B', self[v])
        return [
            rs,
        ]

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: should check that we have not yet seen the capability
        while data:
            afi = AFI.unpack(data[:2])
            safi = SAFI.unpack(data[2])
            sr = ordinal(data[3])
            instance.add_path(afi, safi, sr)
            data = data[4:]
        return instance
