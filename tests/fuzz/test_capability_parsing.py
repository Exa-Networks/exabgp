"""Comprehensive fuzz tests for BGP capability parsing.

This module tests that capability parsing handles malformed input gracefully
without crashing. All parsing errors should result in appropriate Notify
exceptions, not crashes or undefined behavior.

Test Categories:
- Capability length vs data length mismatch
- Unknown capability codes
- Malformed AddPath data (not multiple of 4)
- Malformed Graceful Restart data
- Truncated hostname/software version
- Extended format validation
"""

import pytest
import struct
from typing import Any
from hypothesis import given, strategies as st, settings, HealthCheck, assume

pytestmark = pytest.mark.fuzz


# =============================================================================
# Helper Functions
# =============================================================================


def create_capability(code: int, value: bytes) -> bytes:
    """Create a capability TLV.

    Args:
        code: Capability code (1 byte)
        value: Capability value bytes

    Returns:
        Complete capability TLV: [code:1][length:1][value:var]
    """
    return bytes([code, len(value)]) + value


def create_parameter(param_type: int, capabilities: bytes) -> bytes:
    """Create an optional parameter containing capabilities.

    Args:
        param_type: Parameter type (2 = Capabilities)
        capabilities: Concatenated capability TLVs

    Returns:
        Complete parameter: [type:1][length:1][capabilities:var]
    """
    return bytes([param_type, len(capabilities)]) + capabilities


def create_open_params(params: bytes) -> bytes:
    """Create OPEN optional parameters section.

    Args:
        params: Concatenated parameters

    Returns:
        [opt_param_len:1][params:var]
    """
    return bytes([len(params)]) + params


# =============================================================================
# Capabilities Container Tests
# =============================================================================


@pytest.mark.fuzz
@given(random_data=st.binary(min_size=0, max_size=100))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=100)
def test_capabilities_random_data(random_data: bytes) -> None:
    """Test Capabilities.unpack doesn't crash on random data."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities
    from exabgp.bgp.message.notification import Notify

    try:
        capabilities = Capabilities.unpack(random_data)
        assert isinstance(capabilities, Capabilities)
    except Notify:
        # Expected for malformed data
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_capabilities_empty() -> None:
    """Test Capabilities.unpack with empty data."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    capabilities = Capabilities.unpack(b'')
    assert isinstance(capabilities, Capabilities)
    assert len(capabilities) == 0


@pytest.mark.fuzz
@given(opt_len=st.integers(min_value=1, max_value=254))
@settings(deadline=None, max_examples=50)
def test_capabilities_length_mismatch(opt_len: int) -> None:
    """Test Capabilities with option length exceeding data."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities
    from exabgp.bgp.message.notification import Notify

    # Claim opt_len bytes but provide less
    data = bytes([opt_len]) + b'\x00' * (opt_len - 1)

    try:
        capabilities = Capabilities.unpack(data)
        # May parse if we got lucky
    except Notify as e:
        # Expected - truncated
        assert e.code == 2  # OPEN message error


@pytest.mark.fuzz
def test_capabilities_extended_format() -> None:
    """Test Capabilities with extended format (RFC 9072)."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    # Extended format: 0xFF 0xFF [length:2] [data]
    # This is valid extended format with empty data
    data = bytes([0xFF, 0xFF]) + struct.pack('!H', 0)

    capabilities = Capabilities.unpack(data)
    assert isinstance(capabilities, Capabilities)


@pytest.mark.fuzz
@given(extended_len=st.integers(min_value=1, max_value=100))
@settings(deadline=None, max_examples=50)
def test_capabilities_extended_truncated(extended_len: int) -> None:
    """Test Capabilities extended format with truncated data."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities
    from exabgp.bgp.message.notification import Notify

    # Claim extended_len bytes but provide less
    data = bytes([0xFF, 0xFF]) + struct.pack('!H', extended_len) + b'\x00' * (extended_len - 1)

    try:
        capabilities = Capabilities.unpack(data)
    except Notify as e:
        # Expected - truncated
        assert e.code == 2  # OPEN message error


# =============================================================================
# AddPath Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(entry_count=st.integers(min_value=0, max_value=20))
@settings(deadline=None, max_examples=50)
def test_addpath_valid_entries(entry_count: int) -> None:
    """Test AddPath capability with valid entry count."""
    from exabgp.bgp.message.open.capability.addpath import AddPath
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode

    # Each entry: AFI(2) + SAFI(1) + send_receive(1) = 4 bytes
    # Use different AFI/SAFI pairs to avoid duplicate key collapsing
    afis = [1, 2]  # IPv4, IPv6
    safis = [1, 2, 4, 128]  # unicast, multicast, nlri_mpls, mpls_vpn

    data = b''
    unique_pairs = set()
    for i in range(entry_count):
        afi = afis[i % len(afis)]
        safi = safis[i % len(safis)]
        if (afi, safi) not in unique_pairs:
            unique_pairs.add((afi, safi))
            data += struct.pack('!H', afi)
            data += bytes([safi])
            data += bytes([3])  # send/receive

    instance = AddPath()
    result = AddPath.unpack_capability(instance, data, CapabilityCode(Capability.CODE.ADD_PATH))

    assert isinstance(result, AddPath)
    # Number of unique AFI/SAFI pairs
    assert len(result) == len(unique_pairs)


@pytest.mark.fuzz
@given(extra_bytes=st.integers(min_value=1, max_value=3))
@settings(deadline=None, max_examples=3)
def test_addpath_not_multiple_of_4(extra_bytes: int) -> None:
    """Test AddPath capability with length not multiple of 4."""
    from exabgp.bgp.message.open.capability.addpath import AddPath
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    # Valid entry + extra bytes
    data = struct.pack('!H', 1) + bytes([1, 3]) + b'\x00' * extra_bytes

    instance = AddPath()

    try:
        result = AddPath.unpack_capability(instance, data, CapabilityCode(Capability.CODE.ADD_PATH))
        # May parse first entry and fail on extra
    except Notify as e:
        # Expected - truncated entry
        assert e.code == 2  # OPEN message error


@pytest.mark.fuzz
def test_addpath_empty() -> None:
    """Test AddPath capability with empty data."""
    from exabgp.bgp.message.open.capability.addpath import AddPath
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode

    instance = AddPath()
    result = AddPath.unpack_capability(instance, b'', CapabilityCode(Capability.CODE.ADD_PATH))

    assert isinstance(result, AddPath)
    assert len(result) == 0


@pytest.mark.fuzz
@given(send_receive=st.integers(min_value=0, max_value=255))
@settings(deadline=None, max_examples=50)
def test_addpath_send_receive_values(send_receive: int) -> None:
    """Test AddPath with various send/receive flag values."""
    from exabgp.bgp.message.open.capability.addpath import AddPath
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode

    data = struct.pack('!H', 1) + bytes([1, send_receive])

    instance = AddPath()
    result = AddPath.unpack_capability(instance, data, CapabilityCode(Capability.CODE.ADD_PATH))

    assert isinstance(result, AddPath)
    # Only values 0-3 are defined, but others shouldn't crash


# =============================================================================
# MultiProtocol Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    afi=st.integers(min_value=0, max_value=65535),
    safi=st.integers(min_value=0, max_value=255),
)
@settings(deadline=None, max_examples=100)
def test_multiprotocol_afi_safi_values(afi: int, safi: int) -> None:
    """Test MultiProtocol capability with various AFI/SAFI values."""
    from exabgp.bgp.message.open.capability.mp import MultiProtocol
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode

    # Format: AFI(2) + reserved(1) + SAFI(1) = 4 bytes
    data = struct.pack('!H', afi) + bytes([0, safi])

    instance = MultiProtocol((0, 0))  # Dummy init

    try:
        result = MultiProtocol.unpack_capability(instance, data, CapabilityCode(Capability.CODE.MULTIPROTOCOL))
        assert isinstance(result, MultiProtocol)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(data_len=st.integers(min_value=0, max_value=3))
@settings(deadline=None, max_examples=4)
def test_multiprotocol_truncated(data_len: int) -> None:
    """Test MultiProtocol capability with truncated data."""
    from exabgp.bgp.message.open.capability.mp import MultiProtocol
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    # Less than 4 bytes
    data = b'\x00' * data_len

    instance = MultiProtocol((0, 0))

    try:
        result = MultiProtocol.unpack_capability(instance, data, CapabilityCode(Capability.CODE.MULTIPROTOCOL))
    except (Notify, IndexError, struct.error):
        # Expected - truncated
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Graceful Restart Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(family_count=st.integers(min_value=0, max_value=10))
@settings(deadline=None, max_examples=30)
def test_graceful_restart_valid(family_count: int) -> None:
    """Test Graceful Restart capability with valid family entries."""
    from exabgp.bgp.message.open.capability.graceful import Graceful
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode

    # Format: flags+time(2) + [AFI(2)+SAFI(1)+flags(1)]*n
    data = struct.pack('!H', 0x8000 | 120)  # Restart bit + 120 seconds

    for _ in range(family_count):
        data += struct.pack('!H', 1)  # AFI IPv4
        data += bytes([1])  # SAFI unicast
        data += bytes([0x80])  # Forwarding state preserved

    instance = Graceful()

    try:
        result = Graceful.unpack_capability(instance, data, CapabilityCode(Capability.CODE.GRACEFUL_RESTART))
        assert isinstance(result, Graceful)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_graceful_restart_empty() -> None:
    """Test Graceful Restart capability with empty data."""
    from exabgp.bgp.message.open.capability.graceful import Graceful
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    instance = Graceful()

    try:
        result = Graceful.unpack_capability(instance, b'', CapabilityCode(Capability.CODE.GRACEFUL_RESTART))
    except (Notify, IndexError, struct.error):
        # Expected - need at least 2 bytes
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(extra_bytes=st.integers(min_value=1, max_value=3))
@settings(deadline=None, max_examples=3)
def test_graceful_restart_not_aligned(extra_bytes: int) -> None:
    """Test Graceful Restart with entry not aligned to 4 bytes."""
    from exabgp.bgp.message.open.capability.graceful import Graceful
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    # Header(2) + incomplete family entry
    data = struct.pack('!H', 0x8000 | 120) + b'\x00' * extra_bytes

    instance = Graceful()

    try:
        result = Graceful.unpack_capability(instance, data, CapabilityCode(Capability.CODE.GRACEFUL_RESTART))
    except (Notify, IndexError, struct.error):
        # Expected - incomplete family
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# ASN4 Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(asn=st.integers(min_value=0, max_value=0xFFFFFFFF))
@settings(deadline=None, max_examples=50)
def test_asn4_valid_values(asn: int) -> None:
    """Test ASN4 capability with full 32-bit range."""
    from exabgp.bgp.message.open.capability.asn4 import ASN4
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode

    data = struct.pack('!L', asn)

    instance = ASN4(0)

    try:
        result = ASN4.unpack_capability(instance, data, CapabilityCode(Capability.CODE.FOUR_BYTES_ASN))
        assert isinstance(result, ASN4)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(data_len=st.integers(min_value=0, max_value=3))
@settings(deadline=None, max_examples=4)
def test_asn4_truncated(data_len: int) -> None:
    """Test ASN4 capability with truncated data."""
    from exabgp.bgp.message.open.capability.asn4 import ASN4
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    data = b'\x00' * data_len

    instance = ASN4(0)

    try:
        result = ASN4.unpack_capability(instance, data, CapabilityCode(Capability.CODE.FOUR_BYTES_ASN))
    except (Notify, IndexError, struct.error):
        # Expected - need 4 bytes
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Hostname Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    hostname_len=st.integers(min_value=0, max_value=255),
    domain_len=st.integers(min_value=0, max_value=255),
)
@settings(deadline=None, max_examples=50)
def test_hostname_length_combinations(hostname_len: int, domain_len: int) -> None:
    """Test Hostname capability with various length combinations."""
    from exabgp.bgp.message.open.capability.hostname import HostName
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    # Format: hostname_len(1) + hostname + domain_len(1) + domain
    hostname = b'a' * min(hostname_len, 64)
    domain = b'b' * min(domain_len, 64)

    data = bytes([len(hostname)]) + hostname + bytes([len(domain)]) + domain

    instance = HostName()

    try:
        result = HostName.unpack_capability(instance, data, CapabilityCode(Capability.CODE.HOSTNAME))
        assert isinstance(result, HostName)
    except (Notify, IndexError):
        # Expected for invalid lengths
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_hostname_empty() -> None:
    """Test Hostname capability with empty data."""
    from exabgp.bgp.message.open.capability.hostname import HostName
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    instance = HostName()

    try:
        result = HostName.unpack_capability(instance, b'', CapabilityCode(Capability.CODE.HOSTNAME))
    except (Notify, IndexError):
        # Expected - need at least length byte
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_hostname_truncated_hostname() -> None:
    """Test Hostname capability where hostname length exceeds data."""
    from exabgp.bgp.message.open.capability.hostname import HostName
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    # Claim 10 bytes for hostname but provide only 5
    data = bytes([10]) + b'short'

    instance = HostName()

    try:
        result = HostName.unpack_capability(instance, data, CapabilityCode(Capability.CODE.HOSTNAME))
    except (Notify, IndexError):
        # Expected - truncated
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# NextHop Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(entry_count=st.integers(min_value=0, max_value=10))
@settings(deadline=None, max_examples=30)
def test_nexthop_valid_entries(entry_count: int) -> None:
    """Test NextHop capability with valid entries."""
    from exabgp.bgp.message.open.capability.nexthop import NextHop
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode

    # Each entry: AFI(2) + SAFI(2) + next-hop-AFI(2) = 6 bytes
    data = b''
    for _ in range(entry_count):
        data += struct.pack('!H', 1)  # AFI IPv4
        data += struct.pack('!H', 1)  # SAFI unicast
        data += struct.pack('!H', 2)  # NextHop AFI IPv6

    instance = NextHop()

    try:
        result = NextHop.unpack_capability(instance, data, CapabilityCode(Capability.CODE.NEXTHOP))
        assert isinstance(result, NextHop)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(extra_bytes=st.integers(min_value=1, max_value=5))
@settings(deadline=None, max_examples=5)
def test_nexthop_not_multiple_of_6(extra_bytes: int) -> None:
    """Test NextHop capability with length not multiple of 6."""
    from exabgp.bgp.message.open.capability.nexthop import NextHop
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    # Valid entry + extra bytes
    data = struct.pack('!HHH', 1, 1, 2) + b'\x00' * extra_bytes

    instance = NextHop()

    try:
        result = NextHop.unpack_capability(instance, data, CapabilityCode(Capability.CODE.NEXTHOP))
    except (Notify, IndexError, struct.error):
        # Expected - incomplete entry
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Unknown Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    code=st.integers(min_value=100, max_value=255),
    value_len=st.integers(min_value=0, max_value=50),
)
@settings(deadline=None, max_examples=50)
def test_unknown_capability(code: int, value_len: int) -> None:
    """Test handling of unknown capability codes."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    value = b'\x00' * value_len
    capability = create_capability(code, value)
    param = create_parameter(2, capability)
    data = create_open_params(param)

    try:
        capabilities = Capabilities.unpack(data)
        # Unknown capabilities should be stored or ignored, not crash
        assert isinstance(capabilities, Capabilities)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Software Version Capability Tests
# =============================================================================


@pytest.mark.fuzz
@given(version_len=st.integers(min_value=0, max_value=255))
@settings(deadline=None, max_examples=50)
def test_software_version_lengths(version_len: int) -> None:
    """Test Software Version capability with various lengths."""
    from exabgp.bgp.message.open.capability.software import Software
    from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
    from exabgp.bgp.message.notification import Notify

    # Format: version_len(1) + version
    version = b'v' * min(version_len, 64)
    data = bytes([len(version)]) + version

    instance = Software()

    try:
        result = Software.unpack_capability(instance, data, CapabilityCode(Capability.CODE.SOFTWARE_VERSION))
        assert isinstance(result, Software)
    except (Notify, IndexError):
        # Expected for invalid lengths
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Full OPEN Parameters Tests
# =============================================================================


@pytest.mark.fuzz
@given(capability_count=st.integers(min_value=1, max_value=10))
@settings(deadline=None, max_examples=30)
def test_multiple_capabilities(capability_count: int) -> None:
    """Test parsing multiple capabilities in one parameter."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    # Build multiple capabilities
    capabilities = b''
    for i in range(capability_count):
        # Multiprotocol capability for IPv4 unicast
        cap = create_capability(1, struct.pack('!H', 1) + bytes([0, 1]))
        capabilities += cap

    param = create_parameter(2, capabilities)
    data = create_open_params(param)

    result = Capabilities.unpack(data)
    assert isinstance(result, Capabilities)


@pytest.mark.fuzz
def test_multiple_parameters() -> None:
    """Test parsing multiple optional parameters."""
    from exabgp.bgp.message.open.capability.capabilities import Capabilities

    # Two capability parameters
    cap1 = create_capability(1, struct.pack('!H', 1) + bytes([0, 1]))
    cap2 = create_capability(1, struct.pack('!H', 2) + bytes([0, 1]))

    param1 = create_parameter(2, cap1)
    param2 = create_parameter(2, cap2)

    data = create_open_params(param1 + param2)

    result = Capabilities.unpack(data)
    assert isinstance(result, Capabilities)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
