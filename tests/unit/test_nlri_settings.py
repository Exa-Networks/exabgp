"""Tests for NLRI Settings dataclasses (TDD - tests written before implementation)

These tests define the expected behavior of Settings classes that will be used
for deferred NLRI construction. Settings collect configuration values during
parsing and validate before creating the final NLRI object.

The Settings pattern enables immutable NLRI by collecting all values first,
then creating the NLRI in a single construction step.
"""

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import Labels, RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


class TestVPLSSettings:
    """Test VPLSSettings dataclass"""

    def test_create_empty_settings(self) -> None:
        """Empty settings can be created with defaults"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        settings = VPLSSettings()
        assert settings.rd is None
        assert settings.endpoint is None
        assert settings.base is None
        assert settings.offset is None
        assert settings.size is None
        assert settings.action == Action.ANNOUNCE
        assert settings.nexthop is IP.NoNextHop

    def test_validate_missing_rd(self) -> None:
        """Validation returns error when rd is missing"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        settings = VPLSSettings()
        settings.endpoint = 100
        settings.base = 500000
        settings.offset = 50
        settings.size = 16

        error = settings.validate()
        assert 'route-distinguisher' in error.lower() or 'rd' in error.lower()

    def test_validate_missing_endpoint(self) -> None:
        """Validation returns error when endpoint is missing"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.base = 500000
        settings.offset = 50
        settings.size = 16

        error = settings.validate()
        assert 'endpoint' in error.lower()

    def test_validate_missing_base(self) -> None:
        """Validation returns error when base is missing"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.offset = 50
        settings.size = 16

        error = settings.validate()
        assert 'base' in error.lower()

    def test_validate_missing_offset(self) -> None:
        """Validation returns error when offset is missing"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 500000
        settings.size = 16

        error = settings.validate()
        assert 'offset' in error.lower()

    def test_validate_missing_size(self) -> None:
        """Validation returns error when size is missing"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 500000
        settings.offset = 50

        error = settings.validate()
        assert 'size' in error.lower()

    def test_validate_complete_settings(self) -> None:
        """Complete valid settings return empty string"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 500000
        settings.offset = 50
        settings.size = 16

        error = settings.validate()
        assert error == ''

    def test_validate_size_inconsistency(self) -> None:
        """Validation returns error when base + size > 20-bit max"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 0xFFFFF  # Maximum 20-bit value
        settings.offset = 50
        settings.size = 1  # base + size would exceed max

        error = settings.validate()
        assert 'size' in error.lower() or 'inconsisten' in error.lower()

    def test_set_method_assigns_value(self) -> None:
        """set() method assigns values by name"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()

        settings.set('rd', rd)
        settings.set('endpoint', 100)
        settings.set('base', 500000)
        settings.set('offset', 50)
        settings.set('size', 16)

        assert settings.rd == rd
        assert settings.endpoint == 100
        assert settings.base == 500000
        assert settings.offset == 50
        assert settings.size == 16

    def test_set_endpoint_validation(self) -> None:
        """set() validates endpoint is in range 0-65535"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        settings = VPLSSettings()

        # Valid values
        settings.set('endpoint', 0)
        assert settings.endpoint == 0
        settings.set('endpoint', 65535)
        assert settings.endpoint == 65535

        # Invalid value
        with pytest.raises(ValueError):
            settings.set('endpoint', 65536)

    def test_set_base_validation(self) -> None:
        """set() validates base is in range 0-0xFFFFF"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        settings = VPLSSettings()

        # Valid values
        settings.set('base', 0)
        assert settings.base == 0
        settings.set('base', 0xFFFFF)
        assert settings.base == 0xFFFFF

        # Invalid value
        with pytest.raises(ValueError):
            settings.set('base', 0x100000)

    def test_action_default(self) -> None:
        """Default action is ANNOUNCE"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        settings = VPLSSettings()
        assert settings.action == Action.ANNOUNCE

    def test_action_withdraw(self) -> None:
        """Action can be set to WITHDRAW"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings

        settings = VPLSSettings()
        settings.action = Action.WITHDRAW
        assert settings.action == Action.WITHDRAW


class TestVPLSFromSettings:
    """Test VPLS.from_settings() factory method"""

    def test_from_settings_creates_valid_vpls(self) -> None:
        """from_settings creates valid VPLS from complete settings"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings
        from exabgp.bgp.message.update.nlri.vpls import VPLS

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 500000
        settings.offset = 50
        settings.size = 16

        vpls = VPLS.from_settings(settings)

        assert vpls.endpoint == 100
        assert vpls.base == 500000
        assert vpls.offset == 50
        assert vpls.size == 16
        assert vpls.rd is not None

    def test_from_settings_preserves_action(self) -> None:
        """from_settings preserves action from settings"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings
        from exabgp.bgp.message.update.nlri.vpls import VPLS

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 500000
        settings.offset = 50
        settings.size = 16
        settings.action = Action.WITHDRAW

        vpls = VPLS.from_settings(settings)

        assert vpls.action == Action.WITHDRAW

    def test_from_settings_preserves_nexthop(self) -> None:
        """from_settings preserves nexthop from settings"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings
        from exabgp.bgp.message.update.nlri.vpls import VPLS

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        nexthop = IP.from_string('192.168.1.1')

        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 500000
        settings.offset = 50
        settings.size = 16
        settings.nexthop = nexthop

        vpls = VPLS.from_settings(settings)

        assert vpls.nexthop == nexthop

    def test_from_settings_raises_on_invalid(self) -> None:
        """from_settings raises ValueError on incomplete settings"""
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings
        from exabgp.bgp.message.update.nlri.vpls import VPLS

        settings = VPLSSettings()
        settings.endpoint = 100  # Missing rd, base, offset, size

        with pytest.raises(ValueError):
            VPLS.from_settings(settings)

    def test_from_settings_pack_unpack_roundtrip(self) -> None:
        """VPLS from from_settings can be packed and unpacked"""
        from unittest.mock import Mock

        from exabgp.bgp.message.action import Action
        from exabgp.bgp.message.open.capability.negotiated import Negotiated
        from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
        from exabgp.bgp.message.update.nlri.settings import VPLSSettings
        from exabgp.bgp.message.update.nlri.vpls import VPLS
        from exabgp.protocol.family import AFI, SAFI
        from exabgp.bgp.message.direction import Direction

        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = VPLSSettings()
        settings.rd = rd
        settings.endpoint = 100
        settings.base = 500000
        settings.offset = 50
        settings.size = 16

        vpls = VPLS.from_settings(settings)

        # Create minimal negotiated using Mock (standard pattern)
        neighbor = Mock()
        neighbor.__getitem__ = Mock(return_value={'aigp': False})
        negotiated = Negotiated(neighbor, Direction.OUT)

        packed = vpls.pack_nlri(negotiated)
        assert len(packed) == 19  # VPLS wire format length

        # Unpack
        unpacked, remaining = VPLS.unpack_nlri(
            AFI.l2vpn,
            SAFI.vpls,
            packed,
            Action.ANNOUNCE,
            PathInfo.DISABLED,
            negotiated,
        )

        assert unpacked.endpoint == vpls.endpoint
        assert unpacked.base == vpls.base
        assert unpacked.offset == vpls.offset
        assert unpacked.size == vpls.size
        assert len(remaining) == 0


class TestINETSettings:
    """Test INETSettings dataclass"""

    def test_create_empty_settings(self) -> None:
        """Empty settings can be created with defaults"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        settings = INETSettings()
        assert settings.cidr is None
        assert settings.afi is None
        assert settings.safi is None
        assert settings.action == Action.ANNOUNCE
        assert settings.nexthop is IP.NoNextHop
        assert settings.path_info is PathInfo.DISABLED
        assert settings.labels is None
        assert settings.rd is None

    def test_validate_missing_cidr(self) -> None:
        """Validation returns error when cidr is missing"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        settings = INETSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.unicast

        error = settings.validate()
        assert 'cidr' in error.lower() or 'prefix' in error.lower()

    def test_validate_missing_afi(self) -> None:
        """Validation returns error when afi is missing"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.safi = SAFI.unicast

        error = settings.validate()
        assert 'afi' in error.lower()

    def test_validate_missing_safi(self) -> None:
        """Validation returns error when safi is missing"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4

        error = settings.validate()
        assert 'safi' in error.lower()

    def test_validate_complete_settings(self) -> None:
        """Complete valid settings return empty string"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.unicast

        error = settings.validate()
        assert error == ''

    def test_validate_with_labels(self) -> None:
        """Settings with labels validate correctly"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.nlri_mpls
        settings.labels = Labels.make_labels([100000])

        error = settings.validate()
        assert error == ''

    def test_validate_with_rd(self) -> None:
        """Settings with RD validate correctly"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.mpls_vpn
        settings.labels = Labels.make_labels([100000])
        settings.rd = rd

        error = settings.validate()
        assert error == ''

    def test_set_method_assigns_value(self) -> None:
        """set() method assigns values by name"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()

        settings.set('cidr', cidr)
        settings.set('afi', AFI.ipv4)
        settings.set('safi', SAFI.unicast)

        assert settings.cidr == cidr
        assert settings.afi == AFI.ipv4
        assert settings.safi == SAFI.unicast

    def test_action_default(self) -> None:
        """Default action is ANNOUNCE"""
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        settings = INETSettings()
        assert settings.action == Action.ANNOUNCE


class TestINETFromSettings:
    """Test INET.from_settings() factory method"""

    def test_from_settings_creates_valid_inet(self) -> None:
        """from_settings creates valid INET from complete settings"""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.unicast

        inet = INET.from_settings(settings)

        assert inet.afi == AFI.ipv4
        assert inet.safi == SAFI.unicast
        assert inet.cidr.mask == 24

    def test_from_settings_preserves_action(self) -> None:
        """from_settings preserves action from settings"""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.unicast
        settings.action = Action.WITHDRAW

        inet = INET.from_settings(settings)

        assert inet.action == Action.WITHDRAW

    def test_from_settings_preserves_nexthop(self) -> None:
        """from_settings preserves nexthop from settings"""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nexthop = IP.from_string('192.168.1.1')

        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.unicast
        settings.nexthop = nexthop

        inet = INET.from_settings(settings)

        assert inet.nexthop == nexthop

    def test_from_settings_preserves_path_info(self) -> None:
        """from_settings preserves path_info from settings"""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        path_info = PathInfo.make_from_integer(12345)

        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.unicast
        settings.path_info = path_info

        inet = INET.from_settings(settings)

        assert inet.path_info == path_info

    def test_from_settings_raises_on_invalid(self) -> None:
        """from_settings raises ValueError on incomplete settings"""
        from exabgp.bgp.message.update.nlri.inet import INET
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        settings = INETSettings()
        settings.afi = AFI.ipv4  # Missing cidr and safi

        with pytest.raises(ValueError):
            INET.from_settings(settings)


class TestLabelFromSettings:
    """Test Label.from_settings() factory method"""

    def test_from_settings_creates_valid_label(self) -> None:
        """from_settings creates valid Label from complete settings with labels"""
        from exabgp.bgp.message.update.nlri.label import Label
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.nlri_mpls
        settings.labels = Labels.make_labels([100000])

        label = Label.from_settings(settings)

        assert label.afi == AFI.ipv4
        assert label.safi == SAFI.nlri_mpls
        assert label.cidr.mask == 24
        # Verify labels are actually set (not just Labels.NOLABEL)
        assert label._labels_packed == Labels.make_labels([100000]).pack_labels()

    def test_from_settings_preserves_action(self) -> None:
        """from_settings preserves action from settings"""
        from exabgp.bgp.message.update.nlri.label import Label
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.nlri_mpls
        settings.labels = Labels.make_labels([100000])
        settings.action = Action.WITHDRAW

        label = Label.from_settings(settings)

        assert label.action == Action.WITHDRAW

    def test_from_settings_preserves_nexthop(self) -> None:
        """from_settings preserves nexthop from settings"""
        from exabgp.bgp.message.update.nlri.label import Label
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        nexthop = IP.from_string('192.168.1.1')

        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.nlri_mpls
        settings.labels = Labels.make_labels([100000])
        settings.nexthop = nexthop

        label = Label.from_settings(settings)

        assert label.nexthop == nexthop

    def test_from_settings_raises_on_invalid(self) -> None:
        """from_settings raises ValueError on incomplete settings"""
        from exabgp.bgp.message.update.nlri.label import Label
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        settings = INETSettings()
        settings.afi = AFI.ipv4  # Missing cidr, safi, labels

        with pytest.raises(ValueError):
            Label.from_settings(settings)


class TestIPVPNFromSettings:
    """Test IPVPN.from_settings() factory method"""

    def test_from_settings_creates_valid_ipvpn(self) -> None:
        """from_settings creates valid IPVPN from complete settings with rd and labels"""
        from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.mpls_vpn
        settings.labels = Labels.make_labels([100000])
        settings.rd = rd

        ipvpn = IPVPN.from_settings(settings)

        assert ipvpn.afi == AFI.ipv4
        assert ipvpn.safi == SAFI.mpls_vpn
        assert ipvpn.cidr.mask == 24
        # Verify labels are actually set (not just Labels.NOLABEL)
        assert ipvpn._labels_packed == Labels.make_labels([100000]).pack_labels()
        # Verify rd is actually set
        assert ipvpn.rd is not None
        assert ipvpn.rd._str() == rd._str()

    def test_from_settings_preserves_action(self) -> None:
        """from_settings preserves action from settings"""
        from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.mpls_vpn
        settings.labels = Labels.make_labels([100000])
        settings.rd = rd
        settings.action = Action.WITHDRAW

        ipvpn = IPVPN.from_settings(settings)

        assert ipvpn.action == Action.WITHDRAW

    def test_from_settings_preserves_nexthop(self) -> None:
        """from_settings preserves nexthop from settings"""
        from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        cidr = CIDR.make_cidr(IP.pton('10.0.0.0'), 24)
        rd = RouteDistinguisher.make_from_elements('10.0.0.1', 100)
        nexthop = IP.from_string('192.168.1.1')

        settings = INETSettings()
        settings.cidr = cidr
        settings.afi = AFI.ipv4
        settings.safi = SAFI.mpls_vpn
        settings.labels = Labels.make_labels([100000])
        settings.rd = rd
        settings.nexthop = nexthop

        ipvpn = IPVPN.from_settings(settings)

        assert ipvpn.nexthop == nexthop

    def test_from_settings_raises_on_invalid(self) -> None:
        """from_settings raises ValueError on incomplete settings"""
        from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
        from exabgp.bgp.message.update.nlri.settings import INETSettings

        settings = INETSettings()
        settings.afi = AFI.ipv4  # Missing cidr, safi, labels, rd

        with pytest.raises(ValueError):
            IPVPN.from_settings(settings)


class TestFlowSettings:
    """Test FlowSettings dataclass"""

    def test_create_empty_settings(self) -> None:
        """Empty settings can be created with defaults"""
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()
        assert settings.afi is None
        assert settings.safi is None
        assert settings.action == Action.ANNOUNCE
        assert settings.nexthop is IP.NoNextHop
        assert settings.rules == {}
        assert settings.rd is None

    def test_validate_missing_afi(self) -> None:
        """Validation returns error when afi is missing"""
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()
        settings.safi = SAFI.flow_ip

        error = settings.validate()
        assert 'afi' in error.lower()

    def test_validate_missing_safi(self) -> None:
        """Validation returns error when safi is missing"""
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()
        settings.afi = AFI.ipv4

        error = settings.validate()
        assert 'safi' in error.lower()

    def test_validate_complete_settings(self) -> None:
        """Complete valid settings return empty string"""
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.flow_ip

        error = settings.validate()
        assert error == ''

    def test_set_method_assigns_value(self) -> None:
        """set() method assigns values by name"""
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()

        settings.set('afi', AFI.ipv4)
        settings.set('safi', SAFI.flow_ip)

        assert settings.afi == AFI.ipv4
        assert settings.safi == SAFI.flow_ip


class TestFlowFromSettings:
    """Test Flow.from_settings() factory method"""

    def test_from_settings_creates_valid_flow(self) -> None:
        """from_settings creates valid Flow from complete settings"""
        from exabgp.bgp.message.update.nlri.flow import Flow
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.flow_ip

        flow = Flow.from_settings(settings)

        assert flow.afi == AFI.ipv4
        assert flow.safi == SAFI.flow_ip

    def test_from_settings_preserves_action(self) -> None:
        """from_settings preserves action from settings"""
        from exabgp.bgp.message.update.nlri.flow import Flow
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.flow_ip
        settings.action = Action.WITHDRAW

        flow = Flow.from_settings(settings)

        assert flow.action == Action.WITHDRAW

    def test_from_settings_preserves_nexthop(self) -> None:
        """from_settings preserves nexthop from settings"""
        from exabgp.bgp.message.update.nlri.flow import Flow
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        nexthop = IP.from_string('192.168.1.1')

        settings = FlowSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.flow_ip
        settings.nexthop = nexthop

        flow = Flow.from_settings(settings)

        assert flow.nexthop == nexthop

    def test_from_settings_with_rules(self) -> None:
        """from_settings with rules creates flow with those rules"""
        from exabgp.bgp.message.update.nlri.flow import Flow, FlowAnyPort, NumericOperator
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        # Create a simple rule
        port_rule = FlowAnyPort(NumericOperator.EQ, 80)

        settings = FlowSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.flow_ip
        settings.rules = {FlowAnyPort.ID: [port_rule]}

        flow = Flow.from_settings(settings)

        assert FlowAnyPort.ID in flow.rules
        assert len(flow.rules[FlowAnyPort.ID]) == 1

    def test_from_settings_raises_on_invalid(self) -> None:
        """from_settings raises ValueError on incomplete settings"""
        from exabgp.bgp.message.update.nlri.flow import Flow
        from exabgp.bgp.message.update.nlri.settings import FlowSettings

        settings = FlowSettings()
        settings.afi = AFI.ipv4  # Missing safi

        with pytest.raises(ValueError):
            Flow.from_settings(settings)

    def test_from_settings_pack_matches_expected(self) -> None:
        """from_settings with destination rule produces correct wire format.

        This test verifies the packed bytes match expected wire format from
        qa/encoding/conf-flow.ci:
        # flow destination-ipv4 192.168.0.1/32 ...
        NLRI payload: 0120C0A80001
          01 = type (destination prefix)
          20 = prefix length (32 bits)
          C0A80001 = 192.168.0.1
        """
        from unittest.mock import Mock

        from exabgp.bgp.message.direction import Direction
        from exabgp.bgp.message.open.capability.negotiated import Negotiated
        from exabgp.bgp.message.update.nlri.flow import Flow, Flow4Destination
        from exabgp.bgp.message.update.nlri.settings import FlowSettings
        from exabgp.protocol.ip import IPv4

        # Create destination rule for 192.168.0.1/32
        dest_rule = Flow4Destination.make_prefix4(IPv4.pton('192.168.0.1'), 32)

        settings = FlowSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.flow_ip
        settings.rules = {Flow4Destination.ID: [dest_rule]}

        flow = Flow.from_settings(settings)

        # Create negotiated for packing
        neighbor = Mock()
        neighbor.__getitem__ = Mock(return_value={'aigp': False})
        negotiated = Negotiated(neighbor, Direction.OUT)

        # Pack and verify
        packed = flow.pack_nlri(negotiated)

        # Expected NLRI (without length prefix): type(01) + prefix_len(20) + ip(C0A80001)
        # The pack_nlri includes length prefix
        # Length is 6 bytes (01 + 20 + C0A80001), so length prefix is 06
        expected_nlri_payload = bytes.fromhex('0120C0A80001')

        # packed should be [length][rules_data]
        # For compact encoding, length < 240 uses 1-byte length prefix
        assert len(packed) > 0
        assert packed[0] == 6  # Length prefix (6 bytes of NLRI data)
        assert packed[1:] == expected_nlri_payload

    def test_from_settings_pack_multiple_rules(self) -> None:
        """from_settings with multiple rules produces correct wire format.

        Based on qa/encoding/conf-flow.ci:
        # flow destination-ipv4 10.0.0.2/32 source-ipv4 10.0.0.1/32 protocol =TCP destination-port =3128
        NLRI: 1301200A00000202200A00000103810605910C38
          13 = length (19 bytes)
          01 20 0A000002 = destination 10.0.0.2/32
          02 20 0A000001 = source 10.0.0.1/32
          03 81 06 = protocol TCP (6)
          05 91 0C38 = destination-port 3128
        """
        from unittest.mock import Mock

        from exabgp.bgp.message.direction import Direction
        from exabgp.bgp.message.open.capability.negotiated import Negotiated
        from exabgp.bgp.message.update.nlri.flow import (
            Flow,
            Flow4Destination,
            Flow4Source,
            FlowDestinationPort,
            FlowIPProtocol,
            NumericOperator,
        )
        from exabgp.bgp.message.update.nlri.settings import FlowSettings
        from exabgp.protocol import Protocol
        from exabgp.protocol.ip import IPv4

        # Create rules
        dest_rule = Flow4Destination.make_prefix4(IPv4.pton('10.0.0.2'), 32)
        src_rule = Flow4Source.make_prefix4(IPv4.pton('10.0.0.1'), 32)
        proto_rule = FlowIPProtocol(NumericOperator.EQ, Protocol(6))  # TCP
        port_rule = FlowDestinationPort(NumericOperator.EQ, 3128)

        settings = FlowSettings()
        settings.afi = AFI.ipv4
        settings.safi = SAFI.flow_ip
        settings.rules = {
            Flow4Destination.ID: [dest_rule],
            Flow4Source.ID: [src_rule],
            FlowIPProtocol.ID: [proto_rule],
            FlowDestinationPort.ID: [port_rule],
        }

        flow = Flow.from_settings(settings)

        # Create negotiated for packing
        neighbor = Mock()
        neighbor.__getitem__ = Mock(return_value={'aigp': False})
        negotiated = Negotiated(neighbor, Direction.OUT)

        # Pack and verify
        packed = flow.pack_nlri(negotiated)

        # Expected from functional test
        expected = bytes.fromhex('1301200A00000202200A00000103810605910C38')

        assert packed == expected
