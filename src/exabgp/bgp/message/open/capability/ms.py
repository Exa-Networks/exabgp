"""ms.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
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
        # can probably be written better
        rs: list[bytes] = [
            bytes([0]),
        ]
        for v in self:
            rs.append(bytes([v]))
        return rs

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, MultiSession)
        if instance._seen:
            log.debug(lazymsg('capability.multisession.duplicate'), 'parser')
        instance._seen = True
        # The value is a set of 1-octet session-id capability codes (one per BGP
        # session the peer splits this capability set onto, per
        # draft-ietf-idr-bgp-multisession). Every remaining byte is a complete
        # record, so the loop below is bounded by `data` shrinking by one byte
        # each pass; there is no partial-record case to Notify() on, unlike the
        # multi-byte records in graceful.py/addpath.py.
        #
        # extract_capability_bytes() always prepends a bytes([0]) placeholder
        # ahead of the real session-id bytes, and pack_capabilities() turns every
        # element it returns -- that placeholder included -- into its own
        # capability TLV under this same code; Capability.unpack() folds every
        # TLV for a given code into this one instance via capabilities.get(). A
        # 0x00 byte is CapabilityCode.RESERVED, never a real session id .set()
        # adds, so it is skipped here: that is what makes set(X) -> pack ->
        # unpack recover exactly X instead of X | {RESERVED}.
        while data:
            code = data[0]
            if code:
                instance.append(CapabilityCode(code))
            data = data[1:]
        return instance
