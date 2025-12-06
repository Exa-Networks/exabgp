"""Test configuration export to JSON.

Tests that parsed configuration matches expected JSON output.
"""

from __future__ import annotations

import json
import pytest
from pathlib import Path

from exabgp.configuration.configuration import Configuration
from exabgp.configuration.encoder import ConfigEncoder, config_to_json, _serialize_value


# Directory containing test fixtures
FIXTURES_DIR = Path(__file__).parent / 'fixtures'
# Directory containing ExaBGP example configs
CONFIG_DIR = Path(__file__).parent.parent.parent.parent / 'etc' / 'exabgp'


def get_config_fixtures() -> list[tuple[Path, Path]]:
    """Find all config files with matching expected JSON."""
    fixtures = []
    for expected_file in FIXTURES_DIR.glob('*.expected.json'):
        # Expected file format: configname.expected.json
        config_name = expected_file.stem.replace('.expected', '')
        conf_file = CONFIG_DIR / f'{config_name}.conf'
        if conf_file.exists():
            fixtures.append((conf_file, expected_file))
    return fixtures


@pytest.mark.parametrize('conf_file,expected_file', get_config_fixtures())
def test_configuration_export_matches_expected(conf_file: Path, expected_file: Path) -> None:
    """Test that parsed configuration matches expected JSON."""
    # Load and parse configuration
    config = Configuration([str(conf_file)])
    valid = config.reload()
    assert valid is True, f'Configuration failed to parse: {conf_file}'

    # Export to dict and serialize to JSON using config_to_json
    actual = config.to_dict()
    actual_json = config_to_json(actual, indent=2)

    # Load expected JSON
    with open(expected_file) as f:
        expected = json.load(f)
    expected_json = json.dumps(expected, sort_keys=True, indent=2)

    # Compare
    assert actual_json == expected_json, (
        f'Configuration mismatch for {conf_file.name}\n'
        f'Run: ./sbin/exabgp configuration export {conf_file} > {expected_file}\n'
        f'to update expected output'
    )


def get_all_config_files() -> list[Path]:
    """Get all .conf files from etc/exabgp/."""
    return sorted(CONFIG_DIR.glob('*.conf'))


@pytest.mark.parametrize('conf_file', get_all_config_files(), ids=lambda p: p.name)
def test_configuration_can_be_serialized(conf_file: Path) -> None:
    """Test that configuration can be parsed and serialized to JSON.

    This test verifies that ALL config files in etc/exabgp/ can be:
    1. Parsed successfully
    2. Converted to dict via to_dict()
    3. Serialized to JSON without errors

    This catches any types that aren't handled by the encoder.
    """
    # Load and parse configuration
    config = Configuration([str(conf_file)])
    valid = config.reload()
    assert valid is True, f'Configuration failed to parse: {conf_file}'

    # Export to dict - should not raise
    data = config.to_dict()
    assert isinstance(data, dict)
    assert 'neighbors' in data
    assert 'processes' in data

    # Serialize to JSON - should not raise
    json_output = config_to_json(data)
    assert isinstance(json_output, str)
    assert len(json_output) > 0

    # Verify it's valid JSON by parsing it back
    parsed = json.loads(json_output)
    assert isinstance(parsed, dict)


class TestConfigurationToDict:
    """Test Configuration.to_dict() method."""

    def test_to_dict_returns_dict(self) -> None:
        """Test that to_dict returns a dictionary."""
        config = Configuration([''], text=True)
        # Empty config should still work
        result = config.to_dict()
        assert isinstance(result, dict)
        assert 'neighbors' in result
        assert 'processes' in result

    def test_to_dict_empty_config(self) -> None:
        """Test to_dict with empty configuration."""
        config = Configuration([''], text=True)
        result = config.to_dict()
        assert result['neighbors'] == {}
        assert result['processes'] == {}


class TestConfigEncoder:
    """Test ConfigEncoder JSON encoder."""

    def test_encode_ip(self) -> None:
        """Test IP address encoding."""
        from exabgp.protocol.ip import IPv4

        ip = IPv4.from_string('192.168.1.1')
        result = json.dumps(ip, cls=ConfigEncoder)
        parsed = json.loads(result)
        assert parsed['_type'] == 'IP'
        assert parsed['value'] == '192.168.1.1'

    def test_encode_no_nexthop(self) -> None:
        """Test NoNextHop sentinel encoding."""
        from exabgp.protocol.ip import IP

        result = json.dumps(IP.NoNextHop, cls=ConfigEncoder)
        parsed = json.loads(result)
        assert parsed['_type'] == 'IP'
        assert parsed['value'] == 'no-nexthop'

    def test_encode_asn(self) -> None:
        """Test ASN encoding.

        Note: ASN subclasses int, so we must use _serialize_value()
        instead of json.dumps() with ConfigEncoder.
        """
        from exabgp.bgp.message.open.asn import ASN

        asn = ASN(65000)
        parsed = _serialize_value(asn)
        assert parsed['_type'] == 'ASN'
        assert parsed['value'] == 65000

    def test_encode_afi(self) -> None:
        """Test AFI encoding.

        Note: AFI subclasses int, so we must use _serialize_value().
        """
        from exabgp.protocol.family import AFI

        afi = AFI.ipv4
        parsed = _serialize_value(afi)
        assert parsed['_type'] == 'AFI'
        assert parsed['value'] == 'ipv4'

    def test_encode_safi(self) -> None:
        """Test SAFI encoding.

        Note: SAFI subclasses int, so we must use _serialize_value().
        """
        from exabgp.protocol.family import SAFI

        safi = SAFI.unicast
        parsed = _serialize_value(safi)
        assert parsed['_type'] == 'SAFI'
        assert parsed['value'] == 'unicast'

    def test_encode_holdtime(self) -> None:
        """Test HoldTime encoding.

        Note: HoldTime subclasses int, so we must use _serialize_value().
        """
        from exabgp.bgp.message.open.holdtime import HoldTime

        holdtime = HoldTime(180)
        parsed = _serialize_value(holdtime)
        assert parsed['_type'] == 'HoldTime'
        assert parsed['value'] == 180

    def test_encode_tristate(self) -> None:
        """Test TriState encoding.

        Note: TriState is an IntEnum, so we must use _serialize_value().
        """
        from exabgp.util.enumeration import TriState

        for state in [TriState.TRUE, TriState.FALSE, TriState.UNSET]:
            parsed = _serialize_value(state)
            assert parsed['_type'] == 'TriState'
            assert parsed['value'] == state.name

    def test_encode_graceful_restart_config(self) -> None:
        """Test GracefulRestartConfig encoding."""
        from exabgp.bgp.neighbor.capability import GracefulRestartConfig

        gr = GracefulRestartConfig.with_time(120)
        result = json.dumps(gr, cls=ConfigEncoder)
        parsed = json.loads(result)
        assert parsed['_type'] == 'GracefulRestartConfig'
        assert parsed['state'] == 'TRUE'
        assert parsed['time'] == 120

    def test_encode_session(self) -> None:
        """Test Session encoding."""
        from exabgp.bgp.neighbor.session import Session
        from exabgp.bgp.message.open.asn import ASN
        from exabgp.protocol.ip import IPv4

        session = Session()
        session.peer_address = IPv4.from_string('192.168.1.1')
        session.local_address = IPv4.from_string('192.168.1.2')
        session.local_as = ASN(65000)
        session.peer_as = ASN(65001)

        result = json.dumps(session, cls=ConfigEncoder)
        parsed = json.loads(result)
        assert parsed['_type'] == 'Session'
        assert parsed['peer_address']['value'] == '192.168.1.1'
        assert parsed['local_address']['value'] == '192.168.1.2'

    def test_encode_bytes(self) -> None:
        """Test bytes encoding as hex."""
        data = b'\x01\x02\x03\xff'
        result = json.dumps(data, cls=ConfigEncoder)
        parsed = json.loads(result)
        assert parsed['_type'] == 'bytes'
        assert parsed['hex'] == '010203ff'

    def test_encode_deque(self) -> None:
        """Test deque encoding as list."""
        from collections import deque

        data = deque([1, 2, 3])
        result = json.dumps(data, cls=ConfigEncoder)
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_encode_counter(self) -> None:
        """Test Counter encoding as dict."""
        from collections import Counter

        data = Counter(['a', 'a', 'b'])
        result = json.dumps(data, cls=ConfigEncoder)
        parsed = json.loads(result)
        assert parsed == {'a': 2, 'b': 1}


class TestConfigToJson:
    """Test config_to_json helper function."""

    def test_config_to_json_output(self) -> None:
        """Test config_to_json produces valid JSON."""
        data = {'key': 'value', 'nested': {'a': 1}}
        result = config_to_json(data)
        parsed = json.loads(result)
        assert parsed == data

    def test_config_to_json_sorted_keys(self) -> None:
        """Test config_to_json sorts keys."""
        data = {'z': 1, 'a': 2, 'm': 3}
        result = config_to_json(data)
        # Keys should appear in sorted order in JSON string
        assert result.index('"a"') < result.index('"m"') < result.index('"z"')

    def test_config_to_json_indent(self) -> None:
        """Test config_to_json respects indent parameter."""
        data = {'key': 'value'}
        result_2 = config_to_json(data, indent=2)
        result_4 = config_to_json(data, indent=4)
        # 4-space indent should produce more whitespace
        assert len(result_4) > len(result_2)
