"""refresh.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log

# ================================================================= RouteRefresh
#


class REFRESH:
    ABSENT = 0x01
    NORMAL = 0x02
    ENHANCED = 0x04

    @staticmethod
    def json(refresh: int) -> str:
        if refresh == REFRESH.ABSENT:
            return 'absent'
        if refresh == REFRESH.NORMAL:
            return 'normal'
        if refresh == REFRESH.ENHANCED:
            return 'enhanced'
        return 'unknown'

    def __str__(self) -> str:
        if self == REFRESH.ABSENT:
            return 'absent'
        if self == REFRESH.NORMAL:
            return 'normal'
        if self == REFRESH.ENHANCED:
            return 'enhanced'
        return 'unknown'


@Capability.register()
@Capability.register(Capability.CODE.ROUTE_REFRESH_CISCO)
class RouteRefresh(Capability):
    ID = Capability.CODE.ROUTE_REFRESH
    _seen: bool = False

    def __str__(self) -> str:
        if self.ID == Capability.CODE.ROUTE_REFRESH:
            return 'Route Refresh'
        return 'Cisco Route Refresh'

    def json(self) -> str:
        return '{ "name": "route-refresh", "variant": "%s" }' % (
            'RFC' if self.ID == Capability.CODE.ROUTE_REFRESH else 'Cisco'
        )

    def extract(self) -> list[bytes]:
        return [b'']

    @staticmethod
    def unpack_capability(
        instance: RouteRefresh, data: bytes, capability: CapabilityCode | None = None
    ) -> RouteRefresh:  # pylint: disable=W0613
        if instance._seen:
            log.debug(lambda: 'received duplicate RouteRefresh capability', 'parser')
        instance._seen = True
        return instance

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RouteRefresh):
            return False
        return self.ID == other.ID

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')


# ========================================================= EnhancedRouteRefresh
#


@Capability.register()
class EnhancedRouteRefresh(Capability):
    ID = Capability.CODE.ENHANCED_ROUTE_REFRESH
    _seen: bool = False

    def __str__(self) -> str:
        return 'Enhanced Route Refresh'

    def json(self) -> str:
        return '{ "name": "enhanced-route-refresh" }'

    def extract(self) -> list[bytes]:
        return [b'']

    @staticmethod
    def unpack_capability(
        instance: EnhancedRouteRefresh, data: bytes, capability: CapabilityCode | None = None
    ) -> EnhancedRouteRefresh:  # pylint: disable=W0613
        if instance._seen:
            log.debug(lambda: 'received duplicate EnhancedRouteRefresh capability', 'parser')
        instance._seen = True
        return instance
