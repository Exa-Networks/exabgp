"""addpath.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar, Iterable

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log, lazymsg

# ====================================================================== AddPath
#


@Capability.register()
class AddPath(Capability, dict[tuple[AFI, SAFI], int]):
    ID: ClassVar[int] = Capability.CODE.ADD_PATH

    string: ClassVar[dict[int, str]] = {
        0: 'disabled',
        1: 'receive',
        2: 'send',
        3: 'send/receive',
    }

    def __init__(self, families: Iterable[tuple[AFI, SAFI]] = (), send_receive: int = 0) -> None:
        for afi, safi in families:
            self.add_path(afi, safi, send_receive)

    def add_path(self, afi: AFI, safi: SAFI, send_receive: int) -> None:
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

    def extract(self) -> list[bytes]:
        rs = b''
        for v in self:
            if self[v]:
                rs += v[0].pack_afi() + v[1].pack_safi() + pack('!B', self[v])
        return [
            rs,
        ]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: bytes, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, AddPath)
        # Check if this capability was already received (instance would have entries)
        if len(instance) > 0:
            log.debug(lazymsg('capability.addpath.duplicate action=merge'), 'parser')
        while data:
            afi = AFI.unpack_afi(data[:2])
            safi = SAFI.unpack_safi(data[2:3])
            sr = data[3]
            if (afi, safi) in instance:

                def _log_dup(afi: AFI = afi, safi: SAFI = safi) -> str:
                    return f'duplicate AFI/SAFI in AddPath capability: {afi}/{safi}'

                log.debug(_log_dup, 'parser')
            instance.add_path(afi, safi, sr)
            data = data[4:]
        return instance
