"""software_version.py

Copyright (c) 2024 Donatas Abraitis. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# https://datatracker.ietf.org/doc/html/draft-abraitis-bgp-version-capability-18

from __future__ import annotations

from typing import ClassVar
import json

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.unknown import UnknownCapability
from exabgp.version import version
from exabgp.util.types import Buffer
from exabgp.util.intvalue import json_number


class Software(Capability):
    ID: ClassVar = Capability.CODE.SOFTWARE_VERSION
    SOFTWARE_VERSION_MAX_LEN: ClassVar[int] = 64

    def __init__(self) -> None:
        software_version = f'ExaBGP/{version}'
        if len(software_version) > self.SOFTWARE_VERSION_MAX_LEN:
            software_version = software_version[: self.SOFTWARE_VERSION_MAX_LEN - 3] + '...'
        self.software_version: str = software_version

    def __str__(self) -> str:
        return 'Software({})'.format(self.software_version)

    def json(self) -> str:
        return '{{ "software": {} }}'.format(json.dumps(self.software_version, default=json_number))

    def extract_capability_bytes(self) -> list[bytes]:
        """The version as the whole Capability Value, which revisions 15 to 18 of the draft use.

        Revision 00 put a length octet in front of it; the value is now the string alone,
        its length the Capability Length (section 3), which SHOULD be no greater than 64.
        The cut is in bytes, on a character boundary: a decoded peer version may hold
        characters wider than one, and half of one is invalid UTF-8.
        """
        encoded = self.software_version.encode('utf-8')[: self.SOFTWARE_VERSION_MAX_LEN]
        encoded = encoded.decode('utf-8', 'ignore').encode('utf-8')
        assert 0 < len(encoded) <= self.SOFTWARE_VERSION_MAX_LEN, 'section 3: a length of zero is an encoding error'
        return [encoded]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        """The version a peer sent, in either encoding; ignored if it cannot be shown.

        A first octet which accounts for the rest of the value is the length octet of
        revision 00, which ExaBGP sent until now and FRR still sends when told to; FRR reads
        it the same way.  Section 3 has a zero length "treated as an encoding error and the
        Capability MUST be ignored", and invalid UTF-8 must not be interpreted: both become
        the UnknownCapability RFC 5492 section 3 ignores a capability with, never a
        NOTIFICATION, as this capability is only ever displayed.
        """
        version = data[1:] if data and data[0] == len(data) - 1 else data
        try:
            decoded = bytes(version).decode('utf-8')
        except UnicodeDecodeError:
            decoded = ''
        if not decoded:
            return UnknownCapability().set(capability, data)
        software = cls()
        software.software_version = decoded
        return software


Capability.register()(Software)
