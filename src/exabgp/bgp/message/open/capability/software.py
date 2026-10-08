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
    # revision 00's length octet is told apart from text only below the first printable character
    OLD_LENGTH_UNAMBIGUOUS: ClassVar[int] = 0x20

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

        Revision 00 put a length octet in front of the version, which ExaBGP sent until now
        and FRR still sends when told to.  It is read as such only when it accounts for the
        rest of the value and is below OLD_LENGTH_UNAMBIGUOUS, a control character no
        version string starts with.  From 32 the octet is a printable character, which
        a current value may start with ('0' then 48 octets matched), and the current
        layout, the one the draft defines, wins: an old value of 32 octets or more is shown
        with its length octet in front.  Section 3 has a zero length "treated as an
        encoding error and the Capability MUST be ignored", and invalid UTF-8 must not be
        interpreted: both become the UnknownCapability RFC 5492 section 3 ignores a
        capability with, never a NOTIFICATION, as this capability is only ever displayed.
        """
        old = bool(data) and data[0] == len(data) - 1 and data[0] < cls.OLD_LENGTH_UNAMBIGUOUS
        version = data[1:] if old else data
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
