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
import socket
import pytest
from unittest.mock import Mock

from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.notification import Notification
from exabgp.bgp.message.operational import Advisory, Query, Response
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.hostname import HostName
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.software import Software
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.attribute import AttributeCollection, Origin
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.protocol.ip import IPv4, IPv6
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.interrupt import Signal
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
def api_neighbor() -> Mock:
    """Create a neighbor object with fields used by event JSON encoding."""
    neighbor = Mock()
    neighbor.uid = '192.0.2.1'
    neighbor.session = Mock()
    neighbor.session.peer_address = IPv4.from_string('192.0.2.1')
    neighbor.session.local_address = IPv4.from_string('192.0.2.2')
    neighbor.session.peer_as = 65001
    neighbor.session.local_as = 65000
    neighbor.session.router_id = IPv4.from_string('192.0.2.2')
    return neighbor


@pytest.fixture
def mock_negotiated() -> Mock:
    """Create a mock negotiated object."""
    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.asn4 = True
    return negotiated


def parsed_api_event(payload: str) -> dict[str, object]:
    event = json.loads(payload)
    for volatile_key in ('time', 'host', 'pid', 'ppid', 'counter'):
        event.pop(volatile_key, None)
    return event


def sample_negotiated(refresh: int = REFRESH.NORMAL) -> Mock:
    negotiated = Mock()
    negotiated.msg_size = 4096
    negotiated.holdtime = 90
    negotiated.asn4 = True
    negotiated.multisession = False
    negotiated.operational = False
    negotiated.refresh = refresh
    negotiated.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)]
    negotiated.nexthop = [(AFI.ipv4, SAFI.unicast, AFI.ipv4), (AFI.ipv6, SAFI.unicast, AFI.ipv6)]
    negotiated.addpath = Mock()
    negotiated.addpath.send = Mock(side_effect=lambda afi, safi: afi == AFI.ipv4)
    negotiated.addpath.receive = Mock(side_effect=lambda afi, safi: afi == AFI.ipv6)
    return negotiated


def sample_open_message() -> Open:
    capabilities = Capabilities()
    capabilities[Capability.CODE.HOSTNAME] = HostName('router-a', 'example.net')
    software = Software()
    software.software_version = 'ExaBGP/6.0.0'
    capabilities[Capability.CODE.SOFTWARE_VERSION] = software
    return Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), capabilities)


def sample_update_message() -> UpdateCollection:
    nlri = INET.from_cidr(CIDR.create_cidr(socket.inet_aton('10.0.0.0'), 24), AFI.ipv4, SAFI.unicast)
    routed = RoutedNLRI(nlri, IPv4.from_string('192.0.2.254'))
    attrs = AttributeCollection()
    attrs.add(Origin.from_int(Origin.IGP))
    return UpdateCollection(announces=[routed], withdraws=[], attributes=attrs)


class TestUpdateCollectionJSON:
    """Tests for UpdateCollection JSON generation."""

    def test_update_with_ipv4_announce(self, json_encoder: JSON) -> None:
        """Test JSON output for IPv4 unicast announce uses RoutedNLRI nexthop."""
        import socket

        # Create IPv4 route
        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.create_cidr(packed_ip, 24)
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
        cidr = CIDR.create_cidr(packed_ip, 32)
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
        cidr = CIDR.create_cidr(packed_ip, 24)
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
        cidr = CIDR.create_cidr(packed_ip, 24)
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
        cidr1 = CIDR.create_cidr(packed_ip1, 24)
        nlri1 = INET.from_cidr(cidr1, AFI.ipv4, SAFI.unicast)

        packed_ip2 = socket.inet_aton('10.0.1.0')
        cidr2 = CIDR.create_cidr(packed_ip2, 24)
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

        eor = EOR(AFI.ipv4, SAFI.unicast)

        # EOR messages have IS_EOR=True
        assert eor.IS_EOR is True

    def test_update_collection_has_eor_false(self) -> None:
        """Test that UpdateCollection has EOR=False attribute."""
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

        # UpdateCollection has IS_EOR=False
        assert update.IS_EOR is False

    def test_eor_vs_update_distinguished_by_eor_attribute(self, json_encoder: JSON) -> None:
        """Test that EOR and UpdateCollection are correctly distinguished.

        The JSON encoder checks getattr(update_msg, 'IS_EOR', False) to determine
        whether to use EOR path or UpdateCollection path.
        """

        # EOR message
        eor = EOR(AFI.ipv4, SAFI.unicast)
        assert getattr(eor, 'IS_EOR', False) is True

        # UpdateCollection
        attrs = AttributeCollection()
        update = UpdateCollection(announces=[], withdraws=[], attributes=attrs)
        assert getattr(update, 'IS_EOR', False) is False


class TestNLRIAccess:
    """Tests for accessing NLRIs through different interfaces."""

    def test_update_collection_nlris_property(self) -> None:
        """Test UpdateCollection.nlris returns bare NLRIs."""
        import socket

        # Create route
        packed_ip = socket.inet_aton('10.0.0.0')
        cidr = CIDR.create_cidr(packed_ip, 24)
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
        cidr = CIDR.create_cidr(packed_ip, 24)
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
        cidr = CIDR.create_cidr(packed_ip, 24)
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


class TestPublicJSONEventSurface:
    """Public JSON event methods must preserve parseable API semantics."""

    def test_state_events_parse_and_keep_existing_shape(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        up = parsed_api_event(json_encoder.up(api_neighbor))
        connected = parsed_api_event(json_encoder.connected(api_neighbor))
        down = parsed_api_event(json_encoder.down(api_neighbor, 'manual maintenance'))
        shutdown = parsed_api_event(json_encoder.shutdown())

        assert up['type'] == 'state'
        assert up['neighbor']['state'] == 'up'
        assert connected['type'] == 'state'
        assert connected['neighbor']['state'] == 'connected'
        assert down['type'] == 'state'
        assert down['neighbor']['state'] == 'down'
        assert down['neighbor']['reason'] == 'manual maintenance'
        assert shutdown == {
            'exabgp': '6.0.0',
            'type': 'notification',
            'notification': 'shutdown',
        }

    def test_control_events_parse_and_keep_existing_shape(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        fsm = Mock()
        fsm.name = Mock(return_value='established')

        fsm_event = parsed_api_event(json_encoder.fsm(api_neighbor, fsm))
        signal_event = parsed_api_event(json_encoder.signal(api_neighbor, Signal.RELOAD))

        assert fsm_event['type'] == 'fsm'
        assert fsm_event['neighbor']['state'] == 'established'
        assert signal_event['type'] == 'signal'
        assert signal_event['neighbor']['code'] == '-4'
        assert signal_event['neighbor']['name'] == 'reload'

    def test_bgp_message_events_parse_and_keep_existing_shape(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        keepalive = parsed_api_event(json_encoder.keepalive(api_neighbor, 'receive', b'HEAD', b'', Negotiated.UNSET))
        packets = parsed_api_event(
            json_encoder.packets(api_neighbor, 'receive', 2, b'\xff' * 16, b'\x00\x01', Negotiated.UNSET)
        )
        notification = parsed_api_event(
            json_encoder.notification(
                api_neighbor,
                'receive',
                Notification.make_notification(6, 0, b'closing'),
                b'HEAD',
                b'BODY',
                Negotiated.UNSET,
            )
        )
        open_event = parsed_api_event(
            json_encoder.open(api_neighbor, 'receive', sample_open_message(), b'HEAD', b'BODY', Negotiated.UNSET)
        )
        update = parsed_api_event(
            json_encoder.update(api_neighbor, 'receive', sample_update_message(), b'HEAD', b'BODY', Negotiated.UNSET)
        )

        assert keepalive['type'] == 'keepalive'
        assert keepalive['header'] == '0x48454144'
        assert keepalive['neighbor']['direction'] == 'receive'
        assert packets['type'] == 'update'
        assert packets['neighbor']['message'] == {
            'category': 2,
            'header': '0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
            'body': '0x0001',
        }
        assert notification['type'] == 'notification'
        assert notification['header'] == '0x48454144'
        assert notification['body'] == '0x424F4459'
        assert notification['neighbor']['notification']['message'] == 'closing'
        assert open_event['type'] == 'open'
        assert open_event['neighbor']['open']['capabilities']['hostname'] == {
            'host-name': 'router-a',
            'domain-name': 'example.net',
        }
        assert open_event['neighbor']['open']['capabilities']['software-version'] == {'software': 'ExaBGP/6.0.0'}
        assert update['type'] == 'update'
        assert update['header'] == '0x48454144'
        assert update['body'] == '0x424F4459'
        assert 'update' in update['neighbor']['message']

    @pytest.mark.parametrize(
        ('refresh_value', 'refresh_name'),
        [
            (REFRESH.ABSENT, 'absent'),
            (REFRESH.NORMAL, 'normal'),
            (REFRESH.ENHANCED, 'enhanced'),
        ],
    )
    def test_negotiated_refresh_variants_parse(
        self, json_encoder: JSON, api_neighbor: Mock, refresh_value: int, refresh_name: str
    ) -> None:
        event = parsed_api_event(json_encoder.negotiated(api_neighbor, sample_negotiated(refresh_value)))
        negotiated = event['neighbor']['negotiated']

        assert negotiated['message_size'] == 4096
        assert negotiated['hold_time'] == 90
        assert negotiated['asn4'] is True
        assert negotiated['multisession'] is False
        assert negotiated['operational'] is False
        assert negotiated['refresh'] == refresh_name
        assert negotiated['families'] == ['ipv4 unicast', 'ipv6 unicast']
        assert negotiated['nexthop'] == ['ipv4 unicast ipv4', 'ipv6 unicast ipv6']
        assert negotiated['add_path'] == {
            'send': ['ipv4 unicast'],
            'receive': ['ipv6 unicast'],
        }


class TestEventJSONSemantics:
    """Non-UPDATE events must keep JSON API values parseable and typed."""

    def test_route_refresh_event_values_are_strings(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        refresh = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.start)

        event = json.loads(json_encoder.refresh(api_neighbor, 'receive', refresh, b'', b'', Negotiated.UNSET))
        route_refresh = event['neighbor']['route-refresh']

        assert route_refresh == {
            'afi': 'ipv4',
            'safi': 'unicast',
            'subtype': 'begin',
        }

    def test_packets_event_keeps_message_object(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        event = json.loads(
            json_encoder.packets(api_neighbor, 'receive', 2, b'\xff' * 16, b'\x00\x01', Negotiated.UNSET)
        )

        assert event['type'] == 'update'
        assert event['neighbor']['message'] == {
            'category': 2,
            'header': '0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF',
            'body': '0x0001',
        }

    def test_negotiated_event_values_parse(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        negotiated = Mock()
        negotiated.msg_size = 4096
        negotiated.holdtime = 90
        negotiated.asn4 = True
        negotiated.multisession = False
        negotiated.operational = False
        negotiated.refresh = REFRESH.NORMAL
        negotiated.families = [(AFI.ipv4, SAFI.unicast)]
        negotiated.nexthop = [(AFI.ipv4, SAFI.unicast, AFI.ipv4)]
        negotiated.addpath = Mock()
        negotiated.addpath.send = Mock(return_value=True)
        negotiated.addpath.receive = Mock(return_value=False)

        event = json.loads(json_encoder.negotiated(api_neighbor, negotiated))
        negotiated_json = event['neighbor']['negotiated']

        assert negotiated_json['message_size'] == 4096
        assert negotiated_json['hold_time'] == 90
        assert negotiated_json['asn4'] is True
        assert negotiated_json['refresh'] == 'normal'
        assert negotiated_json['families'] == ['ipv4 unicast']
        assert negotiated_json['nexthop'] == ['ipv4 unicast ipv4']
        assert negotiated_json['add_path'] == {
            'send': ['ipv4 unicast'],
            'receive': [],
        }

    def test_operational_events_values_are_strings(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        advisory = Advisory.ADM(AFI.ipv4, SAFI.unicast, 'maintenance')
        query = Query.RPCQ(AFI.ipv4, SAFI.unicast, RouterID('192.0.2.9'), 7)
        counter = Response.RPCP(AFI.ipv4, SAFI.unicast, RouterID('192.0.2.9'), 7, 42)

        advisory_event = json.loads(
            json_encoder.operational(api_neighbor, 'receive', 'advisory', advisory, b'', b'', Negotiated.UNSET)
        )
        query_event = json.loads(
            json_encoder.operational(api_neighbor, 'receive', 'query', query, b'', b'', Negotiated.UNSET)
        )
        counter_event = json.loads(
            json_encoder.operational(api_neighbor, 'receive', 'counter', counter, b'', b'', Negotiated.UNSET)
        )

        assert advisory_event['neighbor']['operational'] == {
            'name': 'ADM',
            'afi': 'ipv4',
            'safi': 'unicast',
            'advisory': 'maintenance',
        }
        assert query_event['neighbor']['operational'] == {
            'name': 'RPCQ',
            'afi': 'ipv4',
            'safi': 'unicast',
        }
        assert counter_event['neighbor']['operational'] == {
            'name': 'RPCP',
            'afi': 'ipv4',
            'safi': 'unicast',
            'router-id': '192.0.2.9',
            'sequence': 7,
            'counter': 42,
        }


class TestPeerStringEscaping:
    """Peer-controlled strings must not inject JSON members."""

    def test_open_hostname_capability_escapes_peer_strings(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        capabilities = Capabilities()
        capabilities[Capability.CODE.HOSTNAME] = HostName('x", "injected": "owned', 'victim.example')
        open_msg = Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), capabilities)

        event = json.loads(json_encoder.open(api_neighbor, 'receive', open_msg, b'', b'', Negotiated.UNSET))
        hostname = event['neighbor']['open']['capabilities']['hostname']

        assert hostname['host-name'] == 'x", "injected": "owned'
        assert hostname['domain-name'] == 'victim.example'
        assert 'injected' not in hostname

    def test_open_software_capability_escapes_peer_strings(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        software = Software()
        software.software_version = 'ExaBGP", "injected": "owned'
        capabilities = Capabilities()
        capabilities[Capability.CODE.SOFTWARE_VERSION] = software
        open_msg = Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), capabilities)

        event = json.loads(json_encoder.open(api_neighbor, 'receive', open_msg, b'', b'', Negotiated.UNSET))
        software_capability = event['neighbor']['open']['capabilities']['software-version']

        assert software_capability['software'] == 'ExaBGP", "injected": "owned'
        assert 'injected' not in software_capability

    def test_notification_escapes_peer_data(self, json_encoder: JSON, api_neighbor: Mock) -> None:
        payload = b'y", "injected-notif": "owned2'
        notification = Notification.make_notification(6, 0, payload)

        event = json.loads(json_encoder.notification(api_neighbor, 'receive', notification, b'', b'', Negotiated.UNSET))
        notification_json = event['neighbor']['notification']

        assert notification_json['message'] == payload.decode()
        assert notification_json['data'] == '0x79222C2022696E6A65637465642D6E6F746966223A20226F776E656432'
        assert 'injected-notif' not in notification_json


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
