"""Tests for protocol/family.py - Family, AFI, SAFI classes."""

from exabgp.protocol.family import AFI, SAFI, Family


class TestFamilyAllFamilies:
    """Tests for Family.all_families() classmethod."""

    def test_all_families_returns_list(self):
        """all_families() should return a list."""
        result = Family.all_families()
        assert isinstance(result, list)

    def test_all_families_returns_tuples(self):
        """all_families() should return list of (AFI, SAFI) tuples."""
        result = Family.all_families()
        assert len(result) > 0
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], AFI)
            assert isinstance(item[1], SAFI)

    def test_all_families_contains_ipv4_unicast(self):
        """all_families() should contain IPv4 unicast."""
        result = Family.all_families()
        assert (AFI.ipv4, SAFI.unicast) in result

    def test_all_families_contains_ipv6_unicast(self):
        """all_families() should contain IPv6 unicast."""
        result = Family.all_families()
        assert (AFI.ipv6, SAFI.unicast) in result

    def test_all_families_contains_evpn(self):
        """all_families() should contain L2VPN EVPN."""
        result = Family.all_families()
        assert (AFI.l2vpn, SAFI.evpn) in result

    def test_all_families_matches_size_keys(self):
        """all_families() should return exactly the keys from Family.size."""
        result = Family.all_families()
        expected = list(Family.size.keys())
        assert sorted(result, key=lambda x: (int(x[0]), int(x[1]))) == sorted(
            expected, key=lambda x: (int(x[0]), int(x[1]))
        )

    def test_all_families_count(self):
        """all_families() should have expected number of families."""
        result = Family.all_families()
        # Family.size has 19 entries based on the code
        assert len(result) == len(Family.size)
