"""pathslimit.py

PATHS-LIMIT Capability (draft-abraitis-idr-addpath-paths-limit-04).

Created by James Raphael Tiovalen on 2026-04-27.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar

from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.notification import Notify
from exabgp.logger import log, lazymsg
from exabgp.util.types import Buffer


@Capability.register()
class PathsLimit(Capability, dict[FamilyTuple, int]):
    ID: ClassVar[int] = Capability.CODE.PATHS_LIMIT

    def __init__(self, families: dict[FamilyTuple, int] | None = None) -> None:
        if families:
            for (afi, safi), limit in families.items():
                self.set_limit(afi, safi, limit)

    def set_limit(self, afi: AFI, safi: SAFI, limit: int) -> None:
        if not (0 <= limit <= 65535):
            raise ValueError(f'paths limit must be 0-65535, got {limit}')
        self[(afi, safi)] = limit

    def __str__(self) -> str:
        entries = ', '.join(f'{afi} {safi} {self[(afi, safi)]}' for afi, safi in self)
        return f'PathsLimit({entries})'

    def json(self) -> str:
        families = ', '.join(
            f'"{afi}/{safi}": {self[(afi, safi)]}' for afi, safi in self
        )
        return '{{ "name": "paths-limit"{}{} }}'.format(', ' if families else '', families)

    def extract_capability_bytes(self) -> list[bytes]:
        rs = b''
        for (afi, safi), limit in self.items():
            if limit > 0:
                rs += afi.pack_afi() + safi.pack_safi() + pack('!H', limit)
        return [rs]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:
        assert isinstance(instance, PathsLimit)
        if len(instance) > 0:
            log.debug(lazymsg('capability.paths-limit.duplicate action=merge'), 'parser')
        while data:
            if len(data) < 5:
                raise Notify(2, 0, f'PATHS-LIMIT capability truncated: need 5 bytes per entry, got {len(data)}')
            afi = AFI.unpack_afi(data[:2])
            safi = SAFI.unpack_safi(data[2:3])
            limit = (data[3] << 8) | data[4]
            if limit == 0:
                data = data[5:]
                continue
            if (afi, safi) in instance:
                def _log_dup(afi: AFI = afi, safi: SAFI = safi) -> str:
                    return f'duplicate AFI/SAFI in PathsLimit capability: {afi}/{safi}'
                log.debug(_log_dup, 'parser')
                data = data[5:]
                continue
            instance.set_limit(afi, safi, limit)
            data = data[5:]
        return instance
