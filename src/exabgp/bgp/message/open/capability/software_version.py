# encoding: utf-8
"""
software_version.py

Copyright (c) 2024 Donatas Abraitis. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# https://datatracker.ietf.org/doc/html/draft-abraitis-bgp-version-capability


from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.version import version


@Capability.register()
class SoftwareVersion(Capability):
    ID = Capability.CODE.SOFTRWARE_VERSION
    SOFTWARE_VERSION_MAX_LEN = 64

    def __init__(self):
        self.software_version = f"ExaBGP/{version}"

    def __str__(self):
        return f'SoftwareVersion({self.software_version})'

    def json(self):
        return f'{ "software-version": "{self.software_version}" }'

    def extract(self):
        software_version = self.software_version.encode('utf-8')
        if len(software_version) > self.SOFTWARE_VERSION_MAX_LEN:
            software_version = software_version[: self.SOFTWARE_VERSION_MAX_LEN]
        return [bytes([len(software_version)]) + software_version]

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        l1 = data[0]
        instance.software_version = data[1 : l1 + 1].decode('utf-8')
        return instance
