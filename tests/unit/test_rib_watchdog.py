#!/usr/bin/env python3
"""
Tests for RIB Watchdog functionality.

Watchdog allows grouping routes under a name that can be announced/withdrawn
together via commands. Routes are tracked in '+' (announced) and '-' (withdrawn)
dictionaries within the _watchdog structure.

Lifecycle:
1. add_to_rib_watchdog() - Add route with watchdog attribute
2. announce_watchdog() - Move routes from '-' to '+' and announce
3. withdraw_watchdog() - Move routes from '+' to '-' and withdraw
"""

import sys
import os
from typing import List
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
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.attribute.origin import Origin  # noqa: E402
from exabgp.bgp.message.update.attribute.attribute import Attribute  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402


# ==============================================================================
# Helper Classes and Functions
# ==============================================================================


class InternalWatchdog(str):
    """Internal watchdog attribute marker."""

    ID = Attribute.CODE.INTERNAL_WATCHDOG


class InternalWithdraw:
    """Internal withdraw attribute marker."""

    ID = Attribute.CODE.INTERNAL_WITHDRAW


def create_route(prefix: str, afi: AFI = AFI.ipv4) -> Route:
    """Create a Route without watchdog."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, afi, SAFI.unicast)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(Origin.IGP)

    return Route(nlri, attrs, nexthop=IP.NoNextHop)


def create_watchdog_route(prefix: str, watchdog_name: str, withdraw: bool = False) -> Route:
    """Create a Route with watchdog attribute.

    Args:
        prefix: IP prefix (e.g., '10.0.1.0/24')
        watchdog_name: Name of the watchdog group
        withdraw: If True, marks route for initial withdraw state
    """
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, afi=AFI.ipv4, safi=SAFI.unicast)
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(Origin.IGP)

    # Add watchdog internal attribute
    attrs[Attribute.CODE.INTERNAL_WATCHDOG] = InternalWatchdog(watchdog_name)

    if withdraw:
        attrs[Attribute.CODE.INTERNAL_WITHDRAW] = InternalWithdraw()

    return Route(nlri, attrs, nexthop=IP.NoNextHop)


def create_rib() -> OutgoingRIB:
    """Create a standard test RIB."""
    return OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})


def consume_updates(rib: OutgoingRIB) -> List:
    """Consume all pending updates from the RIB."""
    return list(rib.updates(grouped=False))


def count_announces_withdraws(updates: list) -> tuple[int, int]:
    """Count total announces and withdraws across all updates."""
    announces = sum(len(u.announces) for u in updates)
    withdraws = sum(len(u.withdraws) for u in updates)
    return announces, withdraws


# ==============================================================================
# Test add_to_rib_watchdog
# ==============================================================================


class TestAddToRibWatchdog:
    """Tests for add_to_rib_watchdog() method."""

    def test_add_to_rib_watchdog_with_withdraw_attribute(self):
        """Route with watchdog+withdraw goes to '-' dict."""
        rib = create_rib()

        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        result = rib.add_to_rib_watchdog(route)

        assert result is True
        assert 'dog1' in rib._watchdog
        assert route.index() in rib._watchdog['dog1'].get('-', {})
        assert route.index() not in rib._watchdog['dog1'].get('+', {})

        # Should NOT be pending (withdraw routes don't get added immediately)
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)
        assert announces == 0
        assert withdraws == 0

    def test_add_to_rib_watchdog_without_withdraw_attribute(self):
        """Route with watchdog (no withdraw) goes to '+' dict and RIB."""
        rib = create_rib()

        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=False)
        result = rib.add_to_rib_watchdog(route)

        assert result is True
        assert 'dog1' in rib._watchdog
        assert route.index() in rib._watchdog['dog1'].get('+', {})

        # Should be pending (non-withdraw routes get added to RIB)
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)
        assert announces == 1
        assert withdraws == 0

    def test_add_to_rib_watchdog_disabled_rib(self):
        """add_to_rib_watchdog returns False when RIB disabled."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        route = create_watchdog_route('10.0.1.0/24', 'dog1')
        result = rib.add_to_rib_watchdog(route)

        assert result is False

    def test_add_to_rib_watchdog_no_watchdog_attribute(self):
        """Route without watchdog is added to RIB normally."""
        rib = create_rib()

        route = create_route('10.0.1.0/24')
        result = rib.add_to_rib_watchdog(route)

        assert result is True
        assert len(rib._watchdog) == 0  # No watchdog entry

        updates = consume_updates(rib)
        announces, _ = count_announces_withdraws(updates)
        assert announces == 1


# ==============================================================================
# Test announce_watchdog
# ==============================================================================


class TestAnnounceWatchdog:
    """Tests for announce_watchdog() method."""

    def test_announce_watchdog_moves_from_minus_to_plus(self):
        """announce_watchdog() moves routes from '-' to '+'."""
        rib = create_rib()

        # Add route to '-' (withdraw state)
        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib.add_to_rib_watchdog(route)

        # Verify in '-'
        assert route.index() in rib._watchdog['dog1']['-']

        # Announce the watchdog
        rib.announce_watchdog('dog1')

        # Should move to '+'
        assert route.index() in rib._watchdog['dog1'].get('+', {})
        assert route.index() not in rib._watchdog['dog1'].get('-', {})

    def test_announce_watchdog_adds_route_to_rib(self):
        """announce_watchdog() adds route to RIB for announcement."""
        rib = create_rib()

        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib.add_to_rib_watchdog(route)

        # Initially nothing pending
        assert not rib.pending()

        rib.announce_watchdog('dog1')

        # Now route should be pending
        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)
        assert announces == 1
        assert withdraws == 0

    def test_announce_watchdog_nonexistent_name_is_noop(self):
        """announce_watchdog() with unknown name does nothing."""
        rib = create_rib()

        # No crash, no updates
        rib.announce_watchdog('nonexistent')

        assert not rib.pending()

    def test_announce_watchdog_empty_minus_dict_is_noop(self):
        """announce_watchdog() with empty '-' dict does nothing."""
        rib = create_rib()

        # Add route to '+' (already announced state)
        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=False)
        rib.add_to_rib_watchdog(route)
        consume_updates(rib)

        # No routes in '-', so announce should do nothing
        rib.announce_watchdog('dog1')

        assert not rib.pending()

    def test_announce_watchdog_multiple_routes(self):
        """announce_watchdog() announces all routes in watchdog group."""
        rib = create_rib()

        route1 = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        route2 = create_watchdog_route('10.0.2.0/24', 'dog1', withdraw=True)
        route3 = create_watchdog_route('10.0.3.0/24', 'dog1', withdraw=True)

        rib.add_to_rib_watchdog(route1)
        rib.add_to_rib_watchdog(route2)
        rib.add_to_rib_watchdog(route3)

        rib.announce_watchdog('dog1')

        updates = consume_updates(rib)
        announces, _ = count_announces_withdraws(updates)
        assert announces == 3

    def test_announce_watchdog_disabled_rib(self):
        """announce_watchdog() is no-op when RIB disabled."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        # Manually add to watchdog (can't use add_to_rib_watchdog on disabled RIB)
        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib._watchdog.setdefault('dog1', {}).setdefault('-', {})[route.index()] = route

        rib.announce_watchdog('dog1')

        # Route should still be in '-'
        assert route.index() in rib._watchdog['dog1']['-']


# ==============================================================================
# Test withdraw_watchdog
# ==============================================================================


class TestWithdrawWatchdog:
    """Tests for withdraw_watchdog() method."""

    def test_withdraw_watchdog_moves_from_plus_to_minus(self):
        """withdraw_watchdog() moves routes from '+' to '-'."""
        rib = create_rib()

        # Add route to '+' (announced state)
        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=False)
        rib.add_to_rib_watchdog(route)
        consume_updates(rib)

        # Verify in '+'
        assert route.index() in rib._watchdog['dog1']['+']

        # Withdraw the watchdog
        rib.withdraw_watchdog('dog1')

        # Should move to '-'
        assert route.index() in rib._watchdog['dog1'].get('-', {})
        assert route.index() not in rib._watchdog['dog1'].get('+', {})

    def test_withdraw_watchdog_calls_del_from_rib(self):
        """withdraw_watchdog() generates withdrawal for routes."""
        rib = create_rib()

        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=False)
        rib.add_to_rib_watchdog(route)
        consume_updates(rib)

        rib.withdraw_watchdog('dog1')

        updates = consume_updates(rib)
        announces, withdraws = count_announces_withdraws(updates)
        assert announces == 0
        assert withdraws == 1

    def test_withdraw_watchdog_nonexistent_name_is_noop(self):
        """withdraw_watchdog() with unknown name does nothing."""
        rib = create_rib()

        # No crash, no updates
        rib.withdraw_watchdog('nonexistent')

        assert not rib.pending()

    def test_withdraw_watchdog_empty_plus_dict_is_noop(self):
        """withdraw_watchdog() with empty '+' dict does nothing."""
        rib = create_rib()

        # Add route to '-' (not announced)
        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib.add_to_rib_watchdog(route)

        # No routes in '+', so withdraw should do nothing
        rib.withdraw_watchdog('dog1')

        assert not rib.pending()

    def test_withdraw_watchdog_multiple_routes(self):
        """withdraw_watchdog() withdraws all routes in group."""
        rib = create_rib()

        route1 = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=False)
        route2 = create_watchdog_route('10.0.2.0/24', 'dog1', withdraw=False)

        rib.add_to_rib_watchdog(route1)
        rib.add_to_rib_watchdog(route2)
        consume_updates(rib)

        rib.withdraw_watchdog('dog1')

        updates = consume_updates(rib)
        _, withdraws = count_announces_withdraws(updates)
        assert withdraws == 2

    def test_withdraw_watchdog_disabled_rib(self):
        """withdraw_watchdog() is no-op when RIB disabled."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)}, enabled=False)

        # Manually add to watchdog
        route = create_watchdog_route('10.0.1.0/24', 'dog1')
        rib._watchdog.setdefault('dog1', {}).setdefault('+', {})[route.index()] = route

        rib.withdraw_watchdog('dog1')

        # Route should still be in '+'
        assert route.index() in rib._watchdog['dog1']['+']


# ==============================================================================
# Test Watchdog Integration
# ==============================================================================


class TestWatchdogIntegration:
    """Integration tests for watchdog lifecycle."""

    def test_full_lifecycle_add_announce_withdraw(self):
        """Test complete watchdog lifecycle: add → announce → withdraw."""
        rib = create_rib()

        # 1. Add route with withdraw=True (starts in '-')
        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib.add_to_rib_watchdog(route)

        assert route.index() in rib._watchdog['dog1']['-']
        assert not rib.pending()

        # 2. Announce watchdog (moves to '+', adds to RIB)
        rib.announce_watchdog('dog1')

        assert route.index() in rib._watchdog['dog1']['+']
        assert route.index() not in rib._watchdog['dog1'].get('-', {})

        updates = consume_updates(rib)
        announces, _ = count_announces_withdraws(updates)
        assert announces == 1

        # 3. Withdraw watchdog (moves to '-', withdraws from RIB)
        rib.withdraw_watchdog('dog1')

        assert route.index() in rib._watchdog['dog1']['-']
        assert route.index() not in rib._watchdog['dog1'].get('+', {})

        updates = consume_updates(rib)
        _, withdraws = count_announces_withdraws(updates)
        assert withdraws == 1

    def test_multiple_watchdogs_independent(self):
        """Multiple watchdogs operate independently."""
        rib = create_rib()

        # Add routes to different watchdogs
        route1 = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        route2 = create_watchdog_route('10.0.2.0/24', 'dog2', withdraw=True)

        rib.add_to_rib_watchdog(route1)
        rib.add_to_rib_watchdog(route2)

        # Announce only dog1
        rib.announce_watchdog('dog1')

        # dog1 should be in '+', dog2 should still be in '-'
        assert route1.index() in rib._watchdog['dog1']['+']
        assert route2.index() in rib._watchdog['dog2']['-']

        updates = consume_updates(rib)
        announces, _ = count_announces_withdraws(updates)
        assert announces == 1

    def test_re_announce_after_withdraw(self):
        """Can re-announce watchdog after withdrawal."""
        rib = create_rib()

        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib.add_to_rib_watchdog(route)

        # Announce
        rib.announce_watchdog('dog1')
        consume_updates(rib)

        # Withdraw
        rib.withdraw_watchdog('dog1')
        consume_updates(rib)

        # Re-announce
        rib.announce_watchdog('dog1')

        updates = consume_updates(rib)
        announces, _ = count_announces_withdraws(updates)
        assert announces == 1

    def test_watchdog_survives_rib_reset(self):
        """Watchdog data survives RIB reset."""
        rib = create_rib()

        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib.add_to_rib_watchdog(route)

        # Reset RIB
        rib.reset()

        # Watchdog should still have the route
        assert 'dog1' in rib._watchdog
        assert route.index() in rib._watchdog['dog1']['-']

    def test_watchdog_cleared_on_rib_clear(self):
        """Watchdog is NOT cleared by RIB clear (clear only affects cache)."""
        rib = create_rib()

        route = create_watchdog_route('10.0.1.0/24', 'dog1', withdraw=True)
        rib.add_to_rib_watchdog(route)

        # Clear RIB
        rib.clear()

        # Watchdog is separate from cache, so it's preserved
        assert 'dog1' in rib._watchdog


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
