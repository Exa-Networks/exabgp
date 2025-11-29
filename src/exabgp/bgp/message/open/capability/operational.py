"""operational.py

Created by Thomas Mangin on 2013-09-01.
Copyright (c) 2013-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log, lazymsg

# https://tools.ietf.org/html/draft-ietf-idr-operational-message-00
# ================================================================== Operational
#


@Capability.register()
class Operational(Capability, list[bytes]):
    ID: ClassVar[int] = Capability.CODE.OPERATIONAL
    _seen: bool = False

    def __str__(self) -> str:
        # XXX: FIXME: could be more verbose
        return 'Operational'

    def json(self) -> str:
        return '{ "name": "operational" }'

    def extract(self) -> list[bytes]:
        return [b'']

    @classmethod
    def unpack_capability(cls, instance: Capability, data: bytes, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, Operational)
        if instance._seen:
            log.debug(lazymsg('capability.operational.duplicate'), 'parser')
        instance._seen = True
        return instance
