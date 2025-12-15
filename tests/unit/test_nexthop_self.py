"""Tests for NextHopSelf sentinel pattern and resolution.

Tests cover:
- NextHopSelf and IPSelf sentinel classes
- neighbor.resolve_self() in-place resolution
- session.ip_self() AFI resolution paths
- RIB rejection of unresolved sentinels
"""

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.nexthop import NextHop, NextHopSelf
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.neighbor.neighbor import Neighbor
from exabgp.bgp.neighbor.session import Session
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPSelf, IPv4, IPv6
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route


class TestNextHopSelfSentinel:
    """Tests for NextHopSelf sentinel class."""

    def test_self_flag_is_true(self) -> None:
        """NextHopSelf.SELF is True (vs NextHop.SELF = False)."""
        assert NextHopSelf.SELF is True
        assert NextHop.SELF is False

    def test_stores_afi(self) -> None:
        """NextHopSelf stores AFI for resolution."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert sentinel.afi == AFI.ipv4

        sentinel6 = NextHopSelf(AFI.ipv6)
        assert sentinel6.afi == AFI.ipv6

    def test_packed_is_empty_before_resolution(self) -> None:
        """NextHopSelf._packed is empty before resolve()."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert sentinel._packed == b''
        assert sentinel.resolved is False

    def test_resolved_property(self) -> None:
        """NextHopSelf.resolved is False before and True after resolve()."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert sentinel.resolved is False

        ip = IPv4.from_string('192.168.1.1')
        sentinel.resolve(ip)

        assert sentinel.resolved is True
        assert sentinel._packed == ip.pack_ip()

    def test_repr_before_resolution(self) -> None:
        """NextHopSelf.__repr__() returns 'self' before resolution."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert repr(sentinel) == 'self'

    def test_repr_after_resolution(self) -> None:
        """NextHopSelf.__repr__() returns IP string after resolution."""
        sentinel = NextHopSelf(AFI.ipv4)
        sentinel.resolve(IPv4.from_string('192.168.1.1'))
        assert repr(sentinel) == '192.168.1.1'

    def test_bool_is_true(self) -> None:
        """NextHopSelf is truthy even before resolution."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert bool(sentinel) is True

    def test_ipv4_method(self) -> None:
        """NextHopSelf.ipv4() returns True for IPv4 AFI."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert sentinel.ipv4() is True
        assert sentinel.ipv6() is False

    def test_ipv6_method(self) -> None:
        """NextHopSelf.ipv6() returns True for IPv6 AFI."""
        sentinel = NextHopSelf(AFI.ipv6)
        assert sentinel.ipv4() is False
        assert sentinel.ipv6() is True

    def test_eq_raises(self) -> None:
        """NextHopSelf.__eq__() raises RuntimeError."""
        sentinel = NextHopSelf(AFI.ipv4)
        with pytest.raises(RuntimeError, match='do not use __eq__'):
            sentinel == sentinel

    def test_pack_attribute_raises_before_resolution(self) -> None:
        """NextHopSelf.pack_attribute() raises ValueError before resolve()."""
        from unittest.mock import Mock

        sentinel = NextHopSelf(AFI.ipv4)
        mock_negotiated = Mock()
        with pytest.raises(ValueError, match='before resolve'):
            sentinel.pack_attribute(mock_negotiated)

    def test_pack_attribute_works_after_resolution(self) -> None:
        """NextHopSelf.pack_attribute() works after resolve()."""
        from unittest.mock import Mock

        sentinel = NextHopSelf(AFI.ipv4)
        sentinel.resolve(IPv4.from_string('192.168.1.1'))
        mock_negotiated = Mock()

        # Should not raise
        result = sentinel.pack_attribute(mock_negotiated)
        assert isinstance(result, bytes)

    def test_resolve_twice_raises(self) -> None:
        """NextHopSelf.resolve() raises ValueError if already resolved."""
        sentinel = NextHopSelf(AFI.ipv4)
        ip = IPv4.from_string('192.168.1.1')
        sentinel.resolve(ip)

        with pytest.raises(ValueError, match='already resolved'):
            sentinel.resolve(ip)


class TestIPSelfSentinel:
    """Tests for IPSelf sentinel class."""

    def test_self_flag_is_true(self) -> None:
        """IPSelf.SELF is True (vs IP.SELF = False)."""
        assert IPSelf.SELF is True
        assert IP.SELF is False

    def test_stores_afi(self) -> None:
        """IPSelf stores AFI for resolution."""
        sentinel = IPSelf(AFI.ipv4)
        assert sentinel.afi == AFI.ipv4

    def test_resolved_property(self) -> None:
        """IPSelf.resolved is False before and True after resolve()."""
        sentinel = IPSelf(AFI.ipv4)
        assert sentinel.resolved is False

        ip = IPv4.from_string('192.168.1.1')
        sentinel.resolve(ip)

        assert sentinel.resolved is True
        assert sentinel._packed == ip.pack_ip()

    def test_repr_before_resolution(self) -> None:
        """IPSelf.__repr__() returns 'self' before resolution."""
        sentinel = IPSelf(AFI.ipv4)
        assert repr(sentinel) == 'self'

    def test_repr_after_resolution(self) -> None:
        """IPSelf.__repr__() returns IP string after resolution."""
        sentinel = IPSelf(AFI.ipv4)
        sentinel.resolve(IPv4.from_string('192.168.1.1'))
        assert repr(sentinel) == '192.168.1.1'

    def test_index_before_resolution(self) -> None:
        """IPSelf.index() includes AFI name before resolution."""
        sentinel = IPSelf(AFI.ipv4)
        assert sentinel.index() == b'self-ipv4'

        sentinel6 = IPSelf(AFI.ipv6)
        assert sentinel6.index() == b'self-ipv6'

    def test_index_after_resolution(self) -> None:
        """IPSelf.index() returns packed bytes after resolution."""
        sentinel = IPSelf(AFI.ipv4)
        ip = IPv4.from_string('192.168.1.1')
        sentinel.resolve(ip)
        assert sentinel.index() == ip.pack_ip()

    def test_pack_ip_raises_before_resolution(self) -> None:
        """IPSelf.pack_ip() raises ValueError before resolve()."""
        sentinel = IPSelf(AFI.ipv4)
        with pytest.raises(ValueError, match='before resolve'):
            sentinel.pack_ip()

    def test_pack_ip_works_after_resolution(self) -> None:
        """IPSelf.pack_ip() works after resolve()."""
        sentinel = IPSelf(AFI.ipv4)
        ip = IPv4.from_string('192.168.1.1')
        sentinel.resolve(ip)
        assert sentinel.pack_ip() == ip.pack_ip()

    def test_resolve_twice_raises(self) -> None:
        """IPSelf.resolve() raises ValueError if already resolved."""
        sentinel = IPSelf(AFI.ipv4)
        ip = IPv4.from_string('192.168.1.1')
        sentinel.resolve(ip)

        with pytest.raises(ValueError, match='already resolved'):
            sentinel.resolve(ip)


class TestSessionIpSelf:
    """Tests for Session.ip_self() resolution logic."""

    def test_ipv4_route_ipv4_session(self) -> None:
        """IPv4 route with IPv4 session returns local_address."""
        session = Session(
            peer_address=IPv4.from_string('192.168.1.2'),
            local_address=IPv4.from_string('192.168.1.1'),
        )
        result = session.ip_self(AFI.ipv4)
        assert result == IPv4.from_string('192.168.1.1')

    def test_ipv6_route_ipv6_session(self) -> None:
        """IPv6 route with IPv6 session returns local_address."""
        session = Session(
            peer_address=IPv6.from_string('2001:db8::2'),
            local_address=IPv6.from_string('2001:db8::1'),
        )
        result = session.ip_self(AFI.ipv6)
        assert result == IPv6.from_string('2001:db8::1')

    def test_ipv4_route_ipv6_session_uses_router_id(self) -> None:
        """IPv4 route with IPv6 session falls back to router_id."""
        session = Session(
            peer_address=IPv6.from_string('2001:db8::2'),
            local_address=IPv6.from_string('2001:db8::1'),
            router_id=RouterID('1.2.3.4'),
        )
        result = session.ip_self(AFI.ipv4)
        assert result == RouterID('1.2.3.4')

    def test_ipv6_route_ipv4_session_raises(self) -> None:
        """IPv6 route with IPv4 session raises TypeError."""
        session = Session(
            peer_address=IPv4.from_string('192.168.1.2'),
            local_address=IPv4.from_string('192.168.1.1'),
        )
        with pytest.raises(TypeError, match='next-hop self'):
            session.ip_self(AFI.ipv6)

    def test_ipv4_route_ipv6_session_no_router_id_raises(self) -> None:
        """IPv4 route with IPv6 session and no router_id raises TypeError."""
        session = Session(
            peer_address=IPv6.from_string('2001:db8::2'),
            local_address=IPv6.from_string('2001:db8::1'),
            # No router_id
        )
        with pytest.raises(TypeError, match='next-hop self'):
            session.ip_self(AFI.ipv4)


def _create_neighbor(local_ip: str = '192.168.1.1', peer_ip: str = '192.168.1.2') -> Neighbor:
    """Create a minimal Neighbor for testing."""
    neighbor = Neighbor()
    neighbor.session = Session(
        peer_address=IPv4.from_string(peer_ip),
        local_address=IPv4.from_string(local_ip),
        local_as=ASN(65000),
        peer_as=ASN(65001),
        router_id=RouterID(local_ip),
    )
    return neighbor


def _create_route_with_nexthop_self(prefix: str = '10.0.0.0/24') -> Route:
    """Create a route with NextHopSelf sentinel."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    cidr = CIDR.make_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
    nexthop = IPSelf(AFI.ipv4)
    # nexthop is stored in Route, not NLRI

    attrs = AttributeCollection()
    attrs[Attribute.CODE.NEXT_HOP] = NextHopSelf(AFI.ipv4)

    return Route(nlri, attrs, nexthop=nexthop)


def _create_route_with_concrete_nexthop(prefix: str = '10.0.0.0/24', nexthop: str = '192.168.1.1') -> Route:
    """Create a route with concrete nexthop."""
    parts = prefix.split('/')
    ip_str = parts[0]
    mask = int(parts[1]) if len(parts) > 1 else 32

    cidr = CIDR.make_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
    nh = IPv4.from_string(nexthop)
    # nexthop is stored in Route, not NLRI

    attrs = AttributeCollection()
    attrs[Attribute.CODE.NEXT_HOP] = NextHop.from_string(nexthop)

    return Route(nlri, attrs, nexthop=nh)


class TestNeighborResolveSelf:
    """Tests for Neighbor.resolve_self() in-place resolution."""

    def test_resolves_nexthop_self_in_route(self) -> None:
        """resolve_self() mutates IPSelf in-place in Route."""
        neighbor = _create_neighbor(local_ip='192.168.1.1')
        route = _create_route_with_nexthop_self()

        # Verify sentinel before (nexthop is in Route, not NLRI)
        assert route.nexthop.SELF is True
        assert route.nexthop.resolved is False

        # Resolve
        resolved = neighbor.resolve_self(route)

        # SELF stays True, but resolved becomes True
        assert resolved.nexthop.SELF is True
        assert resolved.nexthop.resolved is True
        assert repr(resolved.nexthop) == '192.168.1.1'

    def test_resolves_nexthop_self_in_attributes(self) -> None:
        """resolve_self() mutates NextHopSelf in-place in attributes."""
        neighbor = _create_neighbor(local_ip='192.168.1.1')
        route = _create_route_with_nexthop_self()

        resolved = neighbor.resolve_self(route)

        nh_attr = resolved.attributes.get(Attribute.CODE.NEXT_HOP)
        assert nh_attr is not None
        assert nh_attr.SELF is True
        assert nh_attr.resolved is True
        assert repr(nh_attr) == '192.168.1.1'

    def test_returns_copy_not_original(self) -> None:
        """resolve_self() returns a deep copy, not the original."""
        neighbor = _create_neighbor()
        route = _create_route_with_nexthop_self()

        resolved = neighbor.resolve_self(route)

        # Original unchanged (nexthop is in Route, not NLRI)
        assert route.nexthop.resolved is False
        # Resolved is different object
        assert resolved is not route
        assert resolved.nlri is not route.nlri

    def test_passthrough_if_not_self(self) -> None:
        """resolve_self() returns copy unchanged if nexthop is not SELF."""
        neighbor = _create_neighbor()
        route = _create_route_with_concrete_nexthop(nexthop='10.0.0.1')

        resolved = neighbor.resolve_self(route)

        # Should still be the same IP (copy, but same value)
        # nexthop is in Route, not NLRI
        assert resolved.nexthop == IPv4.from_string('10.0.0.1')

    def test_passthrough_if_already_resolved(self) -> None:
        """resolve_self() skips if nexthop already resolved."""
        neighbor = _create_neighbor(local_ip='192.168.1.1')
        route = _create_route_with_nexthop_self()

        # Resolve once (nexthop is in Route, not NLRI)
        resolved1 = neighbor.resolve_self(route)
        assert resolved1.nexthop.resolved is True

        # Resolve again - should not raise
        resolved2 = neighbor.resolve_self(resolved1)
        assert resolved2.nexthop.resolved is True


class TestRibRejectsUnresolvedNextHopSelf:
    """Tests that RIB rejects routes with unresolved NextHopSelf."""

    def test_add_to_rib_raises_on_unresolved_nexthop_self(self) -> None:
        """add_to_rib() raises RuntimeError if nexthop is SELF and not resolved."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
        route = _create_route_with_nexthop_self()

        with pytest.raises(RuntimeError, match='unresolved NextHopSelf'):
            rib.add_to_rib(route)

    def test_add_to_rib_accepts_concrete_nexthop(self) -> None:
        """add_to_rib() accepts routes with concrete nexthop."""
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
        route = _create_route_with_concrete_nexthop()

        # Should not raise
        rib.add_to_rib(route)

        assert rib.pending()

    def test_add_to_rib_accepts_resolved_nexthop_self(self) -> None:
        """add_to_rib() accepts routes with resolved NextHopSelf."""
        neighbor = _create_neighbor()
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

        route = _create_route_with_nexthop_self()
        resolved = neighbor.resolve_self(route)

        # Should not raise - resolved is True even though SELF is True
        rib.add_to_rib(resolved)

        assert rib.pending()


class TestNextHopSelfWorkflow:
    """Integration tests for the complete NextHopSelf workflow."""

    def test_config_to_rib_workflow(self) -> None:
        """Test complete workflow: sentinel creation → resolution → RIB entry."""
        # 1. Create route with sentinel (simulating config parsing)
        # nexthop is in Route, not NLRI
        route = _create_route_with_nexthop_self('10.0.0.0/24')
        assert route.nexthop.SELF is True
        assert route.nexthop.resolved is False

        # 2. Create neighbor (simulating neighbor block exit)
        neighbor = _create_neighbor(local_ip='192.168.1.100')

        # 3. Resolve sentinel (simulating config loading)
        resolved = neighbor.resolve_self(route)
        assert resolved.nexthop.SELF is True  # SELF stays True
        assert resolved.nexthop.resolved is True  # But now resolved
        assert repr(resolved.nexthop) == '192.168.1.100'

        # 4. Add to RIB (should succeed because resolved)
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
        rib.add_to_rib(resolved)

        # 5. Verify pending and generate update
        assert rib.pending()
        updates = list(rib.updates(grouped=False))
        assert len(updates) == 1
        assert len(updates[0].announces) == 1

    def test_unresolved_sentinel_rejected_at_rib(self) -> None:
        """Test that skipping resolution causes RIB to reject route."""
        # 1. Create route with sentinel
        route = _create_route_with_nexthop_self()

        # 2. Try to add directly to RIB (skipping resolve_self)
        rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})

        # 3. Should fail
        with pytest.raises(RuntimeError, match='unresolved NextHopSelf'):
            rib.add_to_rib(route)
