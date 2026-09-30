"""labels.py

Multiple Labels Capability (RFC 8277 section 2.1).

Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from struct import pack
from typing import cast, ClassVar

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode, CapabilityDict
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.util.types import Buffer

# RFC 8277 2.1: <AFI (2 octets), SAFI (1 octet), Count (1 octet)>
TRIPLE_SIZE_BYTES = 4
# a Count of 0 or 1 says nothing a missing triple does not, and is ignored
MULTIPLE_LABELS_MIN = 2
MULTIPLE_LABELS_MAX = 255


class MultipleLabels(CapabilityDict[FamilyTuple, int]):
    """The most labels a speaker can receive bound to one prefix, per family.

    Only the triples counting two labels or more are held: one with a Count of 0 or 1 is
    ignored, and so is every triple after the first for a family, the ignored ones
    included.
    """

    ID: ClassVar = Capability.CODE.MULTIPLE_LABELS

    def __init__(self, families: dict[FamilyTuple, int] | None = None) -> None:
        super().__init__()
        self._seen: set[FamilyTuple] = set()
        for family, count in (families or {}).items():
            assert MULTIPLE_LABELS_MIN <= count <= MULTIPLE_LABELS_MAX, 'RFC 8277 2.1: we never send 0 or 1'
            self[family] = count
            self._seen.add(family)

    def __str__(self) -> str:
        entries = ', '.join(f'{afi} {safi} {count}' for (afi, safi), count in self.items())
        return f'MultipleLabels({entries})'

    def json(self) -> str:
        families = ', '.join(f'"{afi}/{safi}": {count}' for (afi, safi), count in self.items())
        return '{{ "name": "multiple-labels"{}{} }}'.format(', ' if families else '', families)

    def extract_capability_bytes(self) -> list[bytes]:
        return [b''.join(afi.pack_afi() + safi.pack_safi() + pack('!B', count) for (afi, safi), count in self.items())]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:
        assert instance.code() == Capability.CODE.MULTIPLE_LABELS, 'registered for code 8 only'
        # the registry builds the class registered for code 8, which is this one
        labels = cast(MultipleLabels, instance)
        # RFC 8277 2.1: a length which is not a multiple of four is malformed
        if len(data) % TRIPLE_SIZE_BYTES:
            raise Notify(2, 0, f'Multiple Labels Capability of {len(data)} octets, not a multiple of four')
        view = memoryview(data)
        for offset in range(0, len(view), TRIPLE_SIZE_BYTES):
            family = (AFI.unpack_afi(view[offset : offset + 2]), SAFI.unpack_safi(view[offset + 2 : offset + 3]))
            count = view[offset + 3]
            # RFC 8277 2.1: all but the first triple for a family are ignored
            if family in labels._seen:
                log.debug(lazymsg('capability.multiple-labels.duplicate family={family}', family=family), 'parser')
                continue
            labels._seen.add(family)
            if count < MULTIPLE_LABELS_MIN:
                continue
            labels[family] = count
        return labels


Capability.register()(MultipleLabels)
