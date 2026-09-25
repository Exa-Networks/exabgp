"""Wire-level packetization contracts using the stable UPDATE codecs."""

from collections import Counter

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attributes, NextHop
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


@pytest.fixture(autouse=True)
def quiet_codec_logging(monkeypatch):
    monkeypatch.setattr(log, 'debug', lambda *args: None)
    monkeypatch.setattr(log, 'critical', lambda *args: None)


def negotiated_session():
    negotiated = Negotiated({'capability': {'aigp': False}})
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv4, SAFI.multicast), (AFI.ipv6, SAFI.unicast)]
    return negotiated


def routed_prefix(prefix, action=Action.ANNOUNCE, safi=SAFI.unicast, nexthop=True):
    address, mask = prefix.split('/')
    ip = IP.create(address)
    nlri = INET(ip.afi, safi, action)
    nlri.cidr = CIDR(ip.pack(), int(mask))
    if nexthop:
        nlri.nexthop = IP.create('192.0.2.1' if ip.afi == AFI.ipv4 else '2001:db8::ffff')
    return nlri


def decode_messages(update, negotiated):
    messages = list(update.messages(negotiated))
    assert all(len(message) <= negotiated.msg_size for message in messages)
    decoded = [Update.unpack_message(message[19:], Direction.IN, negotiated) for message in messages]
    assert not any(isinstance(message, EOR) for message in decoded)
    return decoded


def route_counts(nlris):
    return Counter((nlri.family().afi_safi(), nlri.cidr.prefix(), nlri.action) for nlri in nlris)


def assert_exact_routes(decoded, expected):
    assert route_counts(nlri for update in decoded for nlri in update.nlris) == route_counts(expected)


def peer_state(decoded, initial=()):
    advertised = set(initial)
    for update in decoded:
        advertised.difference_update(nlri.cidr.prefix() for nlri in update.nlris if nlri.action == Action.WITHDRAW)
        advertised.update(nlri.cidr.prefix() for nlri in update.nlris if nlri.action == Action.ANNOUNCE)
    return advertised


def test_ipv4_multicast_announcement_keeps_its_safi():
    negotiated = negotiated_session()
    route = routed_prefix('239.1.0.0/16', safi=SAFI.multicast)
    decoded = decode_messages(Update([route], Attributes()), negotiated)
    assert_exact_routes(decoded, [route])


@pytest.mark.parametrize('nexthop', [True, False])
def test_ipv4_multicast_withdrawal_keeps_its_safi(nexthop):
    negotiated = negotiated_session()
    route = routed_prefix('239.1.0.0/16', Action.WITHDRAW, SAFI.multicast, nexthop)
    decoded = decode_messages(Update([route], Attributes()), negotiated)
    assert_exact_routes(decoded, [route])


def test_bare_ipv6_withdrawal_needs_no_nexthop():
    negotiated = negotiated_session()
    route = routed_prefix('2001:db8::1/128', Action.WITHDRAW, nexthop=False)
    decoded = decode_messages(Update([route], Attributes()), negotiated)
    assert_exact_routes(decoded, [route])


def test_native_prefixes_are_not_repeated_in_following_mp_packets():
    negotiated = negotiated_session()
    routes = [
        routed_prefix('10.0.0.0/24'),
        routed_prefix('10.0.1.0/24', Action.WITHDRAW),
        routed_prefix('2001:db8::/32'),
        routed_prefix('2001:db9::/32', Action.WITHDRAW),
        routed_prefix('239.1.0.0/16', safi=SAFI.multicast),
        routed_prefix('239.2.0.0/16', Action.WITHDRAW, SAFI.multicast),
    ]
    attributes = Attributes()
    attributes.add(NextHop('192.0.2.1'))
    decoded = decode_messages(Update(routes, attributes), negotiated)
    assert_exact_routes(decoded, routes)


@pytest.mark.parametrize('nexthop', [True, False])
def test_suppressed_mp_withdrawal_does_not_emit_an_empty_update(nexthop):
    negotiated = negotiated_session()
    withdrawal = routed_prefix('2001:db8::1/128', Action.WITHDRAW, nexthop=nexthop)
    assert list(Update([withdrawal], Attributes()).messages(negotiated, include_withdraw=False)) == []


def test_full_mp_reach_does_not_starve_pending_withdrawal():
    negotiated = negotiated_session()
    announces = [routed_prefix('2001:db8::{:x}/128'.format(index)) for index in range(237)]
    withdrawal = routed_prefix('2001:db8:1::1/128', Action.WITHDRAW)
    routes = announces + [withdrawal]
    decoded = decode_messages(Update(routes, Attributes()), negotiated)
    assert_exact_routes(decoded, routes)
    assert peer_state(decoded, [withdrawal.cidr.prefix()]) == {nlri.cidr.prefix() for nlri in announces}


def test_fragmented_announcements_keep_reannounced_prefix():
    negotiated = negotiated_session()
    announces = [routed_prefix('2001:db8::{:x}/128'.format(index)) for index in range(300)]
    withdrawal = routed_prefix('2001:db8::/128', Action.WITHDRAW)
    routes = announces + [withdrawal]
    decoded = decode_messages(Update(routes, Attributes()), negotiated)
    assert_exact_routes(decoded, routes)
    assert peer_state(decoded) == {nlri.cidr.prefix() for nlri in announces}


def test_fragmented_withdrawals_keep_reannounced_prefix():
    negotiated = negotiated_session()
    withdrawals = [routed_prefix('2001:db8::{:x}/128'.format(index), Action.WITHDRAW) for index in range(300)]
    announced = routed_prefix('2001:db8::12b/128')
    routes = withdrawals + [announced]
    decoded = decode_messages(Update(routes, Attributes()), negotiated)
    assert_exact_routes(decoded, routes)
    assert peer_state(decoded, [nlri.cidr.prefix() for nlri in withdrawals]) == {announced.cidr.prefix()}


def test_small_mp_withdrawal_and_announcement_do_not_share_one_packet():
    # They used to. RFC 7606 5.1 says an UPDATE "MUST NOT contain more than one of the
    # following: ... MP_REACH_NLRI attribute, and MP_UNREACH_NLRI attribute". The withdrawal
    # is emitted first, so the prefix is still withdrawn before it is re-announced.
    negotiated = negotiated_session()
    routes = [routed_prefix('2001:db8::1/128', Action.WITHDRAW), routed_prefix('2001:db8::1/128')]
    decoded = decode_messages(Update(routes, Attributes()), negotiated)
    assert len(decoded) == 2
    assert_exact_routes(decoded, routes)
    assert peer_state(decoded) == {'2001:db8::1/128'}
