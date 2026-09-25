"""OTC route parsing, admission and actual UPDATE bytes agree across sessions."""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message import Message
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.logger import log
from exabgp.reactor.api import API
from exabgp.reactor.api.response.json import JSON
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.protocol.family import AFI, SAFI


IPV4 = (AFI.ipv4, SAFI.unicast)
IPV6 = (AFI.ipv6, SAFI.unicast)
# CLI tests can disable the shared dispatcher; retain its real filtering implementation.
ENABLED_LOG_DISPATCH = log.logger


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})


def configured(role='provider', routes='', cache=True):
    role_block = f'role {{ local {role}; }}' if role else ''
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65537;
    peer-as 65002;
    adj-rib-out {'true' if cache else 'false'};
    {role_block}
    family {{ ipv4 unicast; ipv6 unicast; ipv4 multicast; }}
    static {{ {routes} }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    neighbor = next(iter(configuration.neighbors.values()))
    _, negotiated = _negotiated(neighbor)
    return neighbor, negotiated


def route(otc='', path=0, prefix='10.0.0.0/24'):
    command = f'route {prefix} next-hop 192.0.2.2'
    if path:
        command += f' path-information {path}'
    if otc:
        command += f' otc {otc}'
    parsed = API(Mock()).api_route(command, 'announce')
    assert len(parsed) == 1
    return parsed[0]


def sent(rib, negotiated, limits=None):
    return [
        Update.unpack_message(wire[19:], negotiated).parse(negotiated)
        for update in rib.updates(True, limits, negotiated)
        if isinstance(update, UpdateCollection)
        for wire in update.messages(negotiated)
    ]


@pytest.mark.parametrize(
    'role,automatic,explicit',
    [
        ('provider', True, True),
        ('rs', True, True),
        ('peer', True, False),
        ('customer', False, False),
        ('rs-client', False, False),
        (None, False, True),
    ],
)
def test_static_routes_reach_wire_with_role_policy(role, automatic, explicit):
    text = """
        route 10.0.0.0/24 next-hop 192.0.2.2;
        route 10.0.1.0/24 next-hop 192.0.2.2 otc 65009;
    """
    neighbor, negotiated = configured(role, text)
    updates = sent(neighbor.rib.outgoing, negotiated)
    observed = {
        str(item.nlri.cidr): update.attributes.get(Attribute.CODE.OTC)
        for update in updates
        for item in update.announces
    }
    assert ('10.0.1.0/24' in observed) == explicit
    assert (observed['10.0.0.0/24'].asn if automatic else observed['10.0.0.0/24']) == (65537 if automatic else None)
    if explicit:
        assert observed['10.0.1.0/24'].asn == 65009


@pytest.mark.parametrize('cache', [True, False])
def test_blocked_replacement_withdraws_previous_route_after_reload(cache):
    neighbor, negotiated = configured('customer', cache=cache)
    rib = neighbor.rib.outgoing
    original, blocked = route(), route('65009')
    rib.add_to_rib(original)
    assert sent(rib, negotiated)[0].announces[0].nlri == original.nlri
    if not cache:
        rib.clear()
    rib.add_to_rib(blocked)
    updates = sent(rib, negotiated)
    assert not any(update.announces for update in updates)
    assert [nlri for update in updates for nlri in update.withdraws] == [original.nlri]
    rib.resend(False)
    assert sent(rib, negotiated) == []
    rib.add_to_rib(original)
    assert sent(rib, negotiated)[0].announces[0].nlri == original.nlri


def test_final_desired_route_wins_over_attribute_bucket_order():
    neighbor, negotiated = configured('customer')
    rib = neighbor.rib.outgoing
    original = route()
    for desired in (original, route('65009'), route()):
        rib.add_to_rib(desired, force=True)
    updates = sent(rib, negotiated)
    assert [item.nlri for update in updates for item in update.announces] == [original.nlri]
    assert not any(update.withdraws for update in updates)


def test_blocked_held_path_is_not_promoted_and_refusal_frees_slot():
    neighbor, negotiated = configured('customer', cache=False)
    rib = neighbor.rib.outgoing
    limits = {IPV4: 1}
    first, held, third = route(path=1), route(path=2), route(path=3)
    for candidate in (first, held, third):
        rib.add_to_rib(candidate)
    list(rib.updates(True, limits, negotiated))
    rib.add_to_rib(route('65009', path=2))
    assert list(rib.updates(True, limits, negotiated)) == []
    rib.add_to_rib(route('65009', path=1))
    updates = list(rib.updates(True, limits, negotiated))
    assert [nlri for update in updates for nlri in update.withdraws] == [first.nlri]
    assert [item.nlri for update in updates for item in update.announces] == [third.nlri]
    rib.del_from_rib(third)
    updates = list(rib.updates(True, limits, negotiated))
    assert not any(update.announces for update in updates)


def test_shared_self_instruction_is_resolved_without_mutation():
    neighbor, negotiated = configured()
    desired = route('self')
    before = desired.attributes.index(), str(desired.attributes), desired.attributes.json()
    update = UpdateCollection([RoutedNLRI(desired.nlri, desired.nexthop)], [], desired.attributes)
    for local_as in (65537, 65538):
        negotiated.local_as = ASN(local_as)
        decoded = Update.unpack_message(next(update.messages(negotiated))[19:], negotiated).parse(negotiated)
        assert decoded.attributes[Attribute.CODE.OTC].asn == local_as
    assert (desired.attributes.index(), str(desired.attributes), desired.attributes.json()) == before


def test_mixed_unicast_multicast_preserves_family_and_limits_automatic_marking():
    _, negotiated = configured()
    api = API(Mock())
    v4 = route()
    multicast = api.api_announce_v4('ipv4 multicast 10.0.1.0/24 next-hop 192.0.2.2', 'announce')[0]
    collection = UpdateCollection([RoutedNLRI(r.nlri, r.nexthop) for r in (v4, multicast)], [], v4.attributes)
    decoded = [
        Update.unpack_message(wire[19:], negotiated).parse(negotiated) for wire in collection.messages(negotiated)
    ]
    observed = {
        item.nlri.family().afi_safi(): Attribute.CODE.OTC in update.attributes
        for update in decoded
        for item in update.announces
    }
    assert observed == {IPV4: True, (AFI.ipv4, SAFI.multicast): False}


@pytest.mark.parametrize('compact,v4_json', [(False, False), (True, False), (False, True), (True, True)])
def test_ingress_metadata_is_per_announcement_and_optional(compact, v4_json):
    neighbor, negotiated = configured('provider')
    incoming = route('65009')
    collection = UpdateCollection([RoutedNLRI(incoming.nlri, incoming.nexthop)], [], incoming.attributes)
    collection.classify_otc(negotiated)
    encoder = JSON('6.0.0')
    encoder.compact = compact
    encoder.use_v4_json = v4_json
    data = json.loads(encoder._update(collection)['message'])['update']
    report = data['announce']['ipv4 unicast']['192.0.2.2'][0]['meta']['route-leak']
    assert report == {
        'reason': 'invalid-otc',
        'peer-role': 'customer',
        'peer-as': 'AS65002',
        'expected-otc': 'none',
        'received-otc': 'AS65009',
    }
    assert data['attribute']['otc'] == 65009
    assert 'meta' not in encoder._update(collection, include_meta=False)['message']
    assert incoming.attributes[Attribute.CODE.OTC].asn == 65009
    assert 'meta' not in incoming.nlri.json()


def test_clean_peer_otc_and_withdrawals_never_gain_leak_annotations():
    _, negotiated = configured('peer')
    incoming = route('65002')
    collection = UpdateCollection([RoutedNLRI(incoming.nlri, incoming.nexthop)], [], incoming.attributes)
    collection.classify_otc(negotiated)
    assert collection.route_leaks is None
    withdrawn = UpdateCollection([], [incoming.nlri], route('65009').attributes)
    withdrawn.classify_otc(negotiated)
    assert withdrawn.route_leaks is None


@pytest.mark.asyncio
async def test_auto_as_open_and_static_self_reach_wire_with_real_four_octet_asn():
    neighbor, _ = configured(None, 'route 10.0.0.0/24 next-hop 192.0.2.2 otc self;')
    neighbor.session.local_as = ASN(0)
    neighbor.session.peer_as = ASN(70000)
    proto = Protocol(Peer(neighbor, Mock()))
    proto.connection = Mock(writer_async=AsyncMock())
    remote_caps = Capabilities().new(neighbor, False, local_as=ASN(70000))
    remote = Open.make_open(Version(4), ASN(70000), HoldTime(90), RouterID('192.0.2.1'), remote_caps)
    proto.negotiated.received(remote)
    proto.negotiated.sent(await proto.new_open())
    assert proto.negotiated.validate(neighbor) is None
    await proto.new_update(True)
    wire = proto.connection.writer_async.await_args.args[0]
    decoded = Update.unpack_message(wire[19:], proto.negotiated).parse(proto.negotiated)
    assert decoded.attributes[Attribute.CODE.OTC].asn == 70000
    assert str(decoded.announces[0].nlri.cidr) == '10.0.0.0/24'
    assert neighbor.session.local_as == 0


@pytest.mark.asyncio
async def test_receive_classifies_without_api_or_cache_and_live_meta_setting_only_hides_output():
    neighbor, negotiated = configured('provider')
    neighbor.adj_rib_in = False
    incoming = route('65009')
    collection = UpdateCollection([RoutedNLRI(incoming.nlri, incoming.nexthop)], [], incoming.attributes)
    wire = next(collection.messages(negotiated))
    proto = Protocol(Peer(neighbor, Mock()))
    proto.negotiated = negotiated
    proto.log_routes = False
    proto.connection = Mock(
        reader_async=AsyncMock(return_value=(len(wire), Message.CODE.UPDATE, wire[:19], wire[19:], None))
    )
    with patch('exabgp.bgp.message.update.collection.log.warning') as warning:
        received = await proto.read_message()
    assert isinstance(received, Update)
    assert received.data.route_leaks[IPV4].received_otc == 'AS65009'
    assert 'update.otc.leak' in warning.call_args.args[0]()
    encoder = JSON('6.0.0')
    shown = encoder.update(neighbor, 'receive', received.data, b'', b'', negotiated)
    assert 'route-leak' in shown
    neighbor.session.role_add_meta = False
    hidden = encoder.update(neighbor, 'receive', received.data, b'', b'', negotiated)
    assert 'meta' not in hidden
    assert json.loads(hidden)['neighbor']['message']['update']['attribute']['otc'] == 65009


def test_role_schema_exports_the_required_role_and_supported_policies():
    from exabgp.application.schema import _get_root_schema, _get_section_schema, schema_to_json_schema

    role = _get_section_schema('role')
    assert role is not None
    exported = schema_to_json_schema(role)
    assert exported['required'] == ['local']
    assert set(exported['properties']['local']['enum']) == {'provider', 'customer', 'peer', 'rs', 'rs-client'}
    # RFC 9234 section 5 leaves the operator no switch, so none is offered by the schema.
    assert 'otc' not in exported['properties']
    root = schema_to_json_schema(_get_root_schema())
    assert root['properties']['neighbor']['properties']['role'] == exported


@pytest.mark.parametrize('local_as,peer_as', [(65001, 65001), (0, 65002), (65001, 0)])
def test_programmatic_role_settings_reject_ibgp_and_unresolved_asns(local_as, peer_as):
    from exabgp.bgp.neighbor.settings import SessionSettings
    from exabgp.bgp.neighbor.session import Session
    from exabgp.protocol.ip import IP

    settings = SessionSettings(
        peer_address=IP.from_string('192.0.2.1'),
        local_address=IP.from_string('192.0.2.2'),
        local_as=ASN(local_as),
        peer_as=ASN(peer_as),
        role=RoleValue.PROVIDER,
    )
    with pytest.raises(ValueError):
        Session.from_settings(settings)


def test_latest_replacement_is_advertised_inside_enhanced_refresh_boundary():
    from exabgp.bgp.message.refresh import RouteRefresh

    neighbor, negotiated = configured()
    rib = neighbor.rib.outgoing
    rib.add_to_rib(route())
    sent(rib, negotiated)
    rib.resend(True)
    rib.add_to_rib(route('65009'))
    updates = list(rib.updates(True, negotiated=negotiated))
    end = next(
        i
        for i, update in enumerate(updates)
        if isinstance(update, RouteRefresh) and update.reserved == RouteRefresh.end
    )
    advertised = [update for update in updates[:end] if isinstance(update, UpdateCollection) and update.announces]
    assert [str(item.nlri.cidr) for update in advertised for item in update.announces] == ['10.0.0.0/24']
    assert advertised[0].attributes[Attribute.CODE.OTC].asn == 65009


@pytest.mark.parametrize('new_role', [RoleValue.RS, RoleValue.NO_ROLE])
def test_reconnect_revalidates_cached_role_assertions(new_role):
    neighbor, negotiated = configured('provider')
    rib = neighbor.rib.outgoing
    rib.add_to_rib(neighbor.resolve_self(route('provider')))
    assert sent(rib, negotiated)[0].attributes[Attribute.CODE.OTC].asn == 65537
    rib.session_reset()
    negotiated.role = new_role
    negotiated.peer_role = (
        RoleValue.complement(negotiated.role) if negotiated.role != RoleValue.NO_ROLE else RoleValue.NO_ROLE
    )
    rib.resend(False)
    assert sent(rib, negotiated) == []


@pytest.mark.parametrize('receiving', [True, False])
def test_otc_warnings_survive_default_debug_category_filters(receiving, monkeypatch, caplog):
    import logging

    from exabgp.logger.option import echo, option

    neighbor, negotiated = configured('provider' if receiving else 'customer')
    monkeypatch.setattr(log, 'logger', staticmethod(ENABLED_LOG_DISPATCH))
    monkeypatch.setattr(option, 'logger', logging.getLogger('test.otc.policy'))
    monkeypatch.setattr(option, 'formater', echo)
    monkeypatch.setattr(option, 'option', {'parser': False, 'rib': False, 'reactor': True})
    monkeypatch.setattr(option, 'logit', {'WARNING': True})
    caplog.set_level(logging.WARNING, logger='test.otc.policy')
    desired = route('65009')
    if receiving:
        update = UpdateCollection([RoutedNLRI(desired.nlri, desired.nexthop)], [], desired.attributes)
        update.classify_otc(negotiated)
        assert update.route_leaks[IPV4].received_otc == 'AS65009'
    else:
        neighbor.rib.outgoing.add_to_rib(desired)
        assert sent(neighbor.rib.outgoing, negotiated) == []
    assert any('otc' in record.message and '10.0.0.0/24' in record.message for record in caplog.records)
