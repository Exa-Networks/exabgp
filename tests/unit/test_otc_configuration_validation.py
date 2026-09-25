"""Configuration route validation checks emitted OTC semantics, not a second export."""

import pytest

from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.update.attribute import Attribute, OTC
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.configuration.check import _negotiated, check_generation
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})


def configured(role='', otc='', local_as='65537', peer_as='65002', prefix='10.0.0.0/24', extra=''):
    role_block = f'role {{ local {role}; }}' if role else ''
    instruction = f'otc {otc}' if otc else ''
    nexthop = '2001:db8::2' if ':' in prefix else '192.0.2.2'
    config = Configuration(
        [
            f"""neighbor 192.0.2.1 {{
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as {local_as};
            peer-as {peer_as};
            {role_block}
            family {{ ipv4 unicast; ipv6 unicast; }}
            static {{ route {prefix} next-hop {nexthop} med 37 {instruction} {extra}; }}
        }}"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    return config


@pytest.mark.parametrize(
    'role,otc,prefix',
    [
        ('', '', '10.0.0.0/24'),
        ('provider', '', '10.0.0.0/24'),
        ('rs', '', '10.0.0.0/24'),
        ('peer', '', '10.0.0.0/24'),
        ('provider', 'self', '10.0.0.0/24'),
        ('', 'self', '10.0.0.0/24'),
        ('provider', 'provider', '10.0.0.0/24'),
        ('provider', '65009', '10.0.0.0/24'),
        ('peer', '', '2001:db8::/48'),
    ],
)
def test_generation_validates_expected_otc_semantics(role, otc, prefix):
    config = configured(role, otc, prefix=prefix)
    assert check_generation(config.neighbors)


def test_validation_accepts_automatic_otc_with_higher_code_attribute():
    config = configured('provider', extra='bgp-prefix-sid [ 777 ]')
    assert check_generation(config.neighbors)


@pytest.mark.parametrize('role', ['peer', 'customer', 'rs-client'])
def test_validation_accepts_policy_refusal_without_advertising_route(role):
    config = configured(role, '65009')
    (neighbor,) = config.neighbors.values()
    _, negotiated = _negotiated(neighbor)
    route = neighbor.routes[0]
    assert check_generation(config.neighbors)
    assert (
        list(UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes).messages(negotiated)) == []
    )


@pytest.mark.parametrize('role,otc', [('', ''), ('peer', '')])
def test_validation_rejects_unrelated_decoded_attribute_corruption(monkeypatch, role, otc):
    config = configured(role, otc)
    original = UpdateCollection.unpack_message

    def corrupt(data, negotiated):
        update = original(data, negotiated)
        update.attributes[Attribute.CODE.MED] = MED.from_int(38)
        return update

    monkeypatch.setattr(UpdateCollection, 'unpack_message', corrupt)
    assert not check_generation(config.neighbors)


def test_validation_rejects_corrupted_automatic_otc(monkeypatch):
    config = configured('provider')
    original = UpdateCollection.unpack_message

    def corrupt(data, negotiated):
        update = original(data, negotiated)
        update.attributes[Attribute.CODE.OTC] = OTC.make_otc(65009)
        return update

    monkeypatch.setattr(UpdateCollection, 'unpack_message', corrupt)
    assert not check_generation(config.neighbors)


def test_validation_rejects_unexplained_missing_update(monkeypatch):
    config = configured('provider')
    monkeypatch.setattr(UpdateCollection, 'messages', lambda *args, **kwargs: iter(()))
    assert not check_generation(config.neighbors)


@pytest.mark.parametrize('peer_as', ['65002', '65538'])
def test_synthetic_negotiation_resolves_auto_local_as_for_otc_self(peer_as):
    config = configured(otc='self', local_as='auto', peer_as=peer_as)
    (neighbor,) = config.neighbors.values()
    incoming, outgoing = _negotiated(neighbor)
    route = neighbor.routes[0]
    (wire,) = UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes).messages(outgoing)
    update = UpdateCollection.unpack_message(wire[19:], incoming)
    assert update.attributes[Attribute.CODE.OTC].asn == int(peer_as)
    assert neighbor.session.local_as == 0


def test_synthetic_negotiation_does_not_invent_unresolved_auto_asn():
    config = configured(otc='self', local_as='auto', peer_as='auto')
    (neighbor,) = config.neighbors.values()
    _, outgoing = _negotiated(neighbor)
    route = neighbor.routes[0]
    with pytest.raises(ValueError, match='resolved local ASN'):
        list(UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes).messages(outgoing))


def test_validation_keeps_known_local_as_with_auto_peer():
    config = configured(otc='self', local_as='65538', peer_as='auto')
    assert check_generation(config.neighbors)


def test_validation_rejects_unresolved_self_without_crashing():
    config = configured(otc='self', local_as='auto', peer_as='auto')
    assert not check_generation(config.neighbors)
