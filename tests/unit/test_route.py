#!/usr/bin/env python3
"""
Comprehensive tests for the Route class.

Route is an immutable container for NLRI + Attributes + Nexthop.
It provides:
- Lazy index computation with caching
- Reference counting for shared storage
- Factory methods (with_nexthop, with_merged_attributes)
- Validation via feedback()
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

from exabgp.rib.route import Route  # noqa: E402
from exabgp.bgp.message import Action  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.attribute.origin import Origin  # noqa: E402
from exabgp.bgp.message.update.attribute.localpref import LocalPreference  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP, IPv4  # noqa: E402


# ==============================================================================
# Helper Functions
# ==============================================================================


def create_nlri(prefix: str = '10.0.0.0/24', afi: AFI = AFI.ipv4) -> INET:
    """Create an INET NLRI for testing."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else (32 if afi == AFI.ipv4 else 128)

    cidr = CIDR.make_cidr(IP.pton(ip_str), mask)
    return INET.from_cidr(cidr, afi, SAFI.unicast)


def create_attributes(origin: int = Origin.IGP) -> AttributeCollection:
    """Create AttributeCollection with specified origin."""
    attrs = AttributeCollection()
    attrs[Origin.ID] = Origin.from_int(origin)
    return attrs


def create_route(
    prefix: str = '10.0.0.0/24',
    afi: AFI = AFI.ipv4,
    nexthop: IP | None = None,
    origin: int = Origin.IGP,
) -> Route:
    """Create a Route for testing."""
    nlri = create_nlri(prefix, afi)
    attrs = create_attributes(origin)
    nh = nexthop if nexthop is not None else IP.NoNextHop
    return Route(nlri, attrs, nexthop=nh)


def create_concrete_nexthop() -> IPv4:
    """Create a concrete (non-sentinel) IPv4 nexthop."""
    return IPv4(IPv4.pton('192.168.1.1'))


# ==============================================================================
# Test Route.__init__
# ==============================================================================


class TestRouteInit:
    """Tests for Route initialization."""

    def test_init_with_all_parameters(self):
        """Route can be created with all parameters."""
        nlri = create_nlri('10.0.0.0/24')
        attrs = create_attributes()
        nexthop = create_concrete_nexthop()

        route = Route(nlri, attrs, nexthop=nexthop)

        assert route.nlri is nlri
        assert route.attributes is attrs
        assert route.nexthop is nexthop

    def test_init_with_default_nexthop(self):
        """Route uses IP.NoNextHop as default nexthop."""
        nlri = create_nlri()
        attrs = create_attributes()

        route = Route(nlri, attrs)

        assert route.nexthop is IP.NoNextHop

    def test_init_sets_zero_refcount(self):
        """Route initializes with zero reference count."""
        route = create_route()

        assert route._refcount == 0

    def test_init_defers_index_computation(self):
        """Route does not compute index at init time."""
        route = create_route()

        # Index is empty string until first .index() call
        assert route._Route__index == b''


# ==============================================================================
# Test Route.index()
# ==============================================================================


class TestRouteIndex:
    """Tests for Route.index() method."""

    def test_index_computed_lazily(self):
        """Index is computed on first call to index()."""
        route = create_route()

        # Before first call
        assert route._Route__index == b''

        # Call index()
        idx = route.index()

        # After first call - should be populated
        assert route._Route__index == idx
        assert len(idx) > 0

    def test_index_cached_after_first_call(self):
        """Index is cached and reused on subsequent calls."""
        route = create_route()

        idx1 = route.index()
        idx2 = route.index()

        assert idx1 is idx2  # Same object, not just equal

    def test_index_includes_family_prefix(self):
        """Index includes AFI/SAFI family prefix."""
        route = create_route('10.0.0.0/24', afi=AFI.ipv4)

        idx = route.index()

        # Family prefix is first 4 bytes (2 hex chars each for AFI and SAFI)
        family_prefix = Route.family_prefix((AFI.ipv4, SAFI.unicast))
        assert idx.startswith(family_prefix)

    def test_index_different_for_different_prefix(self):
        """Different prefixes produce different indexes."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.1.0/24')

        assert route1.index() != route2.index()

    def test_index_different_for_different_mask(self):
        """Same prefix with different mask produces different index."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.0.0/25')

        assert route1.index() != route2.index()

    def test_index_same_for_same_nlri(self):
        """Same NLRI produces same index even with different attributes."""
        attrs1 = create_attributes(Origin.IGP)
        attrs2 = create_attributes(Origin.EGP)
        nlri = create_nlri('10.0.0.0/24')

        route1 = Route(nlri, attrs1)
        route2 = Route(nlri, attrs2)

        # Index based on NLRI, not attributes
        assert route1.index() == route2.index()


# ==============================================================================
# Test Route.family_prefix()
# ==============================================================================


class TestRouteFamilyPrefix:
    """Tests for Route.family_prefix() static method."""

    def test_family_prefix_ipv4_unicast(self):
        """IPv4 unicast family prefix format."""
        prefix = Route.family_prefix((AFI.ipv4, SAFI.unicast))

        # AFI.ipv4 = 1, SAFI.unicast = 1 -> b'0101'
        assert prefix == b'0101'

    def test_family_prefix_ipv6_unicast(self):
        """IPv6 unicast family prefix format."""
        prefix = Route.family_prefix((AFI.ipv6, SAFI.unicast))

        # AFI.ipv6 = 2, SAFI.unicast = 1 -> b'0201'
        assert prefix == b'0201'

    def test_family_prefix_different_families_different_prefix(self):
        """Different families produce different prefixes."""
        ipv4_prefix = Route.family_prefix((AFI.ipv4, SAFI.unicast))
        ipv6_prefix = Route.family_prefix((AFI.ipv6, SAFI.unicast))

        assert ipv4_prefix != ipv6_prefix


# ==============================================================================
# Test Route.with_nexthop()
# ==============================================================================


class TestRouteWithNexthop:
    """Tests for Route.with_nexthop() factory method."""

    def test_with_nexthop_returns_new_instance(self):
        """with_nexthop() returns a new Route instance."""
        original = create_route()
        new_nh = create_concrete_nexthop()

        new_route = original.with_nexthop(new_nh)

        assert new_route is not original

    def test_with_nexthop_sets_new_nexthop(self):
        """with_nexthop() sets the specified nexthop."""
        original = create_route()
        new_nh = create_concrete_nexthop()

        new_route = original.with_nexthop(new_nh)

        assert new_route.nexthop is new_nh

    def test_with_nexthop_preserves_nlri(self):
        """with_nexthop() preserves the original NLRI."""
        original = create_route()
        new_nh = create_concrete_nexthop()

        new_route = original.with_nexthop(new_nh)

        assert new_route.nlri is original.nlri

    def test_with_nexthop_preserves_attributes(self):
        """with_nexthop() preserves the original attributes."""
        original = create_route()
        new_nh = create_concrete_nexthop()

        new_route = original.with_nexthop(new_nh)

        assert new_route.attributes is original.attributes

    def test_original_unchanged_after_with_nexthop(self):
        """Original route is unchanged after with_nexthop()."""
        original = create_route()
        original_nh = original.nexthop
        new_nh = create_concrete_nexthop()

        _ = original.with_nexthop(new_nh)

        assert original.nexthop is original_nh


# ==============================================================================
# Test Route.with_merged_attributes()
# ==============================================================================


class TestRouteWithMergedAttributes:
    """Tests for Route.with_merged_attributes() factory method."""

    def test_with_merged_attributes_returns_new_instance(self):
        """with_merged_attributes() returns a new Route instance."""
        original = create_route()
        extra = AttributeCollection()

        new_route = original.with_merged_attributes(extra)

        assert new_route is not original

    def test_extra_attributes_take_precedence_for_duplicates(self):
        """Extra attributes added first, so duplicates from extra win.

        Note: Despite docstring saying "Existing attributes take precedence",
        the actual implementation adds extra first, and add() ignores duplicates.
        So extra_attrs values win for overlapping attribute IDs.
        """
        # Original has IGP origin
        original = create_route(origin=Origin.IGP)

        # Extra has EGP origin
        extra = AttributeCollection()
        extra[Origin.ID] = Origin.from_int(Origin.EGP)

        new_route = original.with_merged_attributes(extra)

        # Extra's EGP wins (add() ignores duplicates, extra added first)
        assert new_route.attributes[Origin.ID].origin == Origin.EGP

    def test_extra_attributes_added(self):
        """Extra attributes not in original are added."""
        # Original has only origin
        original = create_route()

        # Extra has local preference (use from_int to create properly)
        extra = AttributeCollection()
        extra[LocalPreference.ID] = LocalPreference.from_int(100)

        new_route = original.with_merged_attributes(extra)

        # Should have both origin and local pref
        assert Origin.ID in new_route.attributes
        assert LocalPreference.ID in new_route.attributes
        assert new_route.attributes[LocalPreference.ID].localpref == 100

    def test_original_unchanged_after_merge(self):
        """Original route is unchanged after with_merged_attributes()."""
        original = create_route()
        original_attrs_count = len(original.attributes)

        extra = AttributeCollection()
        extra[LocalPreference.ID] = LocalPreference.from_int(100)

        _ = original.with_merged_attributes(extra)

        # Original should not have LocalPreference added
        assert len(original.attributes) == original_attrs_count
        assert LocalPreference.ID not in original.attributes

    def test_with_merged_preserves_nexthop(self):
        """with_merged_attributes() preserves nexthop."""
        nh = create_concrete_nexthop()
        original = create_route(nexthop=nh)
        extra = AttributeCollection()

        new_route = original.with_merged_attributes(extra)

        assert new_route.nexthop is nh


# ==============================================================================
# Test Route reference counting
# ==============================================================================


class TestRouteRefCount:
    """Tests for Route reference counting."""

    def test_ref_inc_increments(self):
        """ref_inc() increments the reference count."""
        route = create_route()

        assert route._refcount == 0
        route.ref_inc()
        assert route._refcount == 1
        route.ref_inc()
        assert route._refcount == 2

    def test_ref_dec_decrements(self):
        """ref_dec() decrements the reference count."""
        route = create_route()
        route._refcount = 2

        route.ref_dec()
        assert route._refcount == 1
        route.ref_dec()
        assert route._refcount == 0

    def test_ref_inc_returns_new_count(self):
        """ref_inc() returns the new reference count."""
        route = create_route()

        result = route.ref_inc()
        assert result == 1

        result = route.ref_inc()
        assert result == 2

    def test_ref_dec_returns_new_count(self):
        """ref_dec() returns the new reference count."""
        route = create_route()
        route._refcount = 2

        result = route.ref_dec()
        assert result == 1

        result = route.ref_dec()
        assert result == 0

    def test_ref_dec_can_go_negative(self):
        """ref_dec() can produce negative count (caller's responsibility)."""
        route = create_route()

        result = route.ref_dec()
        assert result == -1


# ==============================================================================
# Test Route equality
# ==============================================================================


class TestRouteEquality:
    """Tests for Route equality comparison."""

    def test_equal_routes(self):
        """Routes with same NLRI and attributes are equal."""
        nlri = create_nlri('10.0.0.0/24')
        attrs = create_attributes()

        route1 = Route(nlri, attrs)
        route2 = Route(nlri, attrs)

        assert route1 == route2

    def test_different_nlri_not_equal(self):
        """Routes with different NLRIs are not equal."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.1.0/24')

        assert route1 != route2

    def test_different_attributes_not_equal(self):
        """Routes with different attributes are not equal."""
        nlri = create_nlri('10.0.0.0/24')
        attrs1 = create_attributes(Origin.IGP)
        attrs2 = create_attributes(Origin.EGP)

        route1 = Route(nlri, attrs1)
        route2 = Route(nlri, attrs2)

        assert route1 != route2

    def test_same_nlri_different_nexthop_equal(self):
        """Routes with same NLRI/attrs but different nexthop ARE equal.

        Note: Nexthop is NOT part of Route equality - only NLRI and attributes.
        """
        nlri = create_nlri('10.0.0.0/24')
        attrs = create_attributes()
        nh1 = IP.NoNextHop
        nh2 = create_concrete_nexthop()

        route1 = Route(nlri, attrs, nexthop=nh1)
        route2 = Route(nlri, attrs, nexthop=nh2)

        assert route1 == route2

    def test_not_equal_to_non_route(self):
        """Route is not equal to non-Route objects."""
        route = create_route()

        assert route != 'not a route'
        assert route != 42
        assert route is not None
        assert route != {'nlri': 'something'}

    def test_ne_returns_true_for_different(self):
        """__ne__ returns True for different routes."""
        route1 = create_route('10.0.0.0/24')
        route2 = create_route('10.0.1.0/24')

        assert (route1 != route2) is True

    def test_ne_returns_false_for_equal(self):
        """__ne__ returns False for equal routes."""
        nlri = create_nlri()
        attrs = create_attributes()

        route1 = Route(nlri, attrs)
        route2 = Route(nlri, attrs)

        assert (route1 != route2) is False

    def test_ne_returns_true_for_non_route(self):
        """__ne__ returns True when comparing to non-Route."""
        route = create_route()

        assert (route != 'string') is True


# ==============================================================================
# Test Route ordering (should raise)
# ==============================================================================


class TestRouteOrdering:
    """Tests that Route ordering raises RuntimeError."""

    def test_lt_raises(self):
        """__lt__ raises RuntimeError."""
        route1 = create_route()
        route2 = create_route()

        with pytest.raises(RuntimeError, match='comparing Route for ordering'):
            _ = route1 < route2

    def test_le_raises(self):
        """__le__ raises RuntimeError."""
        route1 = create_route()
        route2 = create_route()

        with pytest.raises(RuntimeError, match='comparing Route for ordering'):
            _ = route1 <= route2

    def test_gt_raises(self):
        """__gt__ raises RuntimeError."""
        route1 = create_route()
        route2 = create_route()

        with pytest.raises(RuntimeError, match='comparing Route for ordering'):
            _ = route1 > route2

    def test_ge_raises(self):
        """__ge__ raises RuntimeError."""
        route1 = create_route()
        route2 = create_route()

        with pytest.raises(RuntimeError, match='comparing Route for ordering'):
            _ = route1 >= route2


# ==============================================================================
# Test Route.feedback()
# ==============================================================================


class TestRouteFeedback:
    """Tests for Route.feedback() validation method."""

    def test_feedback_requires_nexthop_for_announce(self):
        """Announce action requires nexthop."""
        route = create_route(nexthop=IP.NoNextHop)

        result = route.feedback(Action.ANNOUNCE)

        assert 'next-hop missing' in result

    def test_feedback_allows_no_nexthop_for_withdraw(self):
        """Withdraw action does not require nexthop."""
        route = create_route(nexthop=IP.NoNextHop)

        result = route.feedback(Action.WITHDRAW)

        # Should be empty or not about nexthop
        assert 'next-hop missing' not in result

    def test_feedback_returns_empty_when_valid_announce(self):
        """Valid announce returns empty string."""
        nh = create_concrete_nexthop()
        route = create_route(nexthop=nh)

        result = route.feedback(Action.ANNOUNCE)

        assert result == ''

    def test_feedback_returns_empty_when_valid_withdraw(self):
        """Valid withdraw returns empty string."""
        route = create_route()

        result = route.feedback(Action.WITHDRAW)

        assert result == ''


# ==============================================================================
# Test Route.extensive()
# ==============================================================================


class TestRouteExtensive:
    """Tests for Route.extensive() string representation."""

    def test_extensive_includes_nlri(self):
        """extensive() includes NLRI string."""
        route = create_route('10.0.0.0/24')

        result = route.extensive()

        assert '10.0.0.0/24' in result

    def test_extensive_includes_nexthop_when_present(self):
        """extensive() includes nexthop when not NoNextHop."""
        nh = create_concrete_nexthop()
        route = create_route(nexthop=nh)

        result = route.extensive()

        assert 'next-hop' in result
        assert '192.168.1.1' in result

    def test_extensive_excludes_nexthop_when_none(self):
        """extensive() excludes nexthop when NoNextHop."""
        route = create_route(nexthop=IP.NoNextHop)

        result = route.extensive()

        assert 'next-hop' not in result

    def test_repr_matches_extensive(self):
        """__repr__ returns same as extensive()."""
        route = create_route()

        assert repr(route) == route.extensive()


# ==============================================================================
# Test Route.nexthop property
# ==============================================================================


class TestRouteNexthop:
    """Tests for Route.nexthop property."""

    def test_nexthop_returns_stored_value(self):
        """nexthop property returns the stored nexthop."""
        nh = create_concrete_nexthop()
        route = create_route(nexthop=nh)

        assert route.nexthop is nh

    def test_nexthop_returns_no_nexthop_when_default(self):
        """nexthop property returns NoNextHop for default."""
        route = create_route()

        assert route.nexthop is IP.NoNextHop


# ==============================================================================
# Integration tests
# ==============================================================================


class TestRouteIntegration:
    """Integration tests for Route class."""

    def test_route_can_be_used_as_dict_key(self):
        """Route can be used as dictionary key (via index)."""
        route = create_route()

        # Using index as key (Route itself is not hashable)
        d = {route.index(): route}

        assert d[route.index()] is route

    def test_multiple_routes_same_nlri_different_attrs(self):
        """Multiple routes with same NLRI but different attrs."""
        nlri = create_nlri('10.0.0.0/24')
        attrs1 = create_attributes(Origin.IGP)
        attrs2 = create_attributes(Origin.EGP)

        route1 = Route(nlri, attrs1)
        route2 = Route(nlri, attrs2)

        # Same index (based on NLRI)
        assert route1.index() == route2.index()

        # But not equal (attributes differ)
        assert route1 != route2

    def test_ipv6_route(self):
        """Route works with IPv6 NLRI."""
        route = create_route('2001:db8::1/128', afi=AFI.ipv6)

        idx = route.index()

        # Should have IPv6 family prefix
        ipv6_prefix = Route.family_prefix((AFI.ipv6, SAFI.unicast))
        assert idx.startswith(ipv6_prefix)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
