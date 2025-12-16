"""Test CIDR AFI handling - ensure /32 IPv6 works correctly.

This test file validates the fix for the AFI inference bug where
IPv6 /32 prefixes were incorrectly classified as IPv4.

The bug was in the heuristic: `mask > 32 -> IPv6, else IPv4`
which fails for IPv6 prefixes with masks 0-32.
"""

import pytest

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.protocol.family import AFI


class TestCIDRFromIPv4:
    """Test CIDR.from_ipv4() factory method."""

    def test_slash0(self):
        """IPv4 /0 (default route)."""
        nlri = bytes([0])  # mask=0, no address bytes
        cidr = CIDR.from_ipv4(nlri)
        assert cidr.mask == 0
        assert cidr.prefix() == '0.0.0.0/0'

    def test_slash1(self):
        """IPv4 /1."""
        nlri = bytes([1, 0])  # 0.0.0.0/1
        cidr = CIDR.from_ipv4(nlri)
        assert cidr.mask == 1
        assert cidr.prefix() == '0.0.0.0/1'

    def test_slash8(self):
        """IPv4 /8."""
        nlri = bytes([8, 10])  # 10.0.0.0/8
        cidr = CIDR.from_ipv4(nlri)
        assert cidr.mask == 8
        assert cidr.prefix() == '10.0.0.0/8'

    def test_slash16(self):
        """IPv4 /16."""
        nlri = bytes([16, 172, 16])  # 172.16.0.0/16
        cidr = CIDR.from_ipv4(nlri)
        assert cidr.mask == 16
        assert cidr.prefix() == '172.16.0.0/16'

    def test_slash24(self):
        """IPv4 /24."""
        nlri = bytes([24, 192, 168, 1])  # 192.168.1.0/24
        cidr = CIDR.from_ipv4(nlri)
        assert cidr.mask == 24
        assert cidr.prefix() == '192.168.1.0/24'

    def test_slash32(self):
        """IPv4 /32 (host route)."""
        nlri = bytes([32, 192, 168, 1, 1])  # 192.168.1.1/32
        cidr = CIDR.from_ipv4(nlri)
        assert cidr.mask == 32
        assert cidr.prefix() == '192.168.1.1/32'

    def test_slash25(self):
        """IPv4 /25 (non-byte-aligned)."""
        nlri = bytes([25, 10, 0, 0, 128])  # 10.0.0.128/25
        cidr = CIDR.from_ipv4(nlri)
        assert cidr.mask == 25
        assert cidr.prefix() == '10.0.0.128/25'


class TestCIDRFromIPv6:
    """Test CIDR.from_ipv6() factory method - critical for /32 bug fix."""

    def test_slash0(self):
        """IPv6 /0 (default route)."""
        nlri = bytes([0])  # mask=0, no address bytes
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 0
        assert cidr.prefix() == '::/0'

    def test_slash1(self):
        """IPv6 /1."""
        nlri = bytes([1, 0])  # ::/1
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 1
        assert cidr.prefix() == '::/1'

    def test_slash32_critical(self):
        """IPv6 /32 - THE CRITICAL TEST (was buggy).

        This test ensures that 2001:db8::/32 is correctly identified
        as IPv6, not misclassified as IPv4 due to the mask <= 32.
        """
        # 2001:db8::/32 -> mask=32, 4 bytes of address
        nlri = bytes([32, 0x20, 0x01, 0x0D, 0xB8])
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 32
        assert cidr.prefix() == '2001:db8::/32'

    def test_slash48(self):
        """IPv6 /48 (common allocation size)."""
        # 2001:db8:1234::/48
        nlri = bytes([48, 0x20, 0x01, 0x0D, 0xB8, 0x12, 0x34])
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 48
        assert cidr.prefix() == '2001:db8:1234::/48'

    def test_slash64(self):
        """IPv6 /64 (common prefix length for LANs)."""
        nlri = bytes([64, 0x20, 0x01, 0x0D, 0xB8, 0x00, 0x00, 0x00, 0x01])
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 64
        assert '2001:db8:0:1::/64' in cidr.prefix()

    def test_slash128(self):
        """IPv6 /128 (host route)."""
        # 2001:db8::1/128 - full 16 bytes
        nlri = bytes([128] + [0x20, 0x01, 0x0D, 0xB8] + [0] * 10 + [0, 1])
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 128
        assert '2001:db8::1/128' in cidr.prefix()

    def test_slash8(self):
        """IPv6 /8 (very short prefix, also ambiguous like /32)."""
        # 2000::/8
        nlri = bytes([8, 0x20])
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 8
        assert '2000::/8' in cidr.prefix()

    def test_slash16(self):
        """IPv6 /16 (ambiguous with IPv4)."""
        # 2001::/16
        nlri = bytes([16, 0x20, 0x01])
        cidr = CIDR.from_ipv6(nlri)
        assert cidr.mask == 16
        assert '2001::/16' in cidr.prefix()


class TestCIDRMakeCidr:
    """Test CIDR.create_cidr() factory with full address bytes."""

    def test_ipv4_slash32(self):
        """make_cidr with IPv4 full address."""
        packed = bytes([192, 168, 1, 1])
        cidr = CIDR.create_cidr(packed, 32)
        assert cidr.mask == 32
        assert cidr.prefix() == '192.168.1.1/32'

    def test_ipv4_slash24(self):
        """make_cidr with IPv4 /24."""
        packed = bytes([10, 0, 0, 0])
        cidr = CIDR.create_cidr(packed, 24)
        assert cidr.mask == 24
        assert cidr.prefix() == '10.0.0.0/24'

    def test_ipv6_slash32(self):
        """make_cidr with IPv6 full address and /32 mask."""
        packed = bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12)
        cidr = CIDR.create_cidr(packed, 32)
        assert cidr.mask == 32
        # make_cidr stores full 16 bytes, prefix() will show IPv6 format
        assert '2001:db8::/32' in cidr.prefix()

    def test_ipv6_slash64(self):
        """make_cidr with IPv6 /64."""
        packed = bytes([0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 1] + [0] * 8)
        cidr = CIDR.create_cidr(packed, 64)
        assert cidr.mask == 64

    def test_invalid_length_raises(self):
        """make_cidr rejects invalid packed length."""
        with pytest.raises(ValueError, match='must be 4 or 16 bytes'):
            CIDR.create_cidr(bytes([1, 2, 3]), 24)  # 3 bytes invalid

    def test_invalid_ipv4_mask_raises(self):
        """make_cidr rejects mask > 32 for IPv4."""
        with pytest.raises(ValueError, match='must be 0-32'):
            CIDR.create_cidr(bytes([192, 168, 1, 1]), 33)

    def test_invalid_ipv6_mask_raises(self):
        """make_cidr rejects mask > 128 for IPv6."""
        with pytest.raises(ValueError, match='must be 0-128'):
            CIDR.create_cidr(bytes([0x20, 0x01] + [0] * 14), 129)


class TestCIDRConstructorWithAFI:
    """Test CIDR() constructor with explicit AFI parameter."""

    def test_ipv4_explicit(self):
        """CIDR() with explicit IPv4 AFI."""
        nlri = bytes([32, 192, 168, 1, 1])
        cidr = CIDR(nlri, AFI.ipv4)
        assert cidr.mask == 32
        assert cidr.prefix() == '192.168.1.1/32'

    def test_ipv6_explicit(self):
        """CIDR() with explicit IPv6 AFI."""
        nlri = bytes([32, 0x20, 0x01, 0x0D, 0xB8])
        cidr = CIDR(nlri, AFI.ipv6)
        assert cidr.mask == 32
        assert cidr.prefix() == '2001:db8::/32'

    def test_ipv6_slash32_not_misidentified_as_ipv4(self):
        """Explicit AFI prevents /32 IPv6 from being treated as IPv4.

        This is the core of the bug fix: when AFI is explicit,
        we don't rely on the flawed heuristic.
        """
        nlri = bytes([32, 0x20, 0x01, 0x0D, 0xB8])
        cidr_v6 = CIDR(nlri, AFI.ipv6)
        cidr_v4 = CIDR(nlri, AFI.ipv4)

        # Same wire bytes, different interpretation
        assert cidr_v6.prefix() == '2001:db8::/32'
        assert cidr_v4.prefix() == '32.1.13.184/32'  # Misinterpretation as IPv4


class TestCIDRPackNlri:
    """Test CIDR wire format packing."""

    def test_pack_nlri_ipv4_slash24(self):
        """pack_nlri for IPv4 /24."""
        cidr = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        packed = cidr.pack_nlri()
        assert packed == bytes([24, 192, 168, 1])

    def test_pack_nlri_ipv4_slash32(self):
        """pack_nlri for IPv4 /32."""
        cidr = CIDR.from_ipv4(bytes([32, 10, 0, 0, 1]))
        packed = cidr.pack_nlri()
        assert packed == bytes([32, 10, 0, 0, 1])

    def test_pack_nlri_ipv6_slash32(self):
        """pack_nlri for IPv6 /32."""
        cidr = CIDR.from_ipv6(bytes([32, 0x20, 0x01, 0x0D, 0xB8]))
        packed = cidr.pack_nlri()
        assert packed == bytes([32, 0x20, 0x01, 0x0D, 0xB8])

    def test_pack_nlri_ipv6_slash48(self):
        """pack_nlri for IPv6 /48."""
        cidr = CIDR.from_ipv6(bytes([48, 0x20, 0x01, 0x0D, 0xB8, 0x12, 0x34]))
        packed = cidr.pack_nlri()
        assert packed == bytes([48, 0x20, 0x01, 0x0D, 0xB8, 0x12, 0x34])


class TestCIDRUnpackCidr:
    """Test CIDR.unpack_cidr() class method."""

    def test_unpack_ipv4(self):
        """unpack_cidr with IPv4 data."""
        data = bytes([24, 192, 168, 1])
        cidr = CIDR.unpack_cidr(data, AFI.ipv4)
        assert cidr.mask == 24
        assert cidr.prefix() == '192.168.1.0/24'

    def test_unpack_ipv6(self):
        """unpack_cidr with IPv6 data."""
        data = bytes([32, 0x20, 0x01, 0x0D, 0xB8])
        cidr = CIDR.unpack_cidr(data, AFI.ipv6)
        assert cidr.mask == 32
        assert cidr.prefix() == '2001:db8::/32'


class TestCIDREquality:
    """Test CIDR equality comparisons."""

    def test_same_prefix_equal(self):
        """Same prefix should be equal."""
        cidr1 = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        cidr2 = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        assert cidr1 == cidr2

    def test_different_mask_not_equal(self):
        """Different masks should not be equal."""
        cidr1 = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        cidr2 = CIDR.from_ipv4(bytes([25, 192, 168, 1, 0]))
        assert cidr1 != cidr2

    def test_ipv4_ipv6_same_bytes_not_equal(self):
        """IPv4 and IPv6 with same bytes are different CIDRs."""
        data = bytes([32, 0x20, 0x01, 0x0D, 0xB8])
        cidr_v4 = CIDR(data, AFI.ipv4)
        cidr_v6 = CIDR(data, AFI.ipv6)
        # Different packed representations (IPv6 is zero-padded to 16 bytes)
        assert cidr_v4 != cidr_v6
