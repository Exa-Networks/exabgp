"""Tests for configuration/setup.py - Helper functions for programmatic setup."""

import pytest

from exabgp.protocol.family import AFI, SAFI, Family


class TestParseFamily:
    """Tests for parse_family() helper."""

    def test_parse_single_family(self):
        """parse_family() should handle single family."""
        from exabgp.configuration.setup import parse_family

        result = parse_family('ipv4 unicast')
        assert len(result) == 1
        assert result[0] == (AFI.ipv4, SAFI.unicast)

    def test_parse_multiple_families(self):
        """parse_family() should handle multiple families."""
        from exabgp.configuration.setup import parse_family

        result = parse_family('ipv4 unicast ipv6 unicast')
        assert len(result) == 2
        assert (AFI.ipv4, SAFI.unicast) in result
        assert (AFI.ipv6, SAFI.unicast) in result

    def test_parse_family_all(self):
        """parse_family('all') should return all families."""
        from exabgp.configuration.setup import parse_family

        result = parse_family('all')
        assert len(result) == len(Family.size)
        assert (AFI.ipv4, SAFI.unicast) in result
        assert (AFI.ipv6, SAFI.unicast) in result
        assert (AFI.l2vpn, SAFI.evpn) in result

    def test_parse_family_case_insensitive(self):
        """parse_family() should be case insensitive."""
        from exabgp.configuration.setup import parse_family

        result = parse_family('IPv4 UNICAST')
        assert len(result) == 1
        assert result[0] == (AFI.ipv4, SAFI.unicast)

    def test_parse_family_invalid_odd_words(self):
        """parse_family() should reject odd number of words."""
        from exabgp.configuration.setup import parse_family

        with pytest.raises(ValueError, match='Invalid family format'):
            parse_family('ipv4')

    def test_parse_family_invalid_afi(self):
        """parse_family() should reject unknown AFI."""
        from exabgp.configuration.setup import parse_family

        with pytest.raises(ValueError, match='Unknown family'):
            parse_family('ipv5 unicast')

    def test_parse_family_invalid_safi(self):
        """parse_family() should reject unknown SAFI."""
        from exabgp.configuration.setup import parse_family

        with pytest.raises(ValueError, match='Unknown family'):
            parse_family('ipv4 unknown')

    def test_parse_family_evpn(self):
        """parse_family() should handle L2VPN EVPN."""
        from exabgp.configuration.setup import parse_family

        result = parse_family('l2vpn evpn')
        assert len(result) == 1
        assert result[0] == (AFI.l2vpn, SAFI.evpn)

    def test_parse_family_mpls_vpn(self):
        """parse_family() should handle MPLS-VPN families."""
        from exabgp.configuration.setup import parse_family

        result = parse_family('ipv4 mpls-vpn ipv6 mpls-vpn')
        assert len(result) == 2
        assert (AFI.ipv4, SAFI.mpls_vpn) in result
        assert (AFI.ipv6, SAFI.mpls_vpn) in result


class TestCreateMinimalConfiguration:
    """Tests for create_minimal_configuration() helper."""

    def test_create_default_configuration(self):
        """create_minimal_configuration() should create valid config with defaults."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration()
        assert config is not None
        assert len(config.neighbors) == 1

    def test_create_configuration_with_custom_as(self):
        """create_minimal_configuration() should accept custom AS numbers."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(local_as=65000, peer_as=65001)
        assert len(config.neighbors) == 1

        # Get the neighbor to verify settings
        neighbor = list(config.neighbors.values())[0]
        assert neighbor.session.local_as == 65000
        assert neighbor.session.peer_as == 65001

    def test_create_configuration_with_addresses(self):
        """create_minimal_configuration() should accept custom addresses."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(
            peer_address='192.168.1.1',
            local_address='192.168.1.2',
        )
        neighbor = list(config.neighbors.values())[0]
        assert str(neighbor.session.peer_address) == '192.168.1.1'
        assert str(neighbor.session.local_address) == '192.168.1.2'

    def test_create_configuration_with_families(self):
        """create_minimal_configuration() should configure address families."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(families='ipv4 unicast ipv6 unicast')
        neighbor = list(config.neighbors.values())[0]
        # families() is a method that returns list of (AFI, SAFI) tuples
        assert len(neighbor.families()) == 2

    def test_create_configuration_with_add_path(self):
        """create_minimal_configuration() should enable ADD-PATH when requested."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(add_path=True)
        neighbor = list(config.neighbors.values())[0]
        # addpaths() is a method that returns list of (AFI, SAFI) tuples
        assert len(neighbor.addpaths()) > 0

    def test_create_configuration_all_families(self):
        """create_minimal_configuration() should accept 'all' for families."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(families='all')
        neighbor = list(config.neighbors.values())[0]
        # families() is a method - should have all families
        assert len(neighbor.families()) == len(Family.size)


class TestAddRouteToConfig:
    """Tests for add_route_to_config() helper."""

    def test_add_route_basic(self):
        """add_route_to_config() should add route to neighbor RIB."""
        from exabgp.configuration.setup import create_minimal_configuration, add_route_to_config

        config = create_minimal_configuration(peer_address='127.0.1.1', families='ipv4 unicast')
        result = add_route_to_config(config, 'route 10.0.0.0/24 next-hop 1.2.3.4')

        assert result is True
        neighbor = list(config.neighbors.values())[0]
        routes = list(neighbor.rib.outgoing.cached_routes())
        assert len(routes) == 1
        assert '10.0.0.0/24' in str(routes[0])

    def test_add_route_preserves_neighbors(self):
        """add_route_to_config() should preserve neighbors."""
        from exabgp.configuration.setup import create_minimal_configuration, add_route_to_config

        config = create_minimal_configuration(peer_address='127.0.1.2', families='ipv4 unicast')
        neighbor_count_before = len(config.neighbors)

        add_route_to_config(config, 'route 10.0.0.0/24 next-hop 1.2.3.4')

        assert len(config.neighbors) == neighbor_count_before

    def test_add_route_invalid_syntax(self):
        """add_route_to_config() should return False for invalid route syntax."""
        from exabgp.configuration.setup import create_minimal_configuration, add_route_to_config

        config = create_minimal_configuration(peer_address='127.0.1.3', families='ipv4 unicast')
        result = add_route_to_config(config, 'invalid route syntax')

        assert result is False

    def test_add_multiple_routes(self):
        """add_route_to_config() should work for multiple route additions."""
        from exabgp.configuration.setup import create_minimal_configuration, add_route_to_config

        config = create_minimal_configuration(peer_address='127.0.1.4', families='ipv4 unicast')

        add_route_to_config(config, 'route 10.0.0.0/24 next-hop 1.2.3.4')
        add_route_to_config(config, 'route 10.0.1.0/24 next-hop 1.2.3.5')

        neighbor = list(config.neighbors.values())[0]
        routes = list(neighbor.rib.outgoing.cached_routes())
        assert len(routes) == 2


class TestCreateConfigurationWithRoutes:
    """Tests for create_configuration_with_routes() helper."""

    def test_create_with_route(self):
        """create_configuration_with_routes() should create config with route."""
        from exabgp.configuration.setup import create_configuration_with_routes

        config = create_configuration_with_routes(
            'route 10.0.0.0/24 next-hop 1.2.3.4',
            peer_address='127.0.2.1',
            families='ipv4 unicast',
        )

        assert len(config.neighbors) == 1
        neighbor = list(config.neighbors.values())[0]
        routes = list(neighbor.rib.outgoing.cached_routes())
        assert len(routes) == 1

    def test_create_with_route_custom_as(self):
        """create_configuration_with_routes() should accept custom AS."""
        from exabgp.configuration.setup import create_configuration_with_routes

        config = create_configuration_with_routes(
            'route 10.0.0.0/24 next-hop 1.2.3.4',
            peer_address='127.0.2.2',
            local_as=65000,
            peer_as=65001,
            families='ipv4 unicast',
        )

        neighbor = list(config.neighbors.values())[0]
        assert neighbor.session.local_as == 65000
        assert neighbor.session.peer_as == 65001

    def test_create_with_invalid_route_raises(self):
        """create_configuration_with_routes() should raise for invalid route."""
        from exabgp.configuration.setup import create_configuration_with_routes

        with pytest.raises(ValueError, match='Failed to parse route'):
            create_configuration_with_routes('invalid route', peer_address='127.0.2.3', families='ipv4 unicast')


class TestParseRouteText:
    """Tests for Configuration.parse_route_text() method."""

    def test_parse_route_text_basic(self):
        """parse_route_text() should parse route and preserve neighbors."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(peer_address='127.0.3.1', families='ipv4 unicast')
        neighbor_count_before = len(config.neighbors)

        routes = config.parse_route_text('route 10.0.0.0/24 next-hop 1.2.3.4')

        assert len(routes) == 1
        assert len(config.neighbors) == neighbor_count_before

    def test_parse_route_text_invalid(self):
        """parse_route_text() should return empty list for invalid syntax."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(peer_address='127.0.3.2', families='ipv4 unicast')
        routes = config.parse_route_text('invalid route')

        assert routes == []
        # Neighbors should still be preserved
        assert len(config.neighbors) == 1

    def test_parse_route_text_ipv6(self):
        """parse_route_text() should handle IPv6 routes."""
        from exabgp.configuration.setup import create_minimal_configuration

        config = create_minimal_configuration(peer_address='127.0.3.3', families='ipv6 unicast')
        routes = config.parse_route_text('route 2001:db8::/32 next-hop 2001:db8::1')

        assert len(routes) == 1
        assert '2001:db8::/32' in str(routes[0])
