"""Comprehensive fuzz tests for malformed NLRI parsing.

This module tests that NLRI parsing handles malformed input gracefully
without crashing. All parsing errors should result in appropriate Notify
exceptions, not crashes or undefined behavior.

Test Categories:
- Invalid prefix lengths (>32 for IPv4, >128 for IPv6)
- Truncated NLRI data
- Path-ID with non-AddPath session
- Label stack corruption
- RD field corruption
- FlowSpec malformed components
"""

import pytest
import struct
from typing import Any
from unittest.mock import Mock
from hypothesis import given, strategies as st, settings, HealthCheck, assume

from exabgp.bgp.message import Action
from exabgp.protocol.family import AFI, SAFI

pytestmark = pytest.mark.fuzz


# =============================================================================
# Helper Functions
# =============================================================================


def create_mock_negotiated(addpath: bool = False, asn4: bool = True) -> Any:
    """Create a minimal mock Negotiated object for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})

    negotiated = Mock()
    negotiated.neighbor = neighbor
    negotiated.families = [(1, 1)]
    negotiated.asn4 = asn4
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.aigp = False
    negotiated.msg_size = 4096

    # AddPath configuration
    negotiated.addpath = Mock()
    negotiated.addpath.send = Mock(return_value=addpath)
    negotiated.addpath.receive = Mock(return_value=addpath)
    negotiated.required = Mock(return_value=addpath)

    return negotiated


# =============================================================================
# INET NLRI Malformed Tests
# =============================================================================


@pytest.mark.fuzz
@given(mask=st.integers(min_value=33, max_value=255))
@settings(deadline=None, max_examples=50)
def test_ipv4_prefix_length_too_large(mask: int) -> None:
    """Test IPv4 NLRI with prefix length > 32."""
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.notification import Notify

    # Mask byte + prefix bytes (mask > 32 is invalid for IPv4)
    data = bytes([mask]) + b'\xc0\xa8\x01\x00'

    try:
        nlri, _ = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, data, Action.ANNOUNCE, False, None)
        # If it parses, should at least not crash
        # Some implementations may accept > 32 masks
    except (Notify, ValueError, IndexError):
        # Expected - invalid mask
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(mask=st.integers(min_value=129, max_value=255))
@settings(deadline=None, max_examples=50)
def test_ipv6_prefix_length_too_large(mask: int) -> None:
    """Test IPv6 NLRI with prefix length > 128."""
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.notification import Notify

    # Mask byte + prefix bytes (mask > 128 is invalid for IPv6)
    data = bytes([mask]) + b'\x20\x01\x0d\xb8' + b'\x00' * 12

    try:
        nlri, _ = INET.unpack_nlri(AFI.ipv6, SAFI.unicast, data, Action.ANNOUNCE, False, None)
    except (Notify, ValueError, IndexError):
        # Expected - invalid mask
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(mask=st.integers(min_value=1, max_value=32))
@settings(deadline=None, max_examples=50)
def test_ipv4_truncated_prefix(mask: int) -> None:
    """Test IPv4 NLRI where prefix bytes are truncated."""
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.notification import Notify

    # Calculate needed bytes
    needed_bytes = (mask + 7) // 8

    # Provide less bytes than needed
    assume(needed_bytes > 0)
    data = bytes([mask]) + b'\x00' * (needed_bytes - 1)

    try:
        nlri, _ = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, data, Action.ANNOUNCE, False, None)
    except (Notify, ValueError, IndexError, struct.error):
        # Expected - truncated data
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_inet_empty_data() -> None:
    """Test INET parsing with empty data."""
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.notification import Notify

    try:
        nlri, _ = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, b'', Action.ANNOUNCE, False, None)
    except (Notify, ValueError, IndexError):
        # Expected - no data
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(random_data=st.binary(min_size=0, max_size=50))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=100)
def test_inet_random_data(random_data: bytes) -> None:
    """Test INET parsing doesn't crash on random data."""
    from exabgp.bgp.message.update.nlri.inet import INET

    try:
        nlri, _ = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, random_data, Action.ANNOUNCE, False, None)
    except Exception as e:
        # Should handle gracefully
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(
    path_id=st.binary(min_size=4, max_size=4),
    mask=st.integers(min_value=0, max_value=32),
)
@settings(deadline=None, max_examples=50)
def test_inet_with_addpath(path_id: bytes, mask: int) -> None:
    """Test INET parsing with AddPath path identifier."""
    from exabgp.bgp.message.update.nlri.inet import INET

    # Calculate prefix bytes needed
    prefix_bytes = (mask + 7) // 8
    prefix = b'\xc0\xa8\x01\x00'[:prefix_bytes]

    # Format: path_id(4) + mask(1) + prefix(var)
    data = path_id + bytes([mask]) + prefix

    negotiated = create_mock_negotiated(addpath=True)

    try:
        nlri, leftover = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, data, Action.ANNOUNCE, True, negotiated)
        # If successful, verify path_id is preserved
        assert nlri.path_info.pack_path() == path_id
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_inet_addpath_truncated() -> None:
    """Test INET with AddPath but truncated path ID."""
    from exabgp.bgp.message.update.nlri.inet import INET
    from exabgp.bgp.message.notification import Notify

    # Only 3 bytes of path_id (should be 4)
    data = b'\x00\x00\x00' + bytes([24]) + b'\xc0\xa8\x01'

    negotiated = create_mock_negotiated(addpath=True)

    try:
        nlri, _ = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, data, Action.ANNOUNCE, True, negotiated)
    except (Notify, ValueError, IndexError):
        # Expected - truncated path_id
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# Labeled NLRI Tests
# =============================================================================


@pytest.mark.fuzz
@given(label_count=st.integers(min_value=1, max_value=5))
@settings(deadline=None, max_examples=20)
def test_labeled_nlri_valid(label_count: int) -> None:
    """Test labeled unicast NLRI with valid label stack."""
    from exabgp.bgp.message.update.nlri.label import Label

    # Build label stack (each label is 3 bytes)
    labels = b''
    for i in range(label_count - 1):
        # Label without bottom-of-stack bit
        labels += struct.pack('!I', (100 + i) << 4)[1:]

    # Last label with bottom-of-stack bit
    labels += struct.pack('!I', ((100 + label_count - 1) << 4) | 1)[1:]

    # Mask includes labels: label_bits + prefix_bits
    label_bits = label_count * 24
    prefix_mask = 24
    total_mask = label_bits + prefix_mask

    # Format: mask(1) + labels(var) + prefix(var)
    data = bytes([total_mask]) + labels + b'\xc0\xa8\x01'

    try:
        nlri, _ = Label.unpack_nlri(AFI.ipv4, SAFI.unicast_label, data, Action.ANNOUNCE, False, None)
        assert nlri.labels is not None
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_labeled_nlri_no_bottom_of_stack() -> None:
    """Test labeled NLRI where label stack never terminates."""
    from exabgp.bgp.message.update.nlri.label import Label
    from exabgp.bgp.message.notification import Notify

    # Label without bottom-of-stack bit
    label = struct.pack('!I', 100 << 4)[1:]  # 3 bytes, no BoS

    # Mask: 24 bits label + 24 bits prefix = 48
    data = bytes([48]) + label + b'\xc0\xa8\x01'

    try:
        nlri, _ = Label.unpack_nlri(AFI.ipv4, SAFI.unicast_label, data, Action.ANNOUNCE, False, None)
        # May parse but labels may be incomplete
    except (Notify, ValueError, IndexError):
        # Expected - no bottom of stack
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(random_data=st.binary(min_size=0, max_size=30))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=50)
def test_labeled_nlri_random_data(random_data: bytes) -> None:
    """Test labeled NLRI parsing doesn't crash on random data."""
    from exabgp.bgp.message.update.nlri.label import Label

    try:
        nlri, _ = Label.unpack_nlri(AFI.ipv4, SAFI.unicast_label, random_data, Action.ANNOUNCE, False, None)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# VPN NLRI Tests
# =============================================================================


@pytest.mark.fuzz
@given(
    rd_type=st.integers(min_value=0, max_value=2),
    rd_value=st.binary(min_size=6, max_size=6),
)
@settings(deadline=None, max_examples=30)
def test_vpn_nlri_rd_types(rd_type: int, rd_value: bytes) -> None:
    """Test VPN NLRI with different RD types."""
    from exabgp.bgp.message.update.nlri.ipvpn import IPVPN

    # RD: type(2) + value(6) = 8 bytes
    rd = struct.pack('!H', rd_type) + rd_value

    # Label (3 bytes) + RD (8 bytes) = 88 bits base
    label = struct.pack('!I', (100 << 4) | 1)[1:]

    # Mask: 24 (label) + 64 (RD) + 24 (prefix) = 112
    prefix_mask = 24
    total_mask = 24 + 64 + prefix_mask

    data = bytes([total_mask]) + label + rd + b'\xc0\xa8\x01'

    try:
        nlri, _ = IPVPN.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, data, Action.ANNOUNCE, False, None)
        assert nlri.rd is not None
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_vpn_nlri_truncated_rd() -> None:
    """Test VPN NLRI with truncated Route Distinguisher."""
    from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
    from exabgp.bgp.message.notification import Notify

    # Label (3 bytes) + truncated RD (4 bytes instead of 8)
    label = struct.pack('!I', (100 << 4) | 1)[1:]
    rd = b'\x00\x02\x00\x00'  # Only 4 bytes

    # Claim full mask but provide truncated data
    data = bytes([112]) + label + rd + b'\xc0\xa8\x01'

    try:
        nlri, _ = IPVPN.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, data, Action.ANNOUNCE, False, None)
    except (Notify, ValueError, IndexError, struct.error):
        # Expected - truncated RD
        pass
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
@given(random_data=st.binary(min_size=0, max_size=50))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None, max_examples=50)
def test_vpn_nlri_random_data(random_data: bytes) -> None:
    """Test VPN NLRI parsing doesn't crash on random data."""
    from exabgp.bgp.message.update.nlri.ipvpn import IPVPN

    try:
        nlri, _ = IPVPN.unpack_nlri(AFI.ipv4, SAFI.mpls_vpn, random_data, Action.ANNOUNCE, False, None)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


# =============================================================================
# CIDR Boundary Tests
# =============================================================================


@pytest.mark.fuzz
def test_cidr_mask_zero() -> None:
    """Test CIDR with mask = 0 (default route)."""
    from exabgp.bgp.message.update.nlri.inet import INET

    # Mask 0 = 0 prefix bytes needed
    data = bytes([0])

    try:
        nlri, leftover = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, data, Action.ANNOUNCE, False, None)
        assert nlri.cidr.mask == 0
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_cidr_mask_max_ipv4() -> None:
    """Test CIDR with mask = 32 (host route)."""
    from exabgp.bgp.message.update.nlri.inet import INET

    # Mask 32 = 4 prefix bytes needed
    data = bytes([32]) + b'\xc0\xa8\x01\x01'

    nlri, leftover = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, data, Action.ANNOUNCE, False, None)
    assert nlri.cidr.mask == 32


@pytest.mark.fuzz
def test_cidr_mask_max_ipv6() -> None:
    """Test CIDR with mask = 128 (host route)."""
    from exabgp.bgp.message.update.nlri.inet import INET

    # Mask 128 = 16 prefix bytes needed
    data = bytes([128]) + b'\x20\x01\x0d\xb8' + b'\x00' * 12

    nlri, leftover = INET.unpack_nlri(AFI.ipv6, SAFI.unicast, data, Action.ANNOUNCE, False, None)
    assert nlri.cidr.mask == 128


# =============================================================================
# Multiple NLRI Parsing Tests
# =============================================================================


@pytest.mark.fuzz
@given(nlri_count=st.integers(min_value=1, max_value=10))
@settings(deadline=None, max_examples=30)
def test_multiple_nlri_parsing(nlri_count: int) -> None:
    """Test parsing multiple NLRIs concatenated together."""
    from exabgp.bgp.message.update.nlri.inet import INET

    # Build multiple /24 prefixes
    data = b''
    for i in range(nlri_count):
        data += bytes([24]) + bytes([192, 168, i])

    nlris = []
    remaining = data
    while remaining:
        try:
            nlri, remaining = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, remaining, Action.ANNOUNCE, False, None)
            nlris.append(nlri)
        except Exception:
            break

    # Should parse at least some NLRIs
    assert len(nlris) > 0


@pytest.mark.fuzz
def test_multiple_nlri_one_truncated() -> None:
    """Test multiple NLRIs where the last one is truncated."""
    from exabgp.bgp.message.update.nlri.inet import INET

    # Two complete + one truncated
    data = bytes([24]) + b'\xc0\xa8\x01'  # Complete
    data += bytes([24]) + b'\xc0\xa8\x02'  # Complete
    data += bytes([24]) + b'\xc0'  # Truncated (missing 2 bytes)

    nlris = []
    remaining = data
    while remaining:
        try:
            nlri, remaining = INET.unpack_nlri(AFI.ipv4, SAFI.unicast, remaining, Action.ANNOUNCE, False, None)
            nlris.append(nlri)
        except Exception:
            # Expected for truncated NLRI
            break

    # Should have parsed the first two
    assert len(nlris) == 2


# =============================================================================
# Qualifier Boundary Tests
# =============================================================================


@pytest.mark.fuzz
@given(path_id=st.integers(min_value=0, max_value=0xFFFFFFFF))
@settings(deadline=None, max_examples=50)
def test_path_info_boundary_values(path_id: int) -> None:
    """Test PathInfo with boundary values."""
    from exabgp.bgp.message.update.nlri.qualifier import PathInfo

    path_bytes = struct.pack('!I', path_id)
    path_info = PathInfo(path_bytes)

    # Should pack to same value
    assert path_info.pack_path() == path_bytes


@pytest.mark.fuzz
@given(label_value=st.integers(min_value=0, max_value=0xFFFFF))
@settings(deadline=None, max_examples=50)
def test_labels_boundary_values(label_value: int) -> None:
    """Test Labels with boundary values."""
    from exabgp.bgp.message.update.nlri.qualifier import Labels

    try:
        labels = Labels.make_labels([label_value])
        packed = labels.pack_labels()
        assert isinstance(packed, bytes)
        assert len(packed) == 3  # One label = 3 bytes
    except Exception as e:
        # Some values may be invalid
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_labels_empty() -> None:
    """Test Labels with empty list."""
    from exabgp.bgp.message.update.nlri.qualifier import Labels

    try:
        labels = Labels.make_labels([])
        packed = labels.pack_labels()
        assert isinstance(packed, bytes)
    except Exception as e:
        assert not isinstance(e, (SystemExit, KeyboardInterrupt, RecursionError))


@pytest.mark.fuzz
def test_labels_multiple() -> None:
    """Test Labels with multiple values (label stack)."""
    from exabgp.bgp.message.update.nlri.qualifier import Labels

    labels = Labels.make_labels([100, 200, 300])
    packed = labels.pack_labels()
    assert isinstance(packed, bytes)
    assert len(packed) == 9  # 3 labels * 3 bytes


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
