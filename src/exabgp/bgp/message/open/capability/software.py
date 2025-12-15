"""software_version.py

Copyright (c) 2024 Donatas Abraitis. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# https://datatracker.ietf.org/doc/html/draft-abraitis-bgp-version-capability

from __future__ import annotations

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.notification import Notify
from exabgp.version import version
from exabgp.util.types import Buffer


@Capability.register()
class Software(Capability):
    ID = Capability.CODE.SOFTWARE_VERSION
    SOFTWARE_VERSION_MAX_LEN = 64

    def __init__(self) -> None:
        software_version = f'ExaBGP/{version}'
        if len(software_version) > self.SOFTWARE_VERSION_MAX_LEN:
            software_version = software_version[: self.SOFTWARE_VERSION_MAX_LEN - 3] + '...'
        self.software_version: str = software_version

    def __str__(self) -> str:
        return 'Software({})'.format(self.software_version)

    def json(self) -> str:
        return '{{ "software": "{}" }}'.format(self.software_version)

    def extract_capability_bytes(self) -> list[bytes]:
        return [bytes([len(self.software_version)]) + self.software_version.encode('utf-8')]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, Software)
        # Software capability: length(1) + version_string
        if len(data) < 1:
            raise Notify(2, 0, 'Software capability too short: need at least 1 byte')
        l1 = data[0]
        if len(data) < l1 + 1:
            raise Notify(2, 0, f'Software capability truncated: need {l1 + 1} bytes, got {len(data)}')
        instance.software_version = data[1 : l1 + 1].decode('utf-8')
        return instance
