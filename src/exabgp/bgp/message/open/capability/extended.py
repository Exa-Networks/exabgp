"""asn4.py

Created by Thomas Mangin on 2014-06-30.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.util.types import Buffer

# ========================================================================= ASN4
#


@Capability.register()
class ExtendedMessage(Capability):
    ID = Capability.CODE.EXTENDED_MESSAGE
    INITIAL_SIZE = 4096
    EXTENDED_SIZE = 65535

    def __str__(self) -> str:
        return 'Extended Message(%d)' % self.EXTENDED_SIZE

    def extract_capability_bytes(self) -> list[bytes]:
        return [b'']

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        return cls()

    def json(self) -> str:
        return '{ "name": "extended-message", "size": %d }' % self.EXTENDED_SIZE
