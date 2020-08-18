# encoding: utf-8
"""
refresh.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================= RouteRefresh
#


class REFRESH(object):
    ABSENT = 0x01
    NORMAL = 0x02
    ENHANCED = 0x04

    @staticmethod
    def json(refresh):
        if refresh == REFRESH.ABSENT:
            return 'absent'
        if refresh == REFRESH.NORMAL:
            return 'normal'
        if refresh == REFRESH.ENHANCED:
            return 'enhanced'
        return 'unknown'


@Capability.register()
@Capability.register(Capability.CODE.ROUTE_REFRESH_CISCO)
class RouteRefresh(Capability):
    ID = Capability.CODE.ROUTE_REFRESH

    def __str__(self):
        if self.ID == Capability.CODE.ROUTE_REFRESH:
            return 'Route Refresh'
        return 'Cisco Route Refresh'

    def json(self):
        return '{ "name": "route-refresh", "variant": "%s" }' % (
            'RFC' if self.ID == Capability.CODE.ROUTE_REFRESH else 'Cisco'
        )

    def extract(self):
        return [b'']

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: we should set that that instance was seen and raise if seen twice
        return instance

    def __eq__(self, other):
        if not isinstance(other, RouteRefresh):
            return False
        return self.ID == other.ID

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')

    def __le__(self, other):
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')

    def __gt__(self, other):
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')

    def __ge__(self, other):
        raise RuntimeError('comparing RouteRefresh for ordering does not make sense')


# ========================================================= EnhancedRouteRefresh
#


@Capability.register()
class EnhancedRouteRefresh(Capability):
    ID = Capability.CODE.ENHANCED_ROUTE_REFRESH

    def __str__(self):
        return 'Enhanced Route Refresh'

    def json(self):
        return '{ "name": "enhanced-route-refresh" }'

    def extract(self):
        return [b'']

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # XXX: FIXME: we should set that that instance was seen and raise if seen twice
        return instance
