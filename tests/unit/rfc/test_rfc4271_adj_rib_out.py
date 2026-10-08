"""RFC 4271 9.2: what the adj-rib-out sends, for routes which differ only by Path Identifier.

The ledger these tests are joined to is qa/rfc/rfc4271.toml.

A route carries a Path Identifier (RFC 7911) when it is configured with `path-information`
or re-advertised from a peer which sent paths. The adj-rib-out keys a route by it, but a
session which did not negotiate ADD-PATH send for the family has no Path Identifier on the
wire: every path of a prefix is the same route to that peer. It is sent one of them, the
first offered, and when that one goes another takes its place rather than the prefix being
withdrawn while a path is left.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route
from tests import negotiation

IPV4_UNICAST: FamilyTuple = (AFI.ipv4, SAFI.unicast)


def path(identifier: int, prefix: str = '10.0.0.0/24') -> INET:
    address, mask = prefix.split('/')
    path_info = PathInfo.make_from_integer(identifier) if identifier else PathInfo.DISABLED
    return INET.from_cidr(CIDR.create_cidr(IP.pton(address), int(mask)), AFI.ipv4, SAFI.unicast, path_info)


def route(identifier: int, preference: int = 100, prefix: str = '10.0.0.0/24') -> Route:
    attributes = AttributeCollection()
    attributes.add(NextHop.from_string('192.0.2.2'))
    attributes.add(LocalPreference.from_int(preference))
    return Route(path(identifier, prefix), attributes, IP.create_ip(IP.pton('192.0.2.2')))


def sent(rib: OutgoingRIB, negotiated: Negotiated) -> list[tuple[str, str]]:
    """What one batch puts on the wire: ('+', prefix local-preference) or ('-', prefix)."""
    wire: list[tuple[str, str]] = []
    for update in rib.updates(False, negotiated.paths_limit or None, negotiated):
        assert isinstance(update, UpdateCollection)
        for nlri in update.withdraws:
            wire.append(('-', bytes(nlri.pack_nlri(negotiated)).hex()))
        for routed in update.announces:
            preference = str(update.attributes[LocalPreference.ID].value)
            wire.append(('+', f'{bytes(routed.nlri.pack_nlri(negotiated)).hex()} {preference}'))
    return wire


PREFIX = '180a0000'  # 10.0.0.0/24 as the wire carries it without a Path Identifier


def without_addpath() -> Negotiated:
    return negotiation.negotiated()


@pytest.mark.rfc('rfc4271#9.2-same-route-not-advertised-again')
def test_paths_of_one_prefix_go_once_to_a_peer_without_add_path() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(2, 200))

    assert sent(rib, without_addpath()) == [('+', f'{PREFIX} 100')]


@pytest.mark.rfc('rfc4271#9.2-unfeasible-without-replacement-advertised')
def test_withdrawing_the_path_sent_sends_the_one_left_instead_of_a_withdrawal() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    negotiated = without_addpath()
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(2, 200))
    sent(rib, negotiated)

    rib.del_from_rib(route(1, 100))

    assert sent(rib, negotiated) == [('+', f'{PREFIX} 200')]


@pytest.mark.rfc('rfc4271#9.2-unfeasible-without-replacement-advertised', polarity='negative')
def test_withdrawing_the_last_path_withdraws_the_prefix() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    negotiated = without_addpath()
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(2, 200))
    sent(rib, negotiated)

    rib.del_from_rib(route(2, 200))
    assert sent(rib, negotiated) == [], 'path 2 was never sent, it has nothing to withdraw'

    rib.del_from_rib(route(1, 100))
    assert sent(rib, negotiated) == [('-', PREFIX)]


@pytest.mark.rfc('rfc4271#9.2-unfeasible-without-replacement-advertised', polarity='negative')
def test_both_paths_withdrawn_in_one_batch_withdraw_the_prefix_once() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    negotiated = without_addpath()
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(2, 200))
    sent(rib, negotiated)

    rib.del_from_rib(route(1, 100))
    rib.del_from_rib(route(2, 200))

    assert sent(rib, negotiated) == [('-', PREFIX)]


@pytest.mark.rfc('rfc4271#9.2-same-route-not-advertised-again', polarity='negative')
def test_the_path_sent_changing_its_attributes_is_sent_again() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    negotiated = without_addpath()
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(2, 200))
    sent(rib, negotiated)

    rib.add_to_rib(route(1, 300))

    assert sent(rib, negotiated) == [('+', f'{PREFIX} 300')]


def test_paths_of_different_prefixes_are_all_sent() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(1, 100, '10.0.1.0/24'))

    assert sent(rib, without_addpath()) == [('+', f'{PREFIX} 100'), ('+', '180a0001 100')]


def test_a_peer_with_add_path_send_is_sent_every_path() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    negotiated = negotiation.negotiated(addpath_send=[IPV4_UNICAST])
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(2, 200))

    assert sent(rib, negotiated) == [('+', f'00000001{PREFIX} 100'), ('+', f'00000002{PREFIX} 200')]


def test_a_new_session_is_sent_one_path_again() -> None:
    rib = OutgoingRIB(True, {IPV4_UNICAST})
    negotiated = without_addpath()
    rib.add_to_rib(route(1, 100))
    rib.add_to_rib(route(2, 200))
    sent(rib, negotiated)

    rib.session_reset()
    rib.resend(False)

    assert sent(rib, negotiated) == [('+', f'{PREFIX} 100')]
