#!/usr/bin/env python3
"""
Tests for Route refcount and Configuration global route store.

The Route class has a _refcount slot for tracking references in the global store.
The _Configuration class has store_route/release_route/get_route methods for
memory-efficient route management.
"""

import sys
import os
from unittest.mock import Mock

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

from exabgp.rib.route import Route  # noqa: E402
from exabgp.bgp.message import Action  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402
from exabgp.configuration.configuration import _Configuration  # noqa: E402


def create_nlri(prefix: str = '10.0.0.0/24', action: int = Action.ANNOUNCE) -> INET:
    """Create an INET NLRI for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    cidr = CIDR.make_cidr(IP.pton(ip_str), mask)
    return INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, action)


def create_route(
    prefix: str = '10.0.0.0/24',
    nexthop: str = '1.2.3.4',
    action: int = Action.ANNOUNCE,
) -> Route:
    """Create a Route for testing."""
    nlri = create_nlri(prefix, action)
    attrs = AttributeCollection()
    nh = IP.from_string(nexthop) if nexthop else IP.NoNextHop
    return Route(nlri, attrs, action, nh)


class TestRouteRefcount:
    """Test Route._refcount slot and ref_inc/ref_dec methods."""

    def test_initial_refcount_is_zero(self):
        """Newly created route has _refcount = 0."""
        route = create_route()
        assert route._refcount == 0

    def test_ref_inc_increments(self):
        """ref_inc() increments refcount and returns new value."""
        route = create_route()

        result = route.ref_inc()
        assert result == 1
        assert route._refcount == 1

        result = route.ref_inc()
        assert result == 2
        assert route._refcount == 2

    def test_ref_dec_decrements(self):
        """ref_dec() decrements refcount and returns new value."""
        route = create_route()
        route._refcount = 3

        result = route.ref_dec()
        assert result == 2
        assert route._refcount == 2

        result = route.ref_dec()
        assert result == 1
        assert route._refcount == 1

    def test_ref_dec_can_go_negative(self):
        """ref_dec() can make refcount negative (caller responsibility)."""
        route = create_route()
        assert route._refcount == 0

        result = route.ref_dec()
        assert result == -1
        assert route._refcount == -1

    def test_with_action_preserves_zero_refcount(self):
        """with_action() creates new route with refcount = 0."""
        route = create_route()
        route._refcount = 5

        route2 = route.with_action(Action.WITHDRAW)
        assert route2._refcount == 0  # New route has fresh refcount
        assert route._refcount == 5  # Original unchanged

    def test_with_nexthop_preserves_zero_refcount(self):
        """with_nexthop() creates new route with refcount = 0."""
        route = create_route()
        route._refcount = 5

        route2 = route.with_nexthop(IP.from_string('9.9.9.9'))
        assert route2._refcount == 0  # New route has fresh refcount
        assert route._refcount == 5  # Original unchanged


class TestConfigurationRouteStore:
    """Test _Configuration global route store."""

    def test_store_route_adds_to_store(self):
        """store_route() adds route to _routes dict."""
        config = _Configuration()
        route = create_route()

        index = config.store_route(route)

        assert index == route.index()
        assert config._routes[index] is route

    def test_store_route_increments_refcount(self):
        """store_route() increments refcount to 1."""
        config = _Configuration()
        route = create_route()
        assert route._refcount == 0

        config.store_route(route)

        assert route._refcount == 1

    def test_store_same_route_twice_increments_refcount(self):
        """Storing same route twice increments existing refcount."""
        config = _Configuration()
        route = create_route()

        config.store_route(route)
        assert route._refcount == 1

        config.store_route(route)
        assert route._refcount == 2

        # Still only one entry in store
        assert len(config._routes) == 1

    def test_store_different_routes(self):
        """Storing different routes adds separate entries."""
        config = _Configuration()
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.1.0/24')

        config.store_route(route1)
        config.store_route(route2)

        assert len(config._routes) == 2
        assert route1._refcount == 1
        assert route2._refcount == 1

    def test_get_route_returns_stored_route(self):
        """get_route() returns route by index."""
        config = _Configuration()
        route = create_route()
        index = config.store_route(route)

        result = config.get_route(index)

        assert result is route

    def test_get_route_returns_none_for_unknown_index(self):
        """get_route() returns None for unknown index."""
        config = _Configuration()

        result = config.get_route(b'nonexistent')

        assert result is None

    def test_release_route_decrements_refcount(self):
        """release_route() decrements refcount."""
        config = _Configuration()
        route = create_route()
        index = config.store_route(route)
        config.store_route(route)  # refcount = 2
        assert route._refcount == 2

        result = config.release_route(index)

        assert result is True
        assert route._refcount == 1
        assert index in config._routes  # Still in store

    def test_release_route_removes_when_refcount_zero(self):
        """release_route() removes route when refcount reaches 0."""
        config = _Configuration()
        route = create_route()
        index = config.store_route(route)
        assert route._refcount == 1

        result = config.release_route(index)

        assert result is True
        assert route._refcount == 0
        assert index not in config._routes  # Removed from store

    def test_release_unknown_route_returns_false(self):
        """release_route() returns False for unknown index."""
        config = _Configuration()

        result = config.release_route(b'nonexistent')

        assert result is False

    def test_multiple_neighbors_share_route(self):
        """Routes can be shared across multiple neighbors via refcount."""
        config = _Configuration()
        route = create_route()

        # Simulate 3 neighbors referencing the same route
        index = config.store_route(route)
        config.store_route(route)
        config.store_route(route)

        assert route._refcount == 3
        assert len(config._routes) == 1

        # First two neighbors release
        config.release_route(index)
        assert route._refcount == 2
        assert index in config._routes

        config.release_route(index)
        assert route._refcount == 1
        assert index in config._routes

        # Last neighbor releases - route removed
        config.release_route(index)
        assert route._refcount == 0
        assert index not in config._routes


class TestRouteIndex:
    """Test Route.index() with refcount."""

    def test_index_computed_once(self):
        """Route.index() is computed lazily and cached."""
        route = create_route()

        # First call computes index
        index1 = route.index()
        # Second call returns cached value
        index2 = route.index()

        assert index1 == index2
        assert isinstance(index1, bytes)

    def test_same_nlri_same_index(self):
        """Routes with same NLRI have same index."""
        route1 = create_route('10.0.0.0/24', '1.2.3.4')
        route2 = create_route('10.0.0.0/24', '5.6.7.8')  # Different nexthop

        assert route1.index() == route2.index()

    def test_different_nlri_different_index(self):
        """Routes with different NLRI have different index."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.1.0/24')

        assert route1.index() != route2.index()


class TestConfigurationIndexedMethods:
    """Test _Configuration inject_route_indexed and withdraw_route_by_index."""

    def test_inject_route_indexed_returns_index_and_success(self):
        """inject_route_indexed returns (index, False) when no neighbors."""
        config = _Configuration()
        route = create_route()

        index, success = config.inject_route_indexed(['peer1'], route)

        assert index == route.index()
        assert success is False  # No neighbors configured
        assert config._routes[index] is route

    def test_inject_route_indexed_stores_in_global(self):
        """inject_route_indexed stores route in global store."""
        config = _Configuration()
        route = create_route()

        index, _ = config.inject_route_indexed(['peer1'], route)

        # Route is in global store
        assert config.get_route(index) is route
        assert route._refcount == 1

    def test_withdraw_route_by_index_not_found(self):
        """withdraw_route_by_index returns False for unknown index."""
        config = _Configuration()

        result = config.withdraw_route_by_index(['peer1'], b'nonexistent')

        assert result is False

    def test_withdraw_route_by_index_no_neighbors(self):
        """withdraw_route_by_index returns False when no matching neighbors."""
        config = _Configuration()
        route = create_route()
        index, _ = config.inject_route_indexed(['peer1'], route)

        result = config.withdraw_route_by_index(['peer1'], index)

        assert result is False  # No neighbors configured
        # Route still in store (not released because no withdrawal happened)
        assert config.get_route(index) is route
