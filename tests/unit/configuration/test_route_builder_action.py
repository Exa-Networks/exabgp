#!/usr/bin/env python3
"""
Tests for route validation when a route is read.

Reading a route validates its structure, NOT nexthop presence.
Nexthop validation happens at wire format generation time, not during
route parsing. Withdrawals don't have nexthop per RFC 4271.

The legacy parser did this in AnnounceIP.check(); the grammar reads the route
(Configuration.partial / parse_route_text) and must accept the same routes.
"""

from __future__ import annotations

from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


def _read(text: str, action: str = 'announce') -> list:
    configuration = Configuration([])
    routes = configuration.parse_route_text(text, action)
    assert routes, str(configuration.error)
    return routes


class TestAnnounceIPCheck:
    """Test the route validation done when an IP route is read."""

    def test_route_with_nexthop_passes(self):
        """Route with nexthop passes validation."""
        (route,) = _read('route 10.0.0.0/24 next-hop 1.2.3.4')

        assert route.nexthop == IP.from_string('1.2.3.4')

    def test_route_without_nexthop_passes(self):
        """Route without nexthop passes validation.

        Nexthop validation is NOT done when the route is read - it happens at wire format
        generation time. Withdrawals legitimately don't have nexthop per RFC 4271.
        """
        for action in ('announce', 'withdraw'):
            (route,) = _read('route 10.0.0.0/24', action)

            assert route.nexthop is IP.NoNextHop

    def test_ipv6_route_with_nexthop_passes(self):
        """IPv6 route with nexthop passes validation."""
        (route,) = _read('route 2001:db8::/32 next-hop 2001:db8::1')

        assert route.nlri.afi == AFI.ipv6
        assert route.nexthop == IP.from_string('2001:db8::1')

    def test_non_unicast_without_nexthop_passes(self):
        """Non-unicast/multicast SAFI routes pass validation without nexthop."""
        configuration = Configuration([])

        assert configuration.partial('flow', 'route { match { destination 10.0.0.0/24; } then { discard; } }')
        (route,) = configuration.pop_routes()

        assert route.nlri.safi == SAFI.flow_ip
        assert route.nexthop is IP.NoNextHop
