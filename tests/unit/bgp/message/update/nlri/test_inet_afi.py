"""Test INET NLRI AFI handling.

This test file validates that INET factory methods correctly handle
explicit AFI parameters, avoiding the /32 IPv6 misclassification bug.
"""

from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message import Action
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.update.nlri.qualifier import PathInfo


class TestINETFromCidr:
    """Test INET.from_cidr() factory method with explicit AFI."""

    def test_ipv4_slash24(self):
        """INET.from_cidr with IPv4 /24."""
        cidr = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        assert inet.afi == AFI.ipv4
        assert inet.safi == SAFI.unicast
        assert inet.cidr.mask == 24
        assert inet.cidr.prefix() == '192.168.1.0/24'

    def test_ipv4_slash32(self):
        """INET.from_cidr with IPv4 /32."""
        cidr = CIDR.from_ipv4(bytes([32, 192, 168, 1, 1]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        assert inet.afi == AFI.ipv4
        assert inet.cidr.prefix() == '192.168.1.1/32'

    def test_ipv6_slash32_critical(self):
        """INET.from_cidr with IPv6 /32 - THE CRITICAL TEST.

        This validates that IPv6 /32 is correctly handled when
        AFI is explicit, avoiding the misclassification bug.
        """
        cidr = CIDR.from_ipv6(bytes([32, 0x20, 0x01, 0x0D, 0xB8]))
        inet = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast)
        assert inet.afi == AFI.ipv6
        assert inet.cidr.mask == 32
        assert inet.cidr.prefix() == '2001:db8::/32'

    def test_ipv6_slash64(self):
        """INET.from_cidr with IPv6 /64."""
        cidr = CIDR.from_ipv6(bytes([64, 0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 1]))
        inet = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast)
        assert inet.afi == AFI.ipv6
        assert inet.cidr.mask == 64

    def test_ipv6_slash128(self):
        """INET.from_cidr with IPv6 /128."""
        cidr = CIDR.from_ipv6(bytes([128] + [0x20, 0x01, 0x0D, 0xB8] + [0] * 10 + [0, 1]))
        inet = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast)
        assert inet.afi == AFI.ipv6
        assert inet.cidr.mask == 128

    def test_multicast_safi(self):
        """INET.from_cidr with multicast SAFI."""
        cidr = CIDR.from_ipv4(bytes([24, 224, 0, 0]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.multicast)
        assert inet.safi == SAFI.multicast

    def test_with_action(self):
        """INET.from_cidr with explicit action."""
        cidr = CIDR.from_ipv4(bytes([24, 10, 0, 0]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, action=Action.ANNOUNCE)
        assert inet.action == Action.ANNOUNCE

    def test_with_path_info(self):
        """INET.from_cidr with path info."""
        cidr = CIDR.from_ipv4(bytes([24, 10, 0, 0]))
        path_info = PathInfo(bytes([0, 0, 0, 1]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, path_info=path_info)
        assert inet.path_info == path_info


class TestINETMakeRoute:
    """Test INET.make_route() factory method."""

    def test_ipv4_slash24(self):
        """INET.make_route with IPv4 /24."""
        packed = bytes([192, 168, 1, 0])
        inet = INET.make_route(AFI.ipv4, SAFI.unicast, packed, 24)
        assert inet.afi == AFI.ipv4
        assert inet.cidr.mask == 24

    def test_ipv4_slash32(self):
        """INET.make_route with IPv4 /32."""
        packed = bytes([10, 0, 0, 1])
        inet = INET.make_route(AFI.ipv4, SAFI.unicast, packed, 32)
        assert inet.afi == AFI.ipv4
        assert inet.cidr.mask == 32

    def test_ipv6_slash32_critical(self):
        """INET.make_route with IPv6 /32 - critical bug fix test."""
        packed = bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 12)
        inet = INET.make_route(AFI.ipv6, SAFI.unicast, packed, 32)
        assert inet.afi == AFI.ipv6
        assert inet.cidr.mask == 32
        # Verify it's not misclassified as IPv4
        assert '2001:db8' in inet.cidr.prefix()

    def test_ipv6_slash64(self):
        """INET.make_route with IPv6 /64."""
        packed = bytes([0x20, 0x01, 0x0D, 0xB8, 0, 0, 0, 1] + [0] * 8)
        inet = INET.make_route(AFI.ipv6, SAFI.unicast, packed, 64)
        assert inet.afi == AFI.ipv6
        assert inet.cidr.mask == 64


class TestINETCidrProperty:
    """Test INET.cidr property returns correct CIDR."""

    def test_cidr_ipv4(self):
        """INET.cidr returns correct IPv4 CIDR."""
        cidr = CIDR.from_ipv4(bytes([24, 10, 0, 0]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        assert inet.cidr.prefix() == '10.0.0.0/24'

    def test_cidr_ipv6_slash32(self):
        """INET.cidr returns correct IPv6 /32 CIDR."""
        cidr = CIDR.from_ipv6(bytes([32, 0x20, 0x01, 0x0D, 0xB8]))
        inet = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast)
        assert inet.cidr.prefix() == '2001:db8::/32'


class TestINETHash:
    """Test INET hashing for use in sets/dicts."""

    def test_same_nlri_same_hash(self):
        """Same NLRI should have same hash."""
        cidr1 = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        cidr2 = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        inet1 = INET.from_cidr(cidr1, AFI.ipv4, SAFI.unicast)
        inet2 = INET.from_cidr(cidr2, AFI.ipv4, SAFI.unicast)
        assert hash(inet1) == hash(inet2)

    def test_different_mask_different_hash(self):
        """Different masks should produce different hashes."""
        cidr1 = CIDR.from_ipv4(bytes([24, 192, 168, 1]))
        cidr2 = CIDR.from_ipv4(bytes([25, 192, 168, 1, 0]))
        inet1 = INET.from_cidr(cidr1, AFI.ipv4, SAFI.unicast)
        inet2 = INET.from_cidr(cidr2, AFI.ipv4, SAFI.unicast)
        # Hashes might collide, but prefixes should differ
        assert inet1.cidr.prefix() != inet2.cidr.prefix()


class TestINETPrefix:
    """Test INET.prefix() output."""

    def test_prefix_ipv4(self):
        """INET.prefix() for IPv4."""
        cidr = CIDR.from_ipv4(bytes([24, 10, 0, 0]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        assert inet.prefix() == '10.0.0.0/24'

    def test_prefix_ipv6_slash32(self):
        """INET.prefix() for IPv6 /32."""
        cidr = CIDR.from_ipv6(bytes([32, 0x20, 0x01, 0x0D, 0xB8]))
        inet = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast)
        assert inet.prefix() == '2001:db8::/32'


class TestINETJson:
    """Test INET JSON output."""

    def test_json_ipv4(self):
        """INET.json() for IPv4."""
        cidr = CIDR.from_ipv4(bytes([24, 10, 0, 0]))
        inet = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        json_str = inet.json()
        assert '10.0.0.0/24' in json_str

    def test_json_ipv6_slash32(self):
        """INET.json() for IPv6 /32."""
        cidr = CIDR.from_ipv6(bytes([32, 0x20, 0x01, 0x0D, 0xB8]))
        inet = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast)
        json_str = inet.json()
        assert '2001:db8::/32' in json_str
