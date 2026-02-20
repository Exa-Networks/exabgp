"""software_version.py

Copyright (c) 2024 Donatas Abraitis. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# https://datatracker.ietf.org/doc/html/draft-abraitis-bgp-version-capability

from __future__ import annotations

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.version import version


@Capability.register()
class Software(Capability):
    ID = Capability.CODE.SOFTWARE_VERSION
    SOFTWARE_VERSION_MAX_LEN = 64

    def __init__(self):
        software_version = f'ExaBGP/{version}'
        if len(software_version) > self.SOFTWARE_VERSION_MAX_LEN:
            software_version = software_version[: self.SOFTWARE_VERSION_MAX_LEN - 3] + '...'
        self.software_version = software_version

    def __str__(self):
        return 'Software({})'.format(self.software_version)

    def json(self):
        return '{{ "software": "{}" }}'.format(self.software_version)

    def extract(self):
        return [bytes([len(self.software_version)]) + self.software_version.encode('utf-8')]

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        l1 = data[0]
        instance.software_version = data[1 : l1 + 1].decode('utf-8')
        return instance
