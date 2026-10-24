"""addpath.py

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

    ENTRY_SIZE = 4  # AFI(2) + SAFI(1) + Send/Receive(1)

    @classmethod
    def send_receive_name(cls, value):
        # RFC 7911 defines 1, 2 and 3.  A peer can send anything, and looking an
        # unknown value up in the table raised KeyError from json() and __str__(),
        # which is to say from the API writer and the logger.
        return cls.string.get(value, 'invalid ({})'.format(value))

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
                    '{} {} {}'.format(self.send_receive_name(self[aafi]), xafi, xsafi)
                    for (aafi, xafi, xsafi) in [((afi, safi), str(afi), str(safi)) for (afi, safi) in self]
                ],
            )
            + ')'
        )

    def json(self):
        families = ','.join(
            '"{}/{}": "{}"'.format(xafi, xsafi, self.send_receive_name(self[aafi]))
            for (aafi, xafi, xsafi) in (((afi, safi), str(afi), str(safi)) for (afi, safi) in self)
        )
        return '{{ "name": "addpath"{}{} }}'.format(', ' if families else '', families)

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
            if len(data) < AddPath.ENTRY_SIZE:
                raise Notify(2, 0, 'invalid ADD-PATH capability, trailing data')
            afi = AFI.unpack(data[:2])
            safi = SAFI.unpack(data[2])
            sr = data[3]
            # the value is consumed as a bitmask during negotiation, so refusing an
            # unknown one would change which sessions come up.  It is kept, and the
            # rendering below is what stops it raising KeyError.
            instance.add_path(afi, safi, sr)
            data = data[AddPath.ENTRY_SIZE :]
        return instance
