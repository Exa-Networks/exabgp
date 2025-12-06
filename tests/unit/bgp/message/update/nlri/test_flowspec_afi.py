"""Test FlowSpec NLRI AFI handling.

This test file validates that FlowSpec IPrefix4 and IPrefix6 classes
correctly handle their CIDR properties with explicit AFI, avoiding
the /32 IPv6 misclassification bug.

The bug: IPrefix6.cidr used CIDR(self._packed) which relied on
the faulty heuristic `mask > 32 -> IPv6`. With /32 masks, IPv6
prefixes were misclassified as IPv4.

The fix: IPrefix4.cidr uses CIDR.from_ipv4() and
IPrefix6.cidr uses CIDR.from_ipv6().
"""

from exabgp.bgp.message.update.nlri.flow import (
    IPrefix4,
    IPrefix6,
    Flow4Destination,
    Flow4Source,
    Flow6Destination,
    Flow6Source,
)


class TestIPrefix4:
    """Test IPrefix4 (IPv4 FlowSpec prefix) CIDR handling."""

    def test_cidr_property_slash8(self):
        """IPrefix4.cidr returns correct IPv4 CIDR for /8."""
        prefix = IPrefix4.make_prefix4(bytes([10, 0, 0, 0]), 8)
        cidr = prefix.cidr
        assert cidr.mask == 8
        assert cidr.prefix() == '10.0.0.0/8'

    def test_cidr_property_slash24(self):
        """IPrefix4.cidr returns correct IPv4 CIDR for /24."""
        prefix = IPrefix4.make_prefix4(bytes([192, 168, 1, 0]), 24)
        cidr = prefix.cidr
        assert cidr.mask == 24
        assert cidr.prefix() == '192.168.1.0/24'

    def test_cidr_property_slash32(self):
        """IPrefix4.cidr returns correct IPv4 CIDR for /32."""
        prefix = IPrefix4.make_prefix4(bytes([192, 168, 1, 1]), 32)
        cidr = prefix.cidr
        assert cidr.mask == 32
        assert cidr.prefix() == '192.168.1.1/32'

    def test_make_parses_wire_format(self):
        """IPrefix4.make parses wire format correctly."""
        # Wire format: [mask][truncated_ip...]
        bgp = bytes([24, 10, 0, 0])
        prefix, remaining = IPrefix4.make(bgp)
        assert prefix.cidr.mask == 24
        assert prefix.cidr.prefix() == '10.0.0.0/24'
        assert remaining == b''

    def test_make_slash32(self):
        """IPrefix4.make parses /32 wire format correctly."""
        bgp = bytes([32, 192, 168, 1, 1])
        prefix, remaining = IPrefix4.make(bgp)
        assert prefix.cidr.mask == 32
        assert prefix.cidr.prefix() == '192.168.1.1/32'

    def test_pack(self):
        """Flow4Destination.pack produces correct wire format."""
        # Use concrete subclass Flow4Destination which has ID
        prefix = Flow4Destination.make_prefix4(bytes([192, 168, 1, 0]), 24)
        packed = prefix.pack()
        # Wire format: [ID][mask][truncated_ip...]
        assert packed[0] == Flow4Destination.ID  # First byte is type ID (0x01)
        assert packed[1:] == bytes([24, 192, 168, 1])

    def test_short(self):
        """IPrefix4.short returns CIDR string."""
        prefix = IPrefix4.make_prefix4(bytes([10, 0, 0, 0]), 8)
        assert prefix.short() == '10.0.0.0/8'


class TestIPrefix6:
    """Test IPrefix6 (IPv6 FlowSpec prefix) CIDR handling - critical for bug fix."""

    def test_cidr_property_slash32_critical(self):
        """IPrefix6.cidr with /32 returns IPv6 CIDR (was buggy).

        This is THE critical test for the AFI inference bug.
        A /32 IPv6 prefix must NOT be misclassified as IPv4.
        """
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12),
            32,
            0,  # offset
        )
        cidr = prefix.cidr
        assert cidr.mask == 32
        # CRITICAL: Must be IPv6, not IPv4 (32.1.13.184/32)!
        assert '2001:db8' in cidr.prefix()
        assert cidr.prefix() == '2001:db8::/32'

    def test_cidr_property_slash48(self):
        """IPrefix6.cidr returns correct IPv6 CIDR for /48."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8, 0x12, 0x34] + [0] * 10),
            48,
            0,
        )
        cidr = prefix.cidr
        assert cidr.mask == 48
        assert '2001:db8:1234::/48' in cidr.prefix()

    def test_cidr_property_slash64(self):
        """IPrefix6.cidr returns correct IPv6 CIDR for /64."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 1] + [0] * 8),
            64,
            0,
        )
        cidr = prefix.cidr
        assert cidr.mask == 64
        assert '2001:db8:0:1::/64' in cidr.prefix()

    def test_cidr_property_slash128(self):
        """IPrefix6.cidr returns correct IPv6 CIDR for /128."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 10 + [0, 1]),
            128,
            0,
        )
        cidr = prefix.cidr
        assert cidr.mask == 128
        assert '2001:db8::1/128' in cidr.prefix()

    def test_make_slash32_critical(self):
        """IPrefix6.make with /32 parses as IPv6 (was buggy).

        Wire format: [mask][offset][ip...]
        """
        # 2001:db8::/32 with offset=0
        bgp = bytes([32, 0, 0x20, 0x01, 0x0D, 0xB8])
        prefix, remaining = IPrefix6.make(bgp)
        assert prefix.cidr.mask == 32
        # CRITICAL: Must be IPv6!
        assert '2001:db8' in prefix.cidr.prefix()
        assert remaining == b''

    def test_make_slash64(self):
        """IPrefix6.make parses /64 wire format correctly."""
        # Wire format: [mask][offset][ip...]
        bgp = bytes([64, 0, 0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 1])
        prefix, remaining = IPrefix6.make(bgp)
        assert prefix.cidr.mask == 64
        assert '2001:db8:0:1::/64' in prefix.cidr.prefix()

    def test_offset_property(self):
        """IPrefix6.offset returns correct offset value."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12),
            32,
            8,  # offset=8
        )
        assert prefix.offset == 8

    def test_pack(self):
        """Flow6Destination.pack produces correct wire format with offset."""
        # Use concrete subclass Flow6Destination which has ID
        prefix = Flow6Destination.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12),
            32,
            4,  # offset=4
        )
        packed = prefix.pack()
        # Wire format: [ID][mask][offset][ip...]
        assert packed[0] == Flow6Destination.ID  # Type ID (0x01)
        assert packed[1] == 32  # mask
        assert packed[2] == 4  # offset
        assert packed[3:7] == bytes([0x20, 0x01, 0x0D, 0xB8])

    def test_short_includes_offset(self):
        """IPrefix6.short includes offset in output."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12),
            32,
            8,
        )
        short = prefix.short()
        assert '2001:db8::/32' in short
        assert '/8' in short  # offset suffix


class TestFlow4Destination:
    """Test Flow4Destination (IPv4 FlowSpec destination prefix)."""

    def test_cidr_property(self):
        """Flow4Destination.cidr returns correct IPv4 CIDR."""
        prefix = Flow4Destination.make_prefix4(bytes([10, 0, 0, 0]), 8)
        cidr = prefix.cidr
        assert cidr.prefix() == '10.0.0.0/8'

    def test_id(self):
        """Flow4Destination has correct type ID."""
        assert Flow4Destination.ID == 0x01


class TestFlow4Source:
    """Test Flow4Source (IPv4 FlowSpec source prefix)."""

    def test_cidr_property(self):
        """Flow4Source.cidr returns correct IPv4 CIDR."""
        prefix = Flow4Source.make_prefix4(bytes([192, 168, 0, 0]), 16)
        cidr = prefix.cidr
        assert cidr.prefix() == '192.168.0.0/16'

    def test_id(self):
        """Flow4Source has correct type ID."""
        assert Flow4Source.ID == 0x02


class TestFlow6Destination:
    """Test Flow6Destination (IPv6 FlowSpec destination prefix) - critical."""

    def test_cidr_property_slash32(self):
        """Flow6Destination.cidr with /32 returns IPv6 CIDR (was buggy)."""
        prefix = Flow6Destination.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12),
            32,
            0,
        )
        cidr = prefix.cidr
        assert cidr.prefix() == '2001:db8::/32'

    def test_id(self):
        """Flow6Destination has correct type ID."""
        assert Flow6Destination.ID == 0x01


class TestFlow6Source:
    """Test Flow6Source (IPv6 FlowSpec source prefix) - critical."""

    def test_cidr_property_slash32(self):
        """Flow6Source.cidr with /32 returns IPv6 CIDR (was buggy)."""
        prefix = Flow6Source.make_prefix6(
            bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12),
            32,
            0,
        )
        cidr = prefix.cidr
        assert cidr.prefix() == '2001:db8::/32'

    def test_id(self):
        """Flow6Source has correct type ID."""
        assert Flow6Source.ID == 0x02


class TestEdgeCases:
    """Test edge cases for FlowSpec prefix handling."""

    def test_ipv6_slash8_ambiguous(self):
        """IPv6 /8 is ambiguous but should work with explicit factory."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20] + [0] * 15),
            8,
            0,
        )
        cidr = prefix.cidr
        assert cidr.mask == 8
        # Should be interpreted as IPv6, not IPv4 10.x.x.x/8
        assert '2000::/8' in cidr.prefix()

    def test_ipv6_slash16_ambiguous(self):
        """IPv6 /16 is ambiguous but should work with explicit factory."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01] + [0] * 14),
            16,
            0,
        )
        cidr = prefix.cidr
        assert cidr.mask == 16
        assert '2001::/16' in cidr.prefix()

    def test_ipv6_slash24_ambiguous(self):
        """IPv6 /24 is ambiguous but should work with explicit factory."""
        prefix = IPrefix6.make_prefix6(
            bytes([0x20, 0x01, 0x0D] + [0] * 13),
            24,
            0,
        )
        cidr = prefix.cidr
        assert cidr.mask == 24
        assert '2001:d00::/24' in cidr.prefix()

    def test_ipv4_slash0_default_route(self):
        """IPv4 /0 default route."""
        prefix = IPrefix4.make_prefix4(bytes([0, 0, 0, 0]), 0)
        cidr = prefix.cidr
        assert cidr.mask == 0
        assert cidr.prefix() == '0.0.0.0/0'

    def test_ipv6_slash0_default_route(self):
        """IPv6 /0 default route."""
        prefix = IPrefix6.make_prefix6(bytes([0] * 16), 0, 0)
        cidr = prefix.cidr
        assert cidr.mask == 0
        assert cidr.prefix() == '::/0'
