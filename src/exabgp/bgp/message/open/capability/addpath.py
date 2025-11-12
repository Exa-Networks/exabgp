"""addpath.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar, Dict, Iterable, List, Tuple

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.protocol.family import _AFI
from exabgp.protocol.family import _SAFI
from exabgp.bgp.message.open.capability.capability import Capability

# ====================================================================== AddPath
#


@Capability.register()
class AddPath(Capability, dict):  # type: ignore[type-arg]
    ID: ClassVar[int] = Capability.CODE.ADD_PATH

    string: ClassVar[Dict[int, str]] = {
        0: 'disabled',
        1: 'receive',
        2: 'send',
        3: 'send/receive',
    }

    def __init__(self, families: Iterable[Tuple[_AFI, _SAFI]] = (), send_receive: int = 0) -> None:
        for afi, safi in families:
            self.add_path(afi, safi, send_receive)

    def add_path(self, afi: _AFI, safi: _SAFI, send_receive: int) -> None:
        self[(afi, safi)] = send_receive

    def __str__(self) -> str:
        return (
            'AddPath('
            + ','.join(
                [
                    '{} {} {}'.format(self.string[self[aafi]], xafi, xsafi)
                    for (aafi, xafi, xsafi) in [((afi, safi), str(afi), str(safi)) for (afi, safi) in self]
                ],
            )
            + ')'
        )

    def json(self) -> str:
        families = ','.join(
            '"{}/{}": "{}"'.format(xafi, xsafi, self.string[self[aafi]])
            for (aafi, xafi, xsafi) in (((afi, safi), str(afi), str(safi)) for (afi, safi) in self)
        )
        return '{{ "name": "addpath"{}{} }}'.format(', ' if families else '', families)

    def extract(self) -> List[bytes]:
        rs = b''
        for v in self:
            if self[v]:
                rs += v[0].pack() + v[1].pack() + pack('!B', self[v])
        return [
            rs,
        ]

    @staticmethod
    def unpack_capability(instance: AddPath, data: bytes, capability: int | None = None) -> AddPath:  # pylint: disable=W0613
        # XXX: FIXME: should check that we have not yet seen the capability
        while data:
            afi = AFI.unpack(data[:2])
            safi = SAFI.unpack(data[2])
            sr = data[3]
            instance.add_path(afi, safi, sr)
            data = data[4:]
        return instance
