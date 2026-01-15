"""linklocal.py

Link-Local Next Hop Capability (RFC draft-ietf-idr-linklocal-capability).

Created for ExaBGP.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log, lazymsg
from exabgp.util.types import Buffer


@Capability.register()
class LinkLocalNextHop(Capability):
    """Link-Local Next Hop Capability (Code 77).

    When negotiated, allows:
    - 16-byte IPv6 next-hop: Link-local only (fe80::/10)
    - 32-byte IPv6 next-hop: Global + link-local (unchanged)

    Capability has no payload (length 0).
    """

    ID = Capability.CODE.LINK_LOCAL_NEXTHOP
    _seen: bool = False

    def __str__(self) -> str:
        return 'Link-Local NextHop'

    def json(self) -> str:
        return '{ "name": "link-local-nexthop" }'

    def extract_capability_bytes(self) -> list[bytes]:
        return [b'']

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:
        assert isinstance(instance, LinkLocalNextHop)
        if instance._seen:
            log.debug(lazymsg('capability.link_local_nexthop.duplicate'), 'parser')
        instance._seen = True
        return instance

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, LinkLocalNextHop):
            return False
        return self.ID == other.ID

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing LinkLocalNextHop for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing LinkLocalNextHop for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing LinkLocalNextHop for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing LinkLocalNextHop for ordering does not make sense')
