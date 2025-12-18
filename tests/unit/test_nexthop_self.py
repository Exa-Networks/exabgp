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
        """NextHopSelf.resolved stays False - resolve() returns new NextHop."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert sentinel.resolved is False

        ip = IPv4.from_string('192.168.1.1')
        resolved = sentinel.resolve(ip)

        # Sentinel stays unresolved (immutable)
        assert sentinel.resolved is False
        assert sentinel._packed == b''
        # Returned NextHop is the resolved value
        assert isinstance(resolved, NextHop)
        assert resolved._packed == ip.pack_ip()

    def test_repr_before_resolution(self) -> None:
        """NextHopSelf.__repr__() returns 'self' before resolution."""
        sentinel = NextHopSelf(AFI.ipv4)
        assert repr(sentinel) == 'self'

    def test_repr_after_resolution(self) -> None:
        """resolve() returns NextHop with correct repr."""
        sentinel = NextHopSelf(AFI.ipv4)
        resolved = sentinel.resolve(IPv4.from_string('192.168.1.1'))
        # Sentinel stays 'self' (immutable)
        assert repr(sentinel) == 'self'
        # Returned NextHop has the resolved IP
        assert repr(resolved) == '192.168.1.1'

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

    def test_pack_attribute_works_on_resolved(self) -> None:
        """Returned NextHop from resolve() can be packed."""
        from unittest.mock import Mock

        sentinel = NextHopSelf(AFI.ipv4)
        resolved = sentinel.resolve(IPv4.from_string('192.168.1.1'))
        mock_negotiated = Mock()

        # Resolved NextHop should pack successfully
        result = resolved.pack_attribute(mock_negotiated)
        assert isinstance(result, bytes)

    def test_resolve_multiple_times_ok(self) -> None:
        """NextHopSelf.resolve() can be called multiple times (sentinel stays immutable)."""
        sentinel = NextHopSelf(AFI.ipv4)
        ip1 = IPv4.from_string('192.168.1.1')
        ip2 = IPv4.from_string('192.168.1.2')

        # Each call returns a new NextHop, sentinel unchanged
        resolved1 = sentinel.resolve(ip1)
        resolved2 = sentinel.resolve(ip2)

        assert repr(resolved1) == '192.168.1.1'
        assert repr(resolved2) == '192.168.1.2'
        assert repr(sentinel) == 'self'  # Sentinel unchanged


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
        """IPSelf.resolved stays False - resolve() returns concrete IP."""
        sentinel = IPSelf(AFI.ipv4)
        assert sentinel.resolved is False

        ip = IPv4.from_string('192.168.1.1')
        resolved = sentinel.resolve(ip)

        # Sentinel stays unresolved (immutable)
        assert sentinel.resolved is False
        assert sentinel._packed == b''
        # Returned IP is the resolved value
        assert resolved is ip

    def test_repr_before_resolution(self) -> None:
        """IPSelf.__repr__() returns 'self' before resolution."""
        sentinel = IPSelf(AFI.ipv4)
        assert repr(sentinel) == 'self'

    def test_repr_after_resolution(self) -> None:
        """resolve() returns concrete IP - sentinel stays 'self'."""
        sentinel = IPSelf(AFI.ipv4)
        resolved = sentinel.resolve(IPv4.from_string('192.168.1.1'))
        # Sentinel stays 'self' (immutable)
        assert repr(sentinel) == 'self'
        # Returned IP has the resolved value
        assert repr(resolved) == '192.168.1.1'

    def test_index_before_resolution(self) -> None:
        """IPSelf.index() includes AFI name before resolution."""
        sentinel = IPSelf(AFI.ipv4)
        assert sentinel.index() == b'self-ipv4'

        sentinel6 = IPSelf(AFI.ipv6)
        assert sentinel6.index() == b'self-ipv6'

    def test_index_after_resolution(self) -> None:
        """resolve() returns concrete IP with proper index - sentinel unchanged."""
        sentinel = IPSelf(AFI.ipv4)
        ip = IPv4.from_string('192.168.1.1')
        resolved = sentinel.resolve(ip)
        # Sentinel stays 'self-*' (immutable)
        assert sentinel.index() == b'self-ipv4'
        # Returned IP has packed bytes index
        assert resolved.index() == ip.pack_ip()

    def test_pack_ip_raises_before_resolution(self) -> None:
        """IPSelf.pack_ip() raises ValueError before resolve()."""
        sentinel = IPSelf(AFI.ipv4)
        with pytest.raises(ValueError, match='before resolve'):
            sentinel.pack_ip()

    def test_pack_ip_works_on_resolved(self) -> None:
        """Returned IP from resolve() can be packed."""
        sentinel = IPSelf(AFI.ipv4)
        ip = IPv4.from_string('192.168.1.1')
        resolved = sentinel.resolve(ip)
        # Resolved IP can be packed
        assert resolved.pack_ip() == ip.pack_ip()

    def test_resolve_multiple_times_ok(self) -> None:
        """IPSelf.resolve() can be called multiple times (sentinel stays immutable)."""
        sentinel = IPSelf(AFI.ipv4)
        ip1 = IPv4.from_string('192.168.1.1')
        ip2 = IPv4.from_string('192.168.1.2')

        # Each call returns the passed IP, sentinel unchanged
        resolved1 = sentinel.resolve(ip1)
        resolved2 = sentinel.resolve(ip2)

        assert resolved1 is ip1
        assert resolved2 is ip2
        assert repr(sentinel) == 'self'  # Sentinel unchanged


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

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
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

    cidr = CIDR.create_cidr(IP.pton(ip_str), mask)
    nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
    nh = IPv4.from_string(nexthop)
    # nexthop is stored in Route, not NLRI

    attrs = AttributeCollection()
    attrs[Attribute.CODE.NEXT_HOP] = NextHop.from_string(nexthop)

    return Route(nlri, attrs, nexthop=nh)


class TestNeighborResolveSelf:
    """Tests for Neighbor.resolve_self() in-place resolution."""

    def test_resolves_nexthop_self_in_route(self) -> None:
        """resolve_self() returns route with concrete IP nexthop (not IPSelf)."""
        neighbor = _create_neighbor(local_ip='192.168.1.1')
        route = _create_route_with_nexthop_self()

        # Verify sentinel before (nexthop is in Route, not NLRI)
        assert route.nexthop.SELF is True
        assert route.nexthop.resolved is False

        # Resolve
        resolved = neighbor.resolve_self(route)

        # Resolved route has concrete IP (not IPSelf) - SELF is False
        assert resolved.nexthop.SELF is False
        assert resolved.nexthop.resolved is True
        assert repr(resolved.nexthop) == '192.168.1.1'

    def test_resolves_nexthop_self_in_attributes(self) -> None:
        """resolve_self() returns route with concrete NextHop attribute (not NextHopSelf)."""
        neighbor = _create_neighbor(local_ip='192.168.1.1')
        route = _create_route_with_nexthop_self()

        resolved = neighbor.resolve_self(route)

        nh_attr = resolved.attributes.get(Attribute.CODE.NEXT_HOP)
        assert nh_attr is not None
        # Resolved route has concrete NextHop (not NextHopSelf) - SELF is False
        assert nh_attr.SELF is False
        assert repr(nh_attr) == '192.168.1.1'

    def test_returns_new_route_original_unchanged(self) -> None:
        """resolve_self() returns new Route, original sentinel unchanged."""
        neighbor = _create_neighbor()
        route = _create_route_with_nexthop_self()

        resolved = neighbor.resolve_self(route)

        # Original unchanged (nexthop sentinel stays unresolved)
        assert route.nexthop.resolved is False
        assert route.nexthop.SELF is True
        # Resolved is different Route object
        assert resolved is not route
        # NLRI can be shared (it's immutable)
        assert resolved.nlri is route.nlri

    def test_passthrough_if_not_self(self) -> None:
        """resolve_self() returns copy unchanged if nexthop is not SELF."""
        neighbor = _create_neighbor()
        route = _create_route_with_concrete_nexthop(nexthop='10.0.0.1')

        resolved = neighbor.resolve_self(route)

        # Should still be the same IP (copy, but same value)
        # nexthop is in Route, not NLRI
        assert resolved.nexthop == IPv4.from_string('10.0.0.1')

    def test_passthrough_if_already_resolved(self) -> None:
        """resolve_self() skips if nexthop not SELF (already concrete)."""
        neighbor = _create_neighbor(local_ip='192.168.1.1')
        route = _create_route_with_nexthop_self()

        # Resolve once - gets concrete IP back
        resolved1 = neighbor.resolve_self(route)
        assert resolved1.nexthop.SELF is False  # Now concrete IP
        assert resolved1.nexthop.resolved is True

        # Resolve again - passthrough because nexthop is not SELF
        resolved2 = neighbor.resolve_self(resolved1)
        assert resolved2 is resolved1  # Same route object returned


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
        # Resolved route has concrete IP (not IPSelf) - SELF is False
        assert resolved.nexthop.SELF is False
        assert resolved.nexthop.resolved is True
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
