"""Tests for ConfigurationSettings dataclass and Configuration.from_settings() (TDD)

These tests define the expected behavior of ConfigurationSettings and the
Configuration.from_settings() factory method for programmatic Configuration construction.

The Settings pattern enables deferred construction by collecting configuration
values first, then validating and creating the Configuration in a single step.
"""

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


class TestConfigurationSettings:
    """Test ConfigurationSettings dataclass"""

    def test_create_empty_settings(self) -> None:
        """Empty settings can be created with defaults"""
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()
        assert settings.neighbors == []
        assert settings.processes == {}

    def test_validate_empty_is_valid(self) -> None:
        """Empty configuration (no neighbors) is valid"""
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        error = settings.validate()
        assert error == ''

    def test_validate_neighbor_error_propagates(self) -> None:
        """Validation error from neighbor propagates with index"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()
        neighbor = NeighborSettings()
        # neighbor is missing peer_address, local_as, peer_as
        settings.neighbors.append(neighbor)

        error = settings.validate()
        assert error != ''
        assert 'neighbor[0]' in error

    def test_validate_multiple_neighbors_with_one_invalid(self) -> None:
        """Validation reports first invalid neighbor"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        # First neighbor is valid
        neighbor1 = NeighborSettings()
        neighbor1.session.peer_address = IP.from_string('192.168.1.1')
        neighbor1.session.local_address = IP.from_string('192.168.1.2')
        neighbor1.session.local_as = ASN(65000)
        neighbor1.session.peer_as = ASN(65001)
        settings.neighbors.append(neighbor1)

        # Second neighbor is invalid
        neighbor2 = NeighborSettings()
        # missing required fields
        settings.neighbors.append(neighbor2)

        error = settings.validate()
        assert error != ''
        assert 'neighbor[1]' in error

    def test_validate_all_valid_neighbors(self) -> None:
        """Validation passes when all neighbors are valid"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        # Add valid neighbor
        neighbor = NeighborSettings()
        neighbor.session.peer_address = IP.from_string('192.168.1.1')
        neighbor.session.local_address = IP.from_string('192.168.1.2')
        neighbor.session.local_as = ASN(65000)
        neighbor.session.peer_as = ASN(65001)
        settings.neighbors.append(neighbor)

        error = settings.validate()
        assert error == ''


class TestConfigurationFromSettings:
    """Test Configuration.from_settings() factory method"""

    def test_from_settings_creates_empty_configuration(self) -> None:
        """from_settings creates Configuration with no neighbors"""
        from exabgp.configuration.configuration import Configuration
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        config = Configuration.from_settings(settings)

        assert len(config.neighbors) == 0

    def test_from_settings_creates_configuration_with_neighbor(self) -> None:
        """from_settings creates Configuration with neighbor"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.configuration import Configuration
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        neighbor = NeighborSettings()
        neighbor.session.peer_address = IP.from_string('192.168.1.1')
        neighbor.session.local_address = IP.from_string('192.168.1.2')
        neighbor.session.local_as = ASN(65000)
        neighbor.session.peer_as = ASN(65001)
        settings.neighbors.append(neighbor)

        config = Configuration.from_settings(settings)

        assert len(config.neighbors) == 1

    def test_from_settings_creates_configuration_with_multiple_neighbors(self) -> None:
        """from_settings creates Configuration with multiple neighbors"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.configuration import Configuration
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        # Add first neighbor
        neighbor1 = NeighborSettings()
        neighbor1.session.peer_address = IP.from_string('192.168.1.1')
        neighbor1.session.local_address = IP.from_string('192.168.1.2')
        neighbor1.session.local_as = ASN(65000)
        neighbor1.session.peer_as = ASN(65001)
        settings.neighbors.append(neighbor1)

        # Add second neighbor
        neighbor2 = NeighborSettings()
        neighbor2.session.peer_address = IP.from_string('192.168.2.1')
        neighbor2.session.local_address = IP.from_string('192.168.2.2')
        neighbor2.session.local_as = ASN(65000)
        neighbor2.session.peer_as = ASN(65002)
        settings.neighbors.append(neighbor2)

        config = Configuration.from_settings(settings)

        assert len(config.neighbors) == 2

    def test_from_settings_preserves_neighbor_settings(self) -> None:
        """from_settings preserves neighbor configuration"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.configuration import Configuration
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        neighbor = NeighborSettings()
        neighbor.session.peer_address = IP.from_string('192.168.1.1')
        neighbor.session.local_address = IP.from_string('192.168.1.2')
        neighbor.session.local_as = ASN(65000)
        neighbor.session.peer_as = ASN(65001)
        neighbor.description = 'Test neighbor'
        neighbor.hold_time = 90
        neighbor.families = [(AFI.ipv4, SAFI.unicast)]
        settings.neighbors.append(neighbor)

        config = Configuration.from_settings(settings)

        # Get the neighbor from config
        neighbor_list = list(config.neighbors.values())
        assert len(neighbor_list) == 1
        n = neighbor_list[0]
        assert n.description == 'Test neighbor'
        assert int(n.hold_time) == 90
        assert (AFI.ipv4, SAFI.unicast) in n.families()

    def test_from_settings_preserves_processes(self) -> None:
        """from_settings preserves process configuration"""
        from exabgp.configuration.configuration import Configuration
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()
        settings.processes = {'my-process': {'run': ['python', 'script.py']}}

        config = Configuration.from_settings(settings)

        assert config.processes == {'my-process': {'run': ['python', 'script.py']}}

    def test_from_settings_raises_on_invalid_neighbor(self) -> None:
        """from_settings raises ValueError when neighbor is invalid"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.configuration import Configuration
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        neighbor = NeighborSettings()
        # Missing required fields
        settings.neighbors.append(neighbor)

        with pytest.raises(ValueError):
            Configuration.from_settings(settings)

    def test_from_settings_neighbor_name_used_as_key(self) -> None:
        """from_settings uses neighbor.name() as dict key"""
        from exabgp.bgp.neighbor.settings import NeighborSettings
        from exabgp.configuration.configuration import Configuration
        from exabgp.configuration.settings import ConfigurationSettings

        settings = ConfigurationSettings()

        neighbor = NeighborSettings()
        neighbor.session.peer_address = IP.from_string('192.168.1.1')
        neighbor.session.local_address = IP.from_string('192.168.1.2')
        neighbor.session.local_as = ASN(65000)
        neighbor.session.peer_as = ASN(65001)
        settings.neighbors.append(neighbor)

        config = Configuration.from_settings(settings)

        # Neighbor should be keyed by its name
        neighbor_names = list(config.neighbors.keys())
        assert len(neighbor_names) == 1
        # Name is typically like "neighbor-192.168.1.1-65001" format
        assert '192.168.1.1' in neighbor_names[0] or 'neighbor' in neighbor_names[0]
