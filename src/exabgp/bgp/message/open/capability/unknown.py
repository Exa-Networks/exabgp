"""unknown.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode

# ============================================================ UnknownCapability
#


@Capability.unknown
class UnknownCapability(Capability):
    capability: CapabilityCode
    data: bytes

    def set(self, capability: CapabilityCode, data: bytes = b'') -> UnknownCapability:
        self.capability = capability
        self.data = data
        return self

    def __str__(self) -> str:
        if self.capability in Capability.CODE.reserved:
            return 'Reserved {}'.format(str(self.capability))
        if self.capability in Capability.CODE.unassigned:
            return 'Unassigned {}'.format(str(self.capability))
        return 'Unknown {}'.format(str(self.capability))

    def json(self) -> str:
        if self.capability in Capability.CODE.reserved:
            iana = 'reserved'
        elif self.capability in Capability.CODE.unassigned:
            iana = 'unassigned'
        else:
            iana = 'unknown'
        raw = ''.join('{:02X}'.format(_) for _ in self.data)
        return '{ "name": "unknown", "iana": "%s", "value": %d, "raw": "%s" }' % (iana, self.capability, raw)

    def extract(self) -> list[bytes]:
        return []

    @staticmethod
    def unpack_capability(instance: UnknownCapability, data: bytes, capability: CapabilityCode) -> UnknownCapability:
        return instance.set(capability, data)
