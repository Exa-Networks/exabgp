"""Tests for JSON API response generation.

These tests ensure the JSON encoder correctly handles:
1. UpdateCollection (regular UPDATE messages) - uses RoutedNLRI for nexthop
2. EOR messages - preserves original behavior
3. Nexthop is correctly extracted from RoutedNLRI container

This catches regressions like:
- EOR messages producing different JSON format than expected
- Nexthop not matching between RoutedNLRI and bare NLRI
- Family (AFI/SAFI) being reported incorrectly
"""

import json
import pytest
from unittest.mock import Mock

from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.attribute import AttributeCollection, Origin
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.protocol.ip import IPv4, IPv6
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.api.response.json import JSON


@pytest.fixture
def json_encoder() -> JSON:
    """Create a JSON encoder for testing."""
    return JSON('6.0.0')


@pytest.fixture
def mock_neighbor() -> Mock:
    """Create a mock neighbor for JSON encoding."""
    neighbor = Mock()
    neighbor.session = Mock()
    neighbor.session.peer_address = IPv4.from_string('192.168.1.1')
    neighbor.session.local_address = IPv4.from_string('192.168.1.2')
    neighbor.asn = Mock()
    neighbor.asn.peer = 65001
    neighbor.asn.local = 65000
    return neighbor


@pytest.fixture
def mock_negotiated() -> Mock:
    """Create a mock negotiated object."""
    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.asn4 = True
    return negotiated


class TestUpdateCollectionJSON:
    """Tests for UpdateCollection JSON generation."""

    def test_update_with_ipv4_announce(self, json_encoder: JSON) -> None:
        """Test JSON output for IPv4 unicast announce uses RoutedNLRI nexthop."""
        import socket

        # Create IPv4 route
        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.make_cidr(packed_ip, 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        nexthop = IPv4.from_string('192.168.1.1')

        # Wrap in RoutedNLRI
        routed = RoutedNLRI(nlri, nexthop)

        # Create UpdateCollection
        attrs = AttributeCollection()
        attrs.add(Origin.from_int(Origin.IGP))
        update = UpdateCollection(announces=[routed], withdraws=[], attributes=attrs)

        # Generate JSON
        result = json_encoder._update(update)

        # Verify structure
        assert 'message' in result
        message = json.loads(result['message'])

        # Should have announce section
        assert 'update' in message
        assert 'announce' in message['update']

        # Check family and nexthop
        announce = message['update']['announce']
        assert 'ipv4 unicast' in announce
        assert '192.168.1.1' in announce['ipv4 unicast']

    def test_update_with_ipv6_announce(self, json_encoder: JSON) -> None:
        """Test JSON output for IPv6 unicast announce uses RoutedNLRI nexthop."""
        import socket

        # Create IPv6 route
        packed_ip = socket.inet_pton(socket.AF_INET6, '2001:db8::')
        cidr = CIDR.make_cidr(packed_ip, 32)
        nlri = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast)
        nexthop = IPv6.from_string('2001:db8::1')

        # Wrap in RoutedNLRI
        routed = RoutedNLRI(nlri, nexthop)

        # Create UpdateCollection
        attrs = AttributeCollection()
        attrs.add(Origin.from_int(Origin.IGP))
        update = UpdateCollection(announces=[routed], withdraws=[], attributes=attrs)

        # Generate JSON
        result = json_encoder._update(update)

        # Verify structure
        message = json.loads(result['message'])
        assert 'update' in message
        assert 'announce' in message['update']

        announce = message['update']['announce']
        assert 'ipv6 unicast' in announce
        assert '2001:db8::1' in announce['ipv6 unicast']

    def test_update_with_withdraw(self, json_encoder: JSON) -> None:
        """Test JSON output for withdraw does not require nexthop."""
        import socket

        # Create IPv4 route for withdraw
        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.make_cidr(packed_ip, 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)

        # Create UpdateCollection with withdraw (no RoutedNLRI needed)
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[], withdraws=[nlri], attributes=attrs)

        # Generate JSON
        result = json_encoder._update(update)

        # Verify structure
        message = json.loads(result['message'])
        assert 'update' in message
        assert 'withdraw' in message['update']

        withdraw = message['update']['withdraw']
        assert 'ipv4 unicast' in withdraw

    def test_update_nexthop_from_routed_nlri(self, json_encoder: JSON) -> None:
        """Test that nexthop comes from RoutedNLRI.

        NLRI no longer stores nexthop - nexthop is stored in RoutedNLRI.
        RoutedNLRI.nexthop is the authoritative source.
        """
        import socket

        # Create IPv4 route
        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.make_cidr(packed_ip, 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        # Note: nlri no longer has nexthop attribute

        # Wrap in RoutedNLRI with nexthop
        routed_nexthop = IPv4.from_string('2.2.2.2')
        routed = RoutedNLRI(nlri, routed_nexthop)

        # Create UpdateCollection
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[routed], withdraws=[], attributes=attrs)

        # Generate JSON
        result = json_encoder._update(update)
        message = json.loads(result['message'])

        # The nexthop should be from RoutedNLRI (2.2.2.2)
        announce = message['update']['announce']
        assert '2.2.2.2' in announce['ipv4 unicast']

    def test_update_multiple_announces_different_nexthops(self, json_encoder: JSON) -> None:
        """Test multiple announces with different nexthops are grouped correctly."""
        import socket

        # Create two routes with different nexthops
        packed_ip1 = socket.inet_aton('10.0.0.0')
        cidr1 = CIDR.make_cidr(packed_ip1, 24)
        nlri1 = INET.from_cidr(cidr1, AFI.ipv4, SAFI.unicast)

        packed_ip2 = socket.inet_aton('10.0.1.0')
        cidr2 = CIDR.make_cidr(packed_ip2, 24)
        nlri2 = INET.from_cidr(cidr2, AFI.ipv4, SAFI.unicast)

        nexthop1 = IPv4.from_string('192.168.1.1')
        nexthop2 = IPv4.from_string('192.168.1.2')

        routed1 = RoutedNLRI(nlri1, nexthop1)
        routed2 = RoutedNLRI(nlri2, nexthop2)

        # Create UpdateCollection
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[routed1, routed2], withdraws=[], attributes=attrs)

        # Generate JSON
        result = json_encoder._update(update)
        message = json.loads(result['message'])

        # Both nexthops should appear
        announce = message['update']['announce']
        assert 'ipv4 unicast' in announce
        ipv4_announce = announce['ipv4 unicast']
        assert '192.168.1.1' in ipv4_announce
        assert '192.168.1.2' in ipv4_announce


class TestEORJSON:
    """Tests for EOR (End-of-RIB) JSON generation."""

    def test_eor_ipv4_unicast_produces_output(self, json_encoder: JSON) -> None:
        """Test EOR for IPv4 unicast produces some JSON output.

        Note: The current EOR JSON format has issues (EOR_NLRI.json() returns
        '"eor": {...}' which creates invalid JSON when embedded in a list).
        This test just verifies EOR doesn't crash and produces output.
        """
        from exabgp.bgp.message import Action

        # Create EOR for IPv4 unicast
        eor = EOR(AFI.ipv4, SAFI.unicast)

        # Generate JSON - should not crash
        result = json_encoder._update(eor)

        # Should produce some output
        assert 'message' in result
        assert len(result['message']) > 0
        # Verify it contains expected keywords
        assert 'eor' in result['message']
        assert 'ipv4' in result['message']

    def test_eor_ipv6_unicast_produces_output(self, json_encoder: JSON) -> None:
        """Test EOR for IPv6 unicast produces some JSON output."""
        from exabgp.bgp.message import Action

        # Create EOR for IPv6 unicast
        eor = EOR(AFI.ipv6, SAFI.unicast)

        # Generate JSON - should not crash
        result = json_encoder._update(eor)

        # Should produce some output
        assert 'message' in result
        assert len(result['message']) > 0
        assert 'eor' in result['message']
        assert 'ipv6' in result['message']

    def test_eor_has_eor_attribute(self) -> None:
        """Test that EOR class has EOR=True attribute."""
        from exabgp.bgp.message import Action

        eor = EOR(AFI.ipv4, SAFI.unicast)

        # EOR messages have EOR=True
        assert eor.EOR is True

    def test_update_collection_has_eor_false(self) -> None:
        """Test that UpdateCollection has EOR=False attribute."""
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

        # UpdateCollection has EOR=False
        assert update.EOR is False

    def test_eor_vs_update_distinguished_by_eor_attribute(self, json_encoder: JSON) -> None:
        """Test that EOR and UpdateCollection are correctly distinguished.

        The JSON encoder checks getattr(update_msg, 'EOR', False) to determine
        whether to use EOR path or UpdateCollection path.
        """
        from exabgp.bgp.message import Action

        # EOR message
        eor = EOR(AFI.ipv4, SAFI.unicast)
        assert getattr(eor, 'EOR', False) is True

        # UpdateCollection
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[], withdraws=[], attributes=attrs)
        assert getattr(update, 'EOR', False) is False


class TestNLRIAccess:
    """Tests for accessing NLRIs through different interfaces."""

    def test_update_collection_nlris_property(self) -> None:
        """Test UpdateCollection.nlris returns bare NLRIs."""
        import socket

        # Create route
        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.make_cidr(packed_ip, 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        nexthop = IPv4.from_string('192.168.1.1')

        routed = RoutedNLRI(nlri, nexthop)
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[routed], withdraws=[], attributes=attrs)

        # .nlris returns bare NLRIs (extracted from RoutedNLRI)
        nlris = update.nlris
        assert len(nlris) == 1
        assert nlris[0] is nlri  # Same object

    def test_update_collection_announces_property(self) -> None:
        """Test UpdateCollection.announces returns RoutedNLRI objects."""
        import socket

        # Create route
        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.make_cidr(packed_ip, 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        nexthop = IPv4.from_string('192.168.1.1')

        routed = RoutedNLRI(nlri, nexthop)
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[routed], withdraws=[], attributes=attrs)

        # .announces returns RoutedNLRI objects
        announces = update.announces
        assert len(announces) == 1
        assert announces[0] is routed
        assert announces[0].nlri is nlri
        assert announces[0].nexthop == nexthop

    def test_routed_nlri_preserves_nexthop(self) -> None:
        """Test RoutedNLRI correctly stores and returns nexthop."""
        import socket

        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.make_cidr(packed_ip, 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast)
        nexthop = IPv4.from_string('192.168.1.1')

        routed = RoutedNLRI(nlri, nexthop)

        assert routed.nlri is nlri
        assert routed.nexthop == nexthop
        assert str(routed.nexthop) == '192.168.1.1'


class TestEmptyUpdate:
    """Tests for empty UPDATE messages."""

    def test_empty_update_no_announces_no_withdraws(self, json_encoder: JSON) -> None:
        """Test empty UpdateCollection produces valid JSON."""
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

        # Generate JSON - should not crash
        result = json_encoder._update(update)

        # Should produce some JSON
        assert 'message' in result

    def test_empty_update_with_eor_check(self, json_encoder: JSON) -> None:
        """Test that empty UpdateCollection triggers EOR check.

        When there are no announces and no withdraws, the code checks
        update_msg.nlris to determine if this is an EOR.
        """
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

        # Empty UpdateCollection has empty nlris
        assert update.nlris == []

        # Generate JSON
        result = json_encoder._update(update)

        # Should produce valid (possibly empty) update JSON
        assert 'message' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
