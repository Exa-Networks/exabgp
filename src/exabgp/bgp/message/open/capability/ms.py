"""ms.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.notification import Notify
from exabgp.logger import log, lazymsg
from exabgp.util.types import Buffer

# ================================================================= MultiSession
#


@Capability.register()
@Capability.register(Capability.CODE.MULTISESSION_CISCO)
class MultiSession(Capability, list[CapabilityCode]):
    ID = Capability.CODE.MULTISESSION
    _seen: bool = False

    def set(self, data: list[Any]) -> MultiSession:
        self.extend(data)
        return self

    def __str__(self) -> str:
        info = ' (RFC)' if self.ID == Capability.CODE.MULTISESSION else ''
        return 'Multisession{} {}'.format(info, ' '.join([str(capa) for capa in self]))

    def json(self) -> str:
        variant = 'RFC' if self.ID == Capability.CODE.MULTISESSION else 'Cisco'
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

        if not data:
            # The draft's value always starts with one flags octet. An empty
            # Session ID is therefore encoded as a one-byte value (0x00 flags
            # and no following codes), not as a zero-length value. Without the
            # flags octet the Session ID length would be capability length - 1,
            # which is impossible, so reject the malformed OPEN.
            raise Notify(2, 0, 'multisession capability is missing its flags byte')

        # The first byte is flags. The G bit is deprecated and reserved bits MUST
        # be ignored by receivers. Each remaining byte is one complete Session ID
        # capability code, so no partial-record case exists and the loop is bounded
        # by the received value length. The draft also requires receivers to ignore
        # the MultiSession capability itself if it appears in the Session ID.
        for code in data[1:]:
            if code in (Capability.CODE.MULTISESSION, Capability.CODE.MULTISESSION_CISCO):
                continue
            instance.append(CapabilityCode(code))
        return instance
