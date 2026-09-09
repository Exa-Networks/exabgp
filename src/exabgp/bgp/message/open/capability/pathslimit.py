"""pathslimit.py

PATHS-LIMIT Capability (draft-abraitis-idr-addpath-paths-limit-04).

Created by James Raphael Tiovalen on 2026-04-27.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack

from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.notification import Notify
from exabgp.logger import log, lazymsg
from exabgp.util.types import Buffer


@Capability.register()
class PathsLimit(Capability, dict[FamilyTuple, int]):
    ID = Capability.CODE.PATHS_LIMIT
    ENTRY_SIZE = 5
    # A capability's length is a single byte, and the draft tells a speaker to describe all
    # of its families in one instance of the capability. So the most a conforming peer can
    # ask for is what one instance holds. ExaBGP still merges a repeated capability, being
    # lenient about how the tuples arrive, but not about how many there can be.
    MAX_FAMILIES = 0xFF // ENTRY_SIZE

    def __init__(self, families: dict[FamilyTuple, int] | None = None) -> None:
        self._ignored_families: set[FamilyTuple] = set()
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
        families = ', '.join(f'"{afi}/{safi}": {self[(afi, safi)]}' for afi, safi in self)
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
        view = memoryview(data)
        while view:
            if len(view) < cls.ENTRY_SIZE:
                raise Notify(
                    2, 0, f'PATHS-LIMIT capability truncated: need {cls.ENTRY_SIZE} bytes per entry, got {len(view)}'
                )
            afi = AFI.unpack_afi(view[:2])
            safi = SAFI.unpack_safi(view[2:3])
            limit = (view[3] << 8) | view[4]
            view = view[cls.ENTRY_SIZE :]
            family = (afi, safi)
            if family in instance or family in instance._ignored_families:

                def _log_dup(afi: AFI = afi, safi: SAFI = safi) -> str:
                    return f'duplicate AFI/SAFI in PathsLimit capability: {afi}/{safi}'

                log.debug(_log_dup, 'parser')
                continue
            if len(instance) + len(instance._ignored_families) >= cls.MAX_FAMILIES:
                # Well formed, only longer than a conforming speaker can have meant. RFC 5492
                # has us ignore capability content we cannot use rather than answer with a
                # NOTIFICATION, and a session is worth more than the families past this point.
                # A truncated entry is a different matter and still ends the session, above.
                log.debug(lazymsg('capability.paths-limit.capacity families={n}', n=cls.MAX_FAMILIES), 'parser')
                break
            if limit == 0:
                # Even an ignored zero tuple wins over later tuples in this OPEN.
                instance._ignored_families.add(family)
                continue
            instance.set_limit(afi, safi, limit)
        return instance
