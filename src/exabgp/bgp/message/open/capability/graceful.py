"""graceful.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from struct import unpack
from typing import ClassVar, Iterable

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log, lazymsg

# =========================================================== Graceful (Restart)
# RFC 4727 - https://tools.ietf.org/html/rfc4727


@Capability.register()
class Graceful(Capability, dict[tuple[AFI, SAFI], int]):
    MAX: ClassVar[int] = 0xFFFF
    ID: ClassVar[int] = Capability.CODE.GRACEFUL_RESTART

    TIME_MASK: ClassVar[int] = 0x0FFF
    FLAG_MASK: ClassVar[int] = 0xF000

    # 0x8 is binary 1000
    RESTART_STATE: ClassVar[int] = 0x08
    FORWARDING_STATE: ClassVar[int] = 0x80

    restart_flag: int
    restart_time: int

    def set(self, restart_flag: int, restart_time: int, protos: Iterable[tuple[AFI, SAFI, int]]) -> Graceful:
        self.restart_flag = restart_flag
        self.restart_time = restart_time & Graceful.TIME_MASK
        for afi, safi, family_flag in protos:
            self[(afi, safi)] = family_flag & Graceful.FORWARDING_STATE
        return self

    def extract_capability_bytes(self) -> list[bytes]:
        restart = pack('!H', ((self.restart_flag << 12) | (self.restart_time & Graceful.TIME_MASK)))
        families = [afi.pack_afi() + safi.pack_safi() + bytes([self[(afi, safi)]]) for (afi, safi) in self.keys()]
        return [restart + b''.join(families)]

    def __str__(self) -> str:
        families = [(str(afi), str(safi), hex(self[(afi, safi)])) for (afi, safi) in self.keys()]
        sfamilies = ' '.join([f'{afi}/{safi}={family}' for (afi, safi, family) in families])
        return f'Graceful Restart Flags {hex(self.restart_flag)} Time {self.restart_time} {sfamilies}'

    def json(self) -> str:
        restart_str = ' "restart"'
        forwarding_str = ' "forwarding" '
        families_json = ', '.join(
            f'"{afi}/{safi}": [{restart_str if family & 0x80 else ""} ] '
            for afi, safi, family in [(str(a), str(s), self[(a, s)]) for (a, s) in self.keys()]
        )
        d: dict[str, int | str] = {
            'name': '"graceful restart"',
            'time': self.restart_time,
            'address-family-flags': f'{{ {families_json}}}',
            'restart-flags': f'[{forwarding_str if self.restart_flag & 0x8 else " "}] ',
        }
        items = ', '.join(f'"{k}": {v}' for k, v in d.items())
        return f'{{ {items} }}'

    def families(self) -> Iterable[tuple[AFI, SAFI]]:
        return self.keys()

    @classmethod
    def unpack_capability(cls, instance: Capability, data: bytes, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, Graceful)
        # Check if this capability was already received (instance would have entries)
        if len(instance) > 0:
            log.debug(lazymsg('capability.graceful_restart.duplicate action=replace'), 'parser')
            instance.clear()
        restart = unpack('!H', data[:2])[0]
        restart_flag = restart >> 12
        restart_time = restart & Graceful.TIME_MASK
        data = data[2:]
        families: list[tuple[AFI, SAFI, int]] = []
        while data:
            afi = AFI.unpack_afi(data[:2])
            safi = SAFI.unpack_safi(data[2:3])
            flag_family = data[3]
            families.append((afi, safi, flag_family))
            data = data[4:]
        return instance.set(restart_flag, restart_time, families)
