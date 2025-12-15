#!/usr/bin/env python3
"""
Tests for route validation check functions.

The check functions validate that routes have required fields:
- Unicast/multicast routes require nexthop
- Labels required for labeled routes
- RD required for VPN routes

Action is no longer passed to check - it's determined by which RIB method is called.
For withdraws, callers set a dummy nexthop before calling check.
"""

from unittest.mock import Mock

from exabgp.rib.route import Route
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.configuration.announce.ip import AnnounceIP


class TestAnnounceIPCheck:
    """Test AnnounceIP.check() route validation."""

    def _create_mock_route(
        self,
        has_nexthop: bool = True,
        afi: AFI = AFI.ipv4,
        safi: SAFI = SAFI.unicast,
    ) -> Mock:
        """Create a mock Route for testing check()."""
        route = Mock(spec=Route)

        # Create mock NLRI
        nlri = Mock()
        nlri.afi = afi
        nlri.safi = safi
        if has_nexthop:
            nexthop = IP.pton('1.2.3.4')
        else:
            nexthop = IP.NoNextHop
        nlri.nexthop = nexthop
        route.nlri = nlri
        # Route.nexthop property
        route.nexthop = nexthop

        return route

    def test_route_with_nexthop_passes(self):
        """Route with nexthop passes validation."""
        route = self._create_mock_route(has_nexthop=True)

        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is True

    def test_route_without_nexthop_fails(self):
        """Route without nexthop fails validation (for unicast/multicast)."""
        route = self._create_mock_route(has_nexthop=False)

        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is False

    def test_ipv6_route_with_nexthop_passes(self):
        """IPv6 route with nexthop passes validation."""
        route = self._create_mock_route(has_nexthop=True, afi=AFI.ipv6)

        result = AnnounceIP.check(route, AFI.ipv6)
        assert result is True

    def test_non_unicast_without_nexthop_passes(self):
        """Non-unicast/multicast SAFI routes don't require nexthop."""
        route = self._create_mock_route(has_nexthop=False, safi=SAFI.flow_ip)

        result = AnnounceIP.check(route, AFI.ipv4)
        assert result is True


# NOTE: Action is no longer passed to check functions.
# For withdraws, the caller (withdraw_route in announce.py) sets a dummy
# nexthop (0.0.0.0) before calling check, so the validation passes.
