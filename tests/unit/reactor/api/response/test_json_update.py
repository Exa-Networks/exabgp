"""Tests for JSON API response generation."""

import json
from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notification
from exabgp.bgp.message.operational import Advisory, Query, Response
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.hostname import HostName
from exabgp.bgp.message.open.capability.refresh import REFRESH
from exabgp.bgp.message.open.capability.software import Software
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IPv4
from exabgp.reactor.api.response.json import JSON
from exabgp.reactor.interrupt import Signal


@pytest.fixture
def json_encoder():
    return JSON('5.0.10')


class Neighbor(dict):
    def __init__(self):
        super().__init__(
            {
                'local-address': IPv4('192.0.2.2'),
                'peer-address': IPv4('192.0.2.1'),
                'local-as': 65000,
                'peer-as': 65001,
                'router-id': IPv4('192.0.2.2'),
            }
        )
        self.uid = '192.0.2.1'


@pytest.fixture
def api_neighbor():
    return Neighbor()


def parsed_api_event(payload):
    event = json.loads(payload)
    for volatile_key in ('time', 'host', 'pid', 'ppid', 'counter'):
        event.pop(volatile_key, None)
    return event


def sample_negotiated(refresh=REFRESH.NORMAL):
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


def sample_open_message():
    capabilities = Capabilities()
    capabilities[Capability.CODE.HOSTNAME] = HostName('router-a', 'example.net')
    software = Software()
    software.software_version = 'ExaBGP/5.0.10'
    capabilities[Capability.CODE.SOFTWARE_VERSION] = software
    return Open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), capabilities)


def sample_update_message():
    family = Mock()
    family.afi_safi = Mock(return_value=(AFI.ipv4, SAFI.unicast))
    nlri = Mock()
    nlri.nexthop = IPv4('192.0.2.254')
    nlri.action = Action.ANNOUNCE
    nlri.family = Mock(return_value=family)
    nlri.json = Mock(return_value='{ "nlri": "10.0.0.0/24" }')
    update = Mock()
    update.nlris = [nlri]
    update.attributes = {}
    return update


class TestPublicJSONEventSurface:
    """Public JSON event methods must preserve parseable API semantics."""

    def test_state_events_parse_and_keep_existing_shape(self, json_encoder, api_neighbor):
        up = parsed_api_event(json_encoder.up(api_neighbor))
        connected = parsed_api_event(json_encoder.connected(api_neighbor))
        down = parsed_api_event(json_encoder.down(api_neighbor, 'manual "maintenance"'))
        shutdown = parsed_api_event(json_encoder.shutdown())

        assert up['type'] == 'state'
        assert up['neighbor']['state'] == 'up'
        assert connected['type'] == 'state'
        assert connected['neighbor']['state'] == 'connected'
        assert down['type'] == 'state'
        assert down['neighbor']['state'] == 'down'
        assert down['neighbor']['reason'] == 'manual "maintenance"'
        assert shutdown == {
            'exabgp': '5.0.10',
            'type': 'notification',
            'notification': 'shutdown',
        }

    def test_control_events_parse_and_keep_existing_shape(self, json_encoder, api_neighbor):
        fsm = Mock()
        fsm.name = Mock(return_value='established')

        fsm_event = parsed_api_event(json_encoder.fsm(api_neighbor, fsm))
        signal_event = parsed_api_event(json_encoder.signal(api_neighbor, Signal.RELOAD))

        assert fsm_event['type'] == 'fsm'
        assert fsm_event['neighbor']['state'] == 'established'
        assert signal_event['type'] == 'signal'
        assert signal_event['neighbor']['code'] == '-4'
        assert signal_event['neighbor']['name'] == 'reload'

    def test_bgp_message_events_parse_and_keep_existing_shape(self, json_encoder, api_neighbor):
        keepalive = parsed_api_event(json_encoder.keepalive(api_neighbor, 'receive', None, b'HEAD', b''))
        packets = parsed_api_event(json_encoder.packets(api_neighbor, 'receive', 2, None, b'\xff' * 16, b'\x00\x01'))
        notification = parsed_api_event(
            json_encoder.notification(
                api_neighbor,
                'receive',
                Notification(6, 0, b'closing', parse_data=False),
                None,
                b'HEAD',
                b'BODY',
            )
        )
        open_event = parsed_api_event(
            json_encoder.open(api_neighbor, 'receive', sample_open_message(), None, b'HEAD', b'BODY')
        )
        update = parsed_api_event(
            json_encoder.update(api_neighbor, 'receive', sample_update_message(), None, b'HEAD', b'BODY')
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
        assert open_event['neighbor']['open']['capabilities']['software-version'] == {'software': 'ExaBGP/5.0.10'}
        assert update['type'] == 'update'
        assert update['header'] == '0x48454144'
        assert update['body'] == '0x424F4459'
        assert update['neighbor']['message']['update']['announce']['ipv4 unicast']['192.0.2.254'] == [
            {'nlri': '10.0.0.0/24'}
        ]

    @pytest.mark.parametrize(
        ('refresh_value', 'refresh_name'),
        [
            (REFRESH.ABSENT, 'absent'),
            (REFRESH.NORMAL, 'normal'),
            (REFRESH.ENHANCED, 'enhanced'),
        ],
    )
    def test_negotiated_refresh_variants_parse(self, json_encoder, api_neighbor, refresh_value, refresh_name):
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

    def test_route_refresh_event_values_are_strings(self, json_encoder, api_neighbor):
        refresh = RouteRefresh(AFI.ipv4, SAFI.unicast, RouteRefresh.start)

        event = json.loads(json_encoder.refresh(api_neighbor, 'receive', refresh, None, b'', b''))
        route_refresh = event['neighbor']['route-refresh']

        assert route_refresh == {
            'afi': 'ipv4',
            'safi': 'unicast',
            'subtype': 'begin',
        }

    def test_operational_events_values_are_strings(self, json_encoder, api_neighbor):
        advisory = Advisory.ADM(AFI.ipv4, SAFI.unicast, 'maintenance')
        query = Query.RPCQ(AFI.ipv4, SAFI.unicast, RouterID('192.0.2.9'), 7)
        counter = Response.RPCP(AFI.ipv4, SAFI.unicast, RouterID('192.0.2.9'), 7, 42)

        advisory_event = json.loads(
            json_encoder.operational(api_neighbor, 'receive', 'advisory', advisory, None, b'', b'')
        )
        query_event = json.loads(json_encoder.operational(api_neighbor, 'receive', 'query', query, None, b'', b''))
        counter_event = json.loads(
            json_encoder.operational(api_neighbor, 'receive', 'counter', counter, None, b'', b'')
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

    def test_open_hostname_capability_escapes_peer_strings(self, json_encoder, api_neighbor):
        capabilities = Capabilities()
        capabilities[Capability.CODE.HOSTNAME] = HostName('x", "injected": "owned', 'victim.example')
        open_msg = Open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), capabilities)

        event = json.loads(json_encoder.open(api_neighbor, 'receive', open_msg, None, b'', b''))
        hostname = event['neighbor']['open']['capabilities']['hostname']

        assert hostname['host-name'] == 'x", "injected": "owned'
        assert hostname['domain-name'] == 'victim.example'
        assert 'injected' not in hostname

    def test_open_software_capability_escapes_peer_strings(self, json_encoder, api_neighbor):
        software = Software()
        software.software_version = 'ExaBGP", "injected": "owned'
        capabilities = Capabilities()
        capabilities[Capability.CODE.SOFTWARE_VERSION] = software
        open_msg = Open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), capabilities)

        event = json.loads(json_encoder.open(api_neighbor, 'receive', open_msg, None, b'', b''))
        software_capability = event['neighbor']['open']['capabilities']['software-version']

        assert software_capability['software'] == 'ExaBGP", "injected": "owned'
        assert 'injected' not in software_capability

    def test_notification_escapes_peer_data(self, json_encoder, api_neighbor):
        payload = b'y", "injected-notif": "owned2'
        notification = Notification(6, 0, payload, parse_data=False)

        event = json.loads(json_encoder.notification(api_neighbor, 'receive', notification, None, b'', b''))
        notification_json = event['neighbor']['notification']

        assert notification_json['message'] == payload.decode()
        assert notification_json['data'] == '0x79222C2022696E6A65637465642D6E6F746966223A20226F776E656432'
        assert 'injected-notif' not in notification_json

    def test_down_reason_round_trips_verbatim(self, json_encoder, api_neighbor):
        # _string() escapes with json.dumps, so the brackets no longer need
        # to be mangled into parentheses before being emitted
        reason = 'notification received (6,0) [hold timer] {peer "a"}'

        event = json.loads(json_encoder.down(api_neighbor, reason))

        assert event['neighbor']['reason'] == reason
