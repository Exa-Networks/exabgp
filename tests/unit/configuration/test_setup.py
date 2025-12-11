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
