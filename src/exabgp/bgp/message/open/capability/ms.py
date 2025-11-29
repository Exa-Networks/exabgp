"""ms.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, ClassVar

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log, lazymsg

# ================================================================= MultiSession
#


@Capability.register()
@Capability.register(Capability.CODE.MULTISESSION_CISCO)
class MultiSession(Capability, list):
    ID: ClassVar[int] = Capability.CODE.MULTISESSION
    _seen: bool = False

    def set(self, data: list[Any]) -> MultiSession:
        self.extend(data)
        return self

    # XXX: FIXME: Looks like we could do with something in this Caoability
    def __str__(self) -> str:
        info = ' (RFC)' if self.ID == Capability.CODE.MULTISESSION else ''
        return 'Multisession{} {}'.format(info, ' '.join([str(capa) for capa in self]))

    def json(self) -> str:
        variant = 'RFC' if self.ID == Capability.CODE.MULTISESSION else 'Cisco'
        return '{{ "name": "multisession", "variant": "{}", "capabilities": [{} ] }}'.format(
            variant,
            ','.join(' "{}"'.format(str(capa)) for capa in self),
        )

    def extract(self) -> list[bytes]:
        # can probably be written better
        rs: list[bytes] = [
            bytes([0]),
        ]
        for v in self:
            rs.append(bytes([v]))
        return rs

    @staticmethod
    def unpack_capability(
        instance: MultiSession, data: bytes, capability: CapabilityCode | None = None
    ) -> MultiSession:  # pylint: disable=W0613
        if instance._seen:
            log.debug(lazymsg('capability.multisession.duplicate'), 'parser')
        instance._seen = True
        return instance
