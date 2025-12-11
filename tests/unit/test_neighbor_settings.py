"""Tests for NeighborSettings dataclass and Neighbor.from_settings() (TDD)

These tests define the expected behavior of NeighborSettings and the
Neighbor.from_settings() factory method for programmatic Neighbor construction.

The Settings pattern enables deferred construction by collecting configuration
values first, then validating and creating the Neighbor in a single step.
"""

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


class TestNeighborSettings:
    """Test NeighborSettings dataclass"""

    def test_create_empty_settings(self) -> None:
        """Empty settings can be created with defaults"""
        from exabgp.bgp.neighbor.settings import NeighborSettings, SessionSettings

        settings = NeighborSettings()
        assert isinstance(settings.session, SessionSettings)
        assert settings.description == ''
        assert settings.hold_time == 180
        assert settings.rate_limit == 0
        assert settings.host_name == ''
        assert settings.domain_name == ''
        assert settings.group_updates is True
        assert settings.auto_flush is True
        assert settings.adj_rib_in is True
        assert settings.adj_rib_out is True
        assert settings.manual_eor is False
        assert settings.families == []
        assert settings.nexthops == []
        assert settings.addpaths == []
        assert settings.routes == []
        assert settings.api == {}

    def test_validate_session_error_propagates(self) -> None:
        """Validation error from session propagates"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        # Session is missing peer_address, local_as, peer_as

        error = settings.validate()
        assert error != ''
        assert 'peer-address' in error.lower() or 'session' in error.lower()

    def test_validate_hold_time_must_be_positive(self) -> None:
        """Validation returns error when hold_time is negative"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.hold_time = -1

        error = settings.validate()
        assert 'hold-time' in error.lower() or 'hold_time' in error.lower()

    def test_validate_hold_time_min_3_if_not_zero(self) -> None:
        """Validation returns error when hold_time is 1 or 2 (must be 0 or >= 3)"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.hold_time = 2

        error = settings.validate()
        assert 'hold-time' in error.lower() or 'hold_time' in error.lower()

    def test_validate_hold_time_zero_is_valid(self) -> None:
        """Hold time of 0 (disabled) is valid"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.hold_time = 0

        error = settings.validate()
        assert error == ''

    def test_validate_hold_time_max(self) -> None:
        """Validation returns error when hold_time exceeds 65535"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.hold_time = 65536

        error = settings.validate()
        assert 'hold-time' in error.lower() or 'hold_time' in error.lower()

    def test_validate_complete_settings(self) -> None:
        """Complete valid settings return empty string"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)

        error = settings.validate()
        assert error == ''

    def test_validate_with_families(self) -> None:
        """Settings with families validate correctly"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)]

        error = settings.validate()
        assert error == ''

    def test_validate_with_description(self) -> None:
        """Settings with description validate correctly"""
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.description = 'Test neighbor'

        error = settings.validate()
        assert error == ''


class TestNeighborFromSettings:
    """Test Neighbor.from_settings() factory method"""

    def test_from_settings_creates_valid_neighbor(self) -> None:
        """from_settings creates valid Neighbor from complete settings"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.session.peer_address == IP.from_string('192.168.1.1')
        assert neighbor.session.local_address == IP.from_string('192.168.1.2')
        assert neighbor.session.local_as == ASN(65000)
        assert neighbor.session.peer_as == ASN(65001)

    def test_from_settings_preserves_description(self) -> None:
        """from_settings preserves description"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.description = 'Test neighbor'

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.description == 'Test neighbor'

    def test_from_settings_preserves_hold_time(self) -> None:
        """from_settings preserves hold_time"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.hold_time = 90

        neighbor = Neighbor.from_settings(settings)

        assert int(neighbor.hold_time) == 90

    def test_from_settings_preserves_rate_limit(self) -> None:
        """from_settings preserves rate_limit"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.rate_limit = 100

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.rate_limit == 100

    def test_from_settings_preserves_host_domain_names(self) -> None:
        """from_settings preserves host_name and domain_name"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.host_name = 'router1'
        settings.domain_name = 'example.com'

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.host_name == 'router1'
        assert neighbor.domain_name == 'example.com'

    def test_from_settings_preserves_group_auto_flush(self) -> None:
        """from_settings preserves group_updates and auto_flush"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.group_updates = False
        settings.auto_flush = False

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.group_updates is False
        assert neighbor.auto_flush is False

    def test_from_settings_preserves_adj_rib_settings(self) -> None:
        """from_settings preserves adj_rib_in and adj_rib_out"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.adj_rib_in = False
        settings.adj_rib_out = False

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.adj_rib_in is False
        assert neighbor.adj_rib_out is False

    def test_from_settings_preserves_manual_eor(self) -> None:
        """from_settings preserves manual_eor"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.manual_eor = True

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.manual_eor is True

    def test_from_settings_with_families(self) -> None:
        """from_settings adds families correctly"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)]

        neighbor = Neighbor.from_settings(settings)

        families = neighbor.families()
        assert (AFI.ipv4, SAFI.unicast) in families
        assert (AFI.ipv6, SAFI.unicast) in families

    def test_from_settings_with_nexthops(self) -> None:
        """from_settings adds nexthops correctly"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.nexthops = [(AFI.ipv4, SAFI.unicast, AFI.ipv6)]

        neighbor = Neighbor.from_settings(settings)

        nexthops = neighbor.nexthops()
        assert (AFI.ipv4, SAFI.unicast, AFI.ipv6) in nexthops

    def test_from_settings_with_addpaths(self) -> None:
        """from_settings adds addpaths correctly"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.addpaths = [(AFI.ipv4, SAFI.unicast)]

        neighbor = Neighbor.from_settings(settings)

        addpaths = neighbor.addpaths()
        assert (AFI.ipv4, SAFI.unicast) in addpaths

    def test_from_settings_initializes_rib(self) -> None:
        """from_settings initializes RIB with families"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.families = [(AFI.ipv4, SAFI.unicast)]

        neighbor = Neighbor.from_settings(settings)

        # RIB should be enabled
        assert neighbor.rib.enabled is True

    def test_from_settings_calls_infer(self) -> None:
        """from_settings calls infer() to derive router_id"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)

        neighbor = Neighbor.from_settings(settings)

        # router_id should be derived from local_address
        assert neighbor.session.router_id is not None
        assert str(neighbor.session.router_id) == '192.168.1.2'

    def test_from_settings_preserves_api(self) -> None:
        """from_settings preserves api dict"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.api = {'send': ['updates'], 'receive': ['updates']}

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.api == {'send': ['updates'], 'receive': ['updates']}

    def test_from_settings_raises_on_invalid(self) -> None:
        """from_settings raises ValueError on incomplete settings"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        # Session missing peer_address, local_as, peer_as

        with pytest.raises(ValueError):
            Neighbor.from_settings(settings)

    def test_from_settings_raises_on_invalid_hold_time(self) -> None:
        """from_settings raises ValueError on invalid hold_time"""
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)
        settings.hold_time = 2  # Invalid: must be 0 or >= 3

        with pytest.raises(ValueError):
            Neighbor.from_settings(settings)

    def test_from_settings_with_capability(self) -> None:
        """from_settings preserves capability settings"""
        from exabgp.bgp.neighbor.capability import TriState
        from exabgp.bgp.neighbor.neighbor import Neighbor
        from exabgp.bgp.neighbor.settings import NeighborSettings

        settings = NeighborSettings()
        settings.session.peer_address = IP.from_string('192.168.1.1')
        settings.session.local_address = IP.from_string('192.168.1.2')
        settings.session.local_as = ASN(65000)
        settings.session.peer_as = ASN(65001)

        # Set custom capabilities
        settings.capability.asn4 = TriState.FALSE
        settings.capability.route_refresh = 2  # NORMAL

        neighbor = Neighbor.from_settings(settings)

        assert neighbor.capability.asn4 == TriState.FALSE
        assert neighbor.capability.route_refresh == 2
