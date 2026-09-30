"""The paths of JSON._update, pinned by their exact output.

JSON._update renders a received UPDATE for the API.  Measured with branch coverage on
2026-09-29, the JSON tests (test_json_update.py, the link-local next-hop, RFC 9234 and
decode tests) never ran an UPDATE which announces and withdraws at once, so the comma
between "announce" and "withdraw" was never written, nor the branch which renders an
End-of-RIB from `nlris` when nothing was announced or withdrawn.  The tests beside them
check the shape of the output, not its text.

These tests pin the text, byte for byte, for every path, before the function is split into
helpers (plan-large-function-decomposition).  They pin what it does today: the doubled space
of an empty UPDATE and the unparseable JSON of the `nlris` branch included.
"""

from __future__ import annotations

import socket
from types import SimpleNamespace
from typing import Any

from exabgp.bgp.message.update.attribute import AttributeCollection, NextHop, Origin
from exabgp.bgp.message.update.collection import RouteLeak, RoutedNLRI, UpdateCollection
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IPv4, IPv6
from exabgp.reactor.api.response.json import JSON
from exabgp.bgp.message.update.attribute.aspath import AS4Path

LEAK = (
    '"meta": {"route-leak": {"reason": "invalid-otc", "peer-role": "customer", "peer-as": "AS1", '
    '"expected-otc": "none", "received-otc": "AS2"}}'
)


def _v4(prefix: str) -> INET:
    return INET.from_cidr(CIDR.create_cidr(socket.inet_aton(prefix), 24), AFI.ipv4, SAFI.unicast)


def _v6(prefix: str) -> INET:
    return INET.from_cidr(CIDR.create_cidr(socket.inet_pton(socket.AF_INET6, prefix), 32), AFI.ipv6, SAFI.unicast)


def _attributes(nexthop: str | None = None) -> AttributeCollection:
    attributes = AttributeCollection()
    attributes.add(Origin.from_int(Origin.IGP))
    if nexthop is not None:
        attributes.add(NextHop.from_string(nexthop))
    return attributes


def _mixed() -> UpdateCollection:
    """Two families announced, one next-hop shared by two routes, two families withdrawn."""
    return UpdateCollection(
        [
            RoutedNLRI(_v4('10.0.0.0'), IPv4.from_string('1.1.1.1')),
            RoutedNLRI(_v6('2001:db8::'), IPv6.from_string('2001:db8::1')),
            RoutedNLRI(_v4('10.0.1.0'), IPv4.from_string('1.1.1.1')),
            RoutedNLRI(_v4('10.0.2.0'), IPv4.from_string('2.2.2.2')),
        ],
        [_v4('10.9.0.0'), _v6('2001:db9::')],
        _attributes('1.1.1.1'),
    )


def _message(update: Any, include_meta: bool = True, encoder: JSON | None = None) -> str:
    result = (encoder or JSON('6.0.0'))._update(update, include_meta=include_meta)
    assert list(result) == ['message']
    return result['message']


MIXED = (
    '{ "update": { "attribute": { "origin": "igp", "next-hop": "1.1.1.1" }, "announce": { '
    '"ipv4 unicast": { "1.1.1.1": [ { "nlri": "10.0.0.0/24" }, { "nlri": "10.0.1.0/24" } ], '
    '"2.2.2.2": [ { "nlri": "10.0.2.0/24" } ] }, '
    '"ipv6 unicast": { "2001:db8::1": [ { "nlri": "2001:db8::/32" } ] } }, '
    '"withdraw": { "ipv4 unicast": [ { "nlri": "10.9.0.0/24" } ], '
    '"ipv6 unicast": [ { "nlri": "2001:db9::/32" } ] } } }'
)


def test_announce_and_withdraw_in_one_update() -> None:
    assert _message(_mixed()) == MIXED


def test_a_route_leak_is_reported_on_the_announces_of_its_family_only() -> None:
    update = _mixed()
    update.route_leaks = {(AFI.ipv4, SAFI.unicast): RouteLeak('customer', 'AS1', 'none', 'AS2')}
    expected = MIXED.replace(
        '{ "nlri": "10.0.0.0/24" }, { "nlri": "10.0.1.0/24" } ], "2.2.2.2": [ { "nlri": "10.0.2.0/24" } ]',
        f'{{"nlri": "10.0.0.0/24", {LEAK}}}, {{"nlri": "10.0.1.0/24", {LEAK}}} ], '
        f'"2.2.2.2": [ {{"nlri": "10.0.2.0/24", {LEAK}}} ]',
    )
    assert expected != MIXED
    assert _message(update) == expected


def test_a_route_leak_is_not_reported_without_meta() -> None:
    update = _mixed()
    update.route_leaks = {(AFI.ipv4, SAFI.unicast): RouteLeak('customer', 'AS1', 'none', 'AS2')}
    assert _message(update, include_meta=False) == MIXED


def test_an_announce_hides_the_next_hop_attribute() -> None:
    update = UpdateCollection([RoutedNLRI(_v4('10.0.0.0'), IPv4.from_string('1.1.1.1'))], [], _attributes('1.1.1.1'))
    assert _message(update) == (
        '{ "update": { "attribute": { "origin": "igp" }, '
        '"announce": { "ipv4 unicast": { "1.1.1.1": [ { "nlri": "10.0.0.0/24" } ] } } } }'
    )


def test_a_withdraw_shows_the_next_hop_attribute() -> None:
    update = UpdateCollection([], [_v4('10.0.0.0')], _attributes('1.1.1.1'))
    assert _message(update) == (
        '{ "update": { "attribute": { "origin": "igp", "next-hop": "1.1.1.1" }, '
        '"withdraw": { "ipv4 unicast": [ { "nlri": "10.0.0.0/24" } ] } } }'
    )


def test_a_withdraw_without_attributes() -> None:
    update = UpdateCollection([], [_v4('10.0.0.0')], AttributeCollection())
    assert _message(update) == '{ "update": { "withdraw": { "ipv4 unicast": [ { "nlri": "10.0.0.0/24" } ] } } }'


def test_attributes_only() -> None:
    assert _message(UpdateCollection([], [], _attributes())) == '{ "update": { "attribute": { "origin": "igp" } } }'


def test_an_empty_update() -> None:
    assert _message(UpdateCollection([], [], AttributeCollection())) == '{ "update": {  } }'


def test_the_attribute_format_and_next_hop_flag_are_passed_on() -> None:
    # an AS4_PATH prints as its path, or as its hex in the generic format, and the next-hop
    # is only listed with the attributes of a withdraw: each flag changes what is printed
    attributes = AttributeCollection()
    attributes.add(Origin.from_int(Origin.IGP))
    attributes.add(NextHop.from_string('1.1.1.1'))
    attributes.add(AS4Path.from_packet(bytes([2, 1, 0, 0, 0xFD, 0xE8])))
    encoder = JSON('6.0.0')
    encoder.generic_attribute_format = True
    announce = UpdateCollection([RoutedNLRI(_v4('10.0.0.0'), IPv4.from_string('1.1.1.1'))], [], attributes)
    withdraw = UpdateCollection([], [_v4('10.0.0.0')], attributes)
    announced = '"origin": "igp", "attribute-0x11-0xC0": "0x02010000fde8"'
    withdrawn = '"origin": "igp", "next-hop": "1.1.1.1", "attribute-0x11-0xC0": "0x02010000fde8"'
    assert _message(announce, encoder=encoder).startswith(f'{{ "update": {{ "attribute": {{ {announced} }}, "announce"')
    assert _message(withdraw, encoder=encoder).startswith(f'{{ "update": {{ "attribute": {{ {withdrawn} }}, "withdraw"')


def test_an_end_of_rib_collection() -> None:
    assert _message(UpdateCollection.make_eor(AFI.ipv6, SAFI.unicast)) == (
        '{ "update": { "announce": { "ipv6 unicast": { "null": '
        '[ { "eor": { "afi" : "ipv6", "safi" : "unicast" } } ] } } } }'
    )


def test_an_end_of_rib_message() -> None:
    # EOR is an Update, not an UpdateCollection: it has no announces and no route_leaks
    assert _message(EOR.make_eor(AFI.ipv4, SAFI.unicast)) == (
        '{ "update": { "announce": { "ipv4 unicast": { "null": '
        '[ { "eor": { "afi" : "ipv4", "safi" : "unicast" } } ] } } } }'
    )


def test_nlris_with_nothing_announced_or_withdrawn() -> None:
    # No real UPDATE reaches this branch: an UpdateCollection's nlris are its announces and
    # withdraws, and an End-of-RIB puts its one NLRI in the announces.  Pinned with a stand-in
    # so a split keeps it, output (not valid JSON) and all.
    update = SimpleNamespace(
        IS_EOR=False,
        announces=[],
        withdraws=[],
        nlris=[EOR.EOR_NLRI(AFI.ipv4, SAFI.unicast)],
        attributes=_attributes(),
        route_leaks=None,
    )
    assert _message(update) == '{ { "eor": { "afi" : "ipv4", "safi" : "unicast" } } }'
