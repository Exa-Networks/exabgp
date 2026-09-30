"""ms.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


from typing import Any, ClassVar

from exabgp.bgp.message.open.capability.capability import Capability, CapabilityList
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.notification import Notify
from exabgp.logger import log, lazymsg
from exabgp.util.types import Buffer

# ================================================================= MultiSession
#

# draft-ietf-idr-bgp-multisession-07 section 4: the value is one octet of flags followed by
# the Session ID.
FLAGS_SIZE_BYTES = 1


class MultiSession(CapabilityList[CapabilityCode]):
    ID: ClassVar = Capability.CODE.MULTISESSION
    _seen: bool = False

    def set(self, data: list[Any]) -> MultiSession:
        self.extend(data)
        return self

    def __str__(self) -> str:
        info = ' (RFC)' if self.code() == Capability.CODE.MULTISESSION else ''
        return 'Multisession{} {}'.format(info, ' '.join([str(capa) for capa in self]))

    def json(self) -> str:
        variant = 'RFC' if self.code() == Capability.CODE.MULTISESSION else 'Cisco'
        return '{{ "name": "multisession", "variant": "{}", "capabilities": [{} ] }}'.format(
            variant,
            ','.join(' "{}"'.format(str(capa)) for capa in self),
        )

    def extract_capability_bytes(self) -> list[bytes]:
        # The draft defines one capability value: a flags byte followed by the
        # complete Session ID list. Returning separate elements here would make
        # pack_capabilities() emit separate MultiSession TLVs instead.
        return [bytes([0, *(int(code) for code in self)])]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, MultiSession)
        if instance._seen:
            # RFC 5492 section 5 lets a receiver keep one instance of a capability sent
            # more than once. Parsing the second one appended its Session ID codes to the
            # first one's list, so two TLVs produced the concatenation of both, which is
            # neither of the Session IDs the peer sent. Keeping the first is also what
            # every ExaBGP before 6.0 needs: it packed the flags byte and each Session ID
            # code as separate one byte capabilities, so its OPEN arrives here as several
            # MultiSession TLVs whose bytes past the first are flags, not Session IDs.
            log.debug(lazymsg('capability.multisession.duplicate action=ignore'), 'parser')
            return instance
        instance._seen = True

        if len(data) < FLAGS_SIZE_BYTES:
            # The draft's value always starts with one flags octet, and infers the
            # Session ID length as "the capability length minus one", so a zero length
            # value is not the encoding the draft defines. Section 4 would give an empty
            # Session ID a meaning, but guessing that a peer meant it is accepting input
            # which does not follow the encoding. Every implementation seen on the wire,
            # Cisco's code 131 included, sends the flags octet. 5.0 accepts this value.
            raise Notify(2, 0, 'multisession capability is missing its flags byte')

        # The first byte is flags. The G bit is deprecated and reserved bits MUST
        # be ignored by receivers. Each remaining byte is one complete Session ID
        # capability code, so no partial-record case exists and the loop is bounded
        # by the received value length. The draft also requires receivers to ignore
        # the MultiSession capability itself if it appears in the Session ID.
        for code in data[FLAGS_SIZE_BYTES:]:
            if code in (Capability.CODE.MULTISESSION, Capability.CODE.MULTISESSION_CISCO):
                continue
            instance.append(CapabilityCode(code))
        return instance


Capability.register(Capability.CODE.MULTISESSION_CISCO)(MultiSession)
Capability.register()(MultiSession)
