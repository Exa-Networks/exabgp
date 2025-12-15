#!/usr/bin/env python3
"""
Tests for RIB UpdateCollection generation.

Verifies that updates() yields correct UpdateCollection objects:
- Announces contain RoutedNLRI (nlri + nexthop)
- Withdraws contain bare NLRI
- Attributes correctly associated
- Withdraws yielded before announces
- Grouping behavior for different families
"""

import sys
import os
from unittest.mock import Mock

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

# Mock logger before importing
from exabgp.logger.option import option

mock_logger = Mock()
mock_logger.debug = Mock()
mock_logger.info = Mock()
mock_logger.warning = Mock()
mock_logger.error = Mock()
option.logger = mock_logger

from exabgp.rib.outgoing import OutgoingRIB  # noqa: E402
from exabgp.rib.route import Route  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.collection import UpdateCollection, RoutedNLRI  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.attribute.origin import Origin  # noqa: E402
from exabgp.bgp.message.refresh import RouteRefresh  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP, IPv4  # noqa: E402


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_nlri(prefix: str, afi: AFI = AFI.ipv4) -> INET:
    """Create an INET NLRI for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    cidr = CIDR.make_cidr(IP.pton(ip_str), mask)
    return INET.from_cidr(cidr, afi, SAFI.unicast)


def create_route(prefix: str, afi: AFI = AFI.ipv4, origin: int = Origin.IGP) -> Route:
    """Create a Route for testing."""
    nlri = create_nlri(prefix, afi)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(origin)
    return Route(nlri, attrs, nexthop=IP.NoNextHop)


def create_route_with_nexthop(prefix: str, nexthop_str: str = '192.168.1.1') -> Route:
    """Create a Route with a concrete nexthop."""
    nlri = create_nlri(prefix)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(Origin.IGP)
    nexthop = IPv4(IPv4.pton(nexthop_str))
    return Route(nlri, attrs, nexthop=nexthop)


def create_rib(families: set | None = None) -> OutgoingRIB:
    """Create a test RIB."""
    if families is None:
        families = {(AFI.ipv4, SAFI.unicast)}
    return OutgoingRIB(cache=True, families=families)


def collect_updates(rib: OutgoingRIB, grouped: bool = False) -> list:
    """Collect all updates from RIB."""
    return list(rib.updates(grouped=grouped))


# ==============================================================================
# Test UpdateCollection Content - Announces
# ==============================================================================


class TestUpdateCollectionAnnounces:
    """Tests for announce content in UpdateCollection."""

    def test_announces_contain_routed_nlri(self):
        """Announces are RoutedNLRI objects (nlri + nexthop)."""
        rib = create_rib()
        route = create_route('10.0.0.0/24')

        rib.add_to_rib(route)

        updates = collect_updates(rib)

        assert len(updates) == 1
        assert len(updates[0].announces) == 1
        assert isinstance(updates[0].announces[0], RoutedNLRI)

    def test_routed_nlri_has_correct_nlri(self):
        """RoutedNLRI contains the correct NLRI."""
        rib = create_rib()
        route = create_route('10.0.0.0/24')

        rib.add_to_rib(route)

        updates = collect_updates(rib)

        routed = updates[0].announces[0]
        assert routed.nlri is route.nlri

    def test_routed_nlri_has_correct_nexthop(self):
        """RoutedNLRI contains the correct nexthop."""
        rib = create_rib()
        route = create_route_with_nexthop('10.0.0.0/24', '192.168.1.1')

        rib.add_to_rib(route)

        updates = collect_updates(rib)

        routed = updates[0].announces[0]
        assert str(routed.nexthop) == '192.168.1.1'

    def test_multiple_announces_in_grouped_mode(self):
        """Multiple routes with same attrs grouped in one UpdateCollection."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)

        updates = collect_updates(rib, grouped=True)

        # Should be one update with multiple announces
        assert len(updates) == 1
        assert len(updates[0].announces) == 2


# ==============================================================================
# Test UpdateCollection Content - Withdraws
# ==============================================================================


class TestUpdateCollectionWithdraws:
    """Tests for withdraw content in UpdateCollection."""

    def test_withdraws_contain_nlri_objects(self):
        """Withdraws contain bare NLRI objects (not RoutedNLRI)."""
        rib = create_rib()
        route = create_route('10.0.0.0/24')

        rib.add_to_rib(route)
        collect_updates(rib)  # Clear pending

        rib.del_from_rib(route)
        updates = collect_updates(rib)

        assert len(updates) == 1
        assert len(updates[0].withdraws) == 1
        # Should be NLRI, not RoutedNLRI
        assert not isinstance(updates[0].withdraws[0], RoutedNLRI)

    def test_withdraw_has_empty_announces(self):
        """Withdraw UpdateCollection has empty announces list."""
        rib = create_rib()
        route = create_route('10.0.0.0/24')

        rib.add_to_rib(route)
        collect_updates(rib)

        rib.del_from_rib(route)
        updates = collect_updates(rib)

        assert len(updates[0].announces) == 0
        assert len(updates[0].withdraws) == 1


# ==============================================================================
# Test UpdateCollection Content - Attributes
# ==============================================================================


class TestUpdateCollectionAttributes:
    """Tests for attribute content in UpdateCollection."""

    def test_attributes_correctly_associated_with_announces(self):
        """Attributes in UpdateCollection match route attributes."""
        rib = create_rib()
        route = create_route('10.0.0.0/24', origin=Origin.EGP)

        rib.add_to_rib(route)

        updates = collect_updates(rib)

        attrs = updates[0].attributes
        assert Origin.ID in attrs
        assert attrs[Origin.ID].origin == Origin.EGP

    def test_different_attributes_create_different_updates(self):
        """Routes with different attributes yield separate UpdateCollections."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24', origin=Origin.IGP)
        route2 = create_route('10.0.2.0/24', origin=Origin.EGP)

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)

        updates = collect_updates(rib, grouped=True)

        # Different attributes = different updates even in grouped mode
        assert len(updates) == 2


# ==============================================================================
# Test Update Ordering
# ==============================================================================


class TestUpdateOrdering:
    """Tests for ordering of updates."""

    def test_withdraws_yielded_before_announces(self):
        """Withdraw updates are yielded before announce updates."""
        rib = create_rib()

        # Add two routes
        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')
        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        collect_updates(rib)  # Clear pending

        # Withdraw route1 and add route3 in same batch
        route3 = create_route('10.0.3.0/24')
        rib.del_from_rib(route1)
        rib.add_to_rib(route3)

        updates = collect_updates(rib)

        # First update should be withdraw
        assert len(updates[0].withdraws) > 0
        assert len(updates[0].announces) == 0

        # Second update should be announce
        assert len(updates[1].announces) > 0
        assert len(updates[1].withdraws) == 0

    def test_multiple_withdraws_before_announces(self):
        """All withdraws come before all announces."""
        rib = create_rib()

        # Add routes
        routes = [create_route(f'10.0.{i}.0/24') for i in range(3)]
        for r in routes:
            rib.add_to_rib(r)
        collect_updates(rib)

        # Withdraw all and add new ones
        for r in routes:
            rib.del_from_rib(r)
        new_routes = [create_route(f'10.1.{i}.0/24') for i in range(2)]
        for r in new_routes:
            rib.add_to_rib(r)

        updates = collect_updates(rib)

        # Count withdraws and announces in order
        saw_announce = False
        for update in updates:
            if update.announces:
                saw_announce = True
            if update.withdraws:
                # Should not see withdraw after announce
                assert not saw_announce, 'Withdraw after announce!'


# ==============================================================================
# Test Grouping Behavior
# ==============================================================================


class TestUpdateGrouping:
    """Tests for grouped vs non-grouped update generation."""

    def test_grouped_true_combines_same_attributes(self):
        """grouped=True combines routes with same attributes."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24', origin=Origin.IGP)
        route2 = create_route('10.0.2.0/24', origin=Origin.IGP)
        route3 = create_route('10.0.3.0/24', origin=Origin.IGP)

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)
        rib.add_to_rib(route3)

        updates = collect_updates(rib, grouped=True)

        # All same attributes = one update
        assert len(updates) == 1
        assert len(updates[0].announces) == 3

    def test_grouped_false_separates_all(self):
        """grouped=False yields one update per route."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)

        updates = collect_updates(rib, grouped=False)

        # Non-grouped = one update per route
        assert len(updates) == 2
        assert len(updates[0].announces) == 1
        assert len(updates[1].announces) == 1

    def test_ipv4_unicast_grouped(self):
        """IPv4 unicast respects grouped flag."""
        rib = create_rib(families={(AFI.ipv4, SAFI.unicast)})

        route1 = create_route('10.0.1.0/24')
        route2 = create_route('10.0.2.0/24')

        rib.add_to_rib(route1)
        rib.add_to_rib(route2)

        # Grouped
        updates_grouped = collect_updates(rib, grouped=True)

        # Re-add for non-grouped test
        rib.add_to_rib(route1, force=True)
        rib.add_to_rib(route2, force=True)
        updates_nongrouped = collect_updates(rib, grouped=False)

        assert len(updates_grouped) == 1
        assert len(updates_nongrouped) == 2


# ==============================================================================
# Test Route Refresh Generation
# ==============================================================================


class TestRouteRefreshGeneration:
    """Tests for Route Refresh message generation."""

    def test_refresh_yields_route_refresh_messages(self):
        """resend() causes RouteRefresh messages to be yielded."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)
        collect_updates(rib)

        # Trigger enhanced refresh
        rib.resend(enhanced_refresh=True)

        updates = list(rib.updates(grouped=False))

        # Should include RouteRefresh start and end
        refresh_messages = [u for u in updates if isinstance(u, RouteRefresh)]
        assert len(refresh_messages) == 2  # start and end

    def test_refresh_start_before_routes_before_end(self):
        """RouteRefresh start → routes → RouteRefresh end."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)
        collect_updates(rib)

        rib.resend(enhanced_refresh=True)

        updates = list(rib.updates(grouped=False))

        # Find positions
        start_idx = None
        end_idx = None
        route_idx = None

        for i, u in enumerate(updates):
            if isinstance(u, RouteRefresh):
                if u.reserved == RouteRefresh.start:
                    start_idx = i
                elif u.reserved == RouteRefresh.end:
                    end_idx = i
            elif isinstance(u, UpdateCollection) and u.announces:
                route_idx = i

        assert start_idx is not None
        assert end_idx is not None
        assert route_idx is not None
        assert start_idx < route_idx < end_idx


# ==============================================================================
# Test Edge Cases
# ==============================================================================


class TestUpdateGenerationEdgeCases:
    """Edge case tests for update generation."""

    def test_empty_rib_yields_nothing(self):
        """Empty RIB yields no updates."""
        rib = create_rib()

        updates = collect_updates(rib)

        assert len(updates) == 0

    def test_disabled_rib_yields_nothing(self):
        """Disabled RIB yields no updates even with pending routes."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        updates = collect_updates(rib)

        assert len(updates) == 0

    def test_updates_clears_pending(self):
        """Calling updates() clears pending state."""
        rib = create_rib()

        route = create_route('10.0.0.0/24')
        rib.add_to_rib(route)

        assert rib.pending()

        collect_updates(rib)

        assert not rib.pending()

    def test_updates_can_be_called_multiple_times(self):
        """updates() can be called repeatedly."""
        rib = create_rib()

        route1 = create_route('10.0.1.0/24')
        rib.add_to_rib(route1)
        updates1 = collect_updates(rib)

        route2 = create_route('10.0.2.0/24')
        rib.add_to_rib(route2)
        updates2 = collect_updates(rib)

        assert len(updates1) == 1
        assert len(updates2) == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
