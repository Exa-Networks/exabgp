"""An attribute given as its wire bytes, `attribute [ 0x<code> 0x<flag> 0x<data> ]`.

exabgp builds MP_REACH_NLRI and MP_UNREACH_NLRI from the routes, and AS4_PATH and
AS4_AGGREGATOR from `as-path` and `aggregator`, each for the session it packs for. A raw
attribute with one of those codes was sent as well: AS4_PATH and AS4_AGGREGATOR to a
four-octet peer (RFC 6793 4.1), and next to the ones exabgp made to a two-octet peer or for
a multiprotocol family, the same code twice in one UPDATE (RFC 4271 5). Those four codes
are now refused, by the configuration and by the API, and no other code can be sent twice.
"""

from __future__ import annotations

from collections import Counter
from typing import Iterator

import pytest

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB

from tests.api_daemon import SECOND, Daemon

# made by exabgp for the session it packs for, never taken as bytes
GENERATED = (
    Attribute.CODE.MP_REACH_NLRI,
    Attribute.CODE.MP_UNREACH_NLRI,
    Attribute.CODE.AS4_PATH,
    Attribute.CODE.AS4_AGGREGATOR,
)

# a four-octet AS, so a two-octet session is sent AS4_PATH and AS4_AGGREGATOR
ROUTES = {
    'ipv4 unicast;': 'route 10.0.0.0/24 next-hop 192.0.2.9 as-path [ 4200000000 ] aggregator ( 4200000000:192.0.2.9 )',
    'ipv6 unicast;': 'route 2001:db8::/32 next-hop 2001:db8::9 as-path [ 4200000000 ] '
    'aggregator ( 4200000000:192.0.2.9 )',
}


def configuration(family: str, route: str, asn4: bool = True) -> tuple[bool, Configuration]:
    capability = '' if asn4 else 'capability { asn4 disable; }'
    text = (
        'neighbor 192.0.2.1 { router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; '
        f'{capability} family {{ {family} }} static {{ {route}; }} }}'
    )
    # the RIB of a neighbour is kept by name across reads, and these all have the same name
    RIB._cache.clear()
    parsed = Configuration([text], text=True)
    return parsed.reload(), parsed


def attribute_codes(message: bytes) -> list[int]:
    """The type codes of the path attributes of an UPDATE, its header included."""
    body = message[19:]
    withdrawn_size = int.from_bytes(body[0:2], 'big')
    position = 2 + withdrawn_size
    attributes_size = int.from_bytes(body[position : position + 2], 'big')
    position += 2
    end = position + attributes_size
    codes = []
    while position < end:
        flag, code = body[position], body[position + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            size = int.from_bytes(body[position + 2 : position + 4], 'big')
            position += 4
        else:
            size = body[position + 2]
            position += 3
        codes.append(code)
        position += size
    assert position == end, 'the attributes did not end where their length said'
    return codes


def sent_codes(parsed: Configuration) -> list[list[int]]:
    """The attribute codes of every UPDATE the neighbour sends for its routes."""
    (neighbor,) = parsed.neighbors.values()
    _, negotiated = _negotiated(neighbor)
    for route in neighbor.routes:
        neighbor.rib.outgoing.add_to_rib(neighbor.resolve_self(route))
    sent = []
    for update in neighbor.rib.outgoing.updates(False, negotiated=negotiated):
        for message in update.messages(negotiated, True):
            sent.append(attribute_codes(message))
    return sent


@pytest.mark.rfc('rfc6793#4.1-no-as4-attributes-between-new-speakers', polarity='negative')
@pytest.mark.rfc('rfc4271#5-an-attribute-at-most-once', polarity='negative')
@pytest.mark.parametrize('code', GENERATED)
@pytest.mark.parametrize('family', list(ROUTES))
def test_a_raw_attribute_exabgp_generates_is_refused(code: int, family: str) -> None:
    loaded, parsed = configuration(family, f'{ROUTES[family]} attribute [ 0x{code:02x} 0xc0 0x00000001 ]')
    assert not loaded, f'attribute 0x{code:02x} was taken as bytes'
    assert 'made by exabgp' in str(parsed.error), parsed.error


@pytest.fixture
def daemon() -> Iterator[Daemon]:
    created = Daemon()
    yield created
    created.close()


@pytest.mark.rfc('rfc6793#4.1-no-as4-attributes-between-new-speakers', polarity='negative')
@pytest.mark.parametrize('code', GENERATED)
def test_the_api_refuses_a_raw_attribute_exabgp_generates(daemon: Daemon, code: int) -> None:
    lines = daemon.send(
        f'neighbor {SECOND} announce route 10.0.0.0/24 next-hop 192.0.2.9 attribute [ 0x{code:02x} 0xc0 0x00000001 ]'
    )
    assert lines[-1] == 'error', lines
    assert daemon.announced(SECOND) == []


@pytest.mark.rfc('rfc4271#5-an-attribute-at-most-once')
@pytest.mark.rfc('rfc6793#4.1-no-as4-attributes-between-new-speakers')
@pytest.mark.parametrize('asn4', [True, False], ids=['four-octet', 'two-octet'])
@pytest.mark.parametrize('family', list(ROUTES))
def test_no_raw_attribute_makes_a_code_appear_twice(family: str, asn4: bool) -> None:
    """Every code a raw attribute may have, next to everything exabgp generates for a route."""
    checked = 0
    for code in range(1, 256):
        if code in GENERATED:
            continue
        loaded, parsed = configuration(family, f'{ROUTES[family]} attribute [ 0x{code:02x} 0xc0 0x00000001 ]', asn4)
        if not loaded:
            # the codes of as-path, next-hop and aggregator, given twice
            assert 'given twice' in str(parsed.error), parsed.error
            continue
        for codes in sent_codes(parsed):
            repeated = [each for each, count in Counter(codes).items() if count > 1]
            assert not repeated, f'attribute 0x{code:02x} made {repeated} appear twice: {codes}'
            if asn4:
                assert Attribute.CODE.AS4_PATH not in codes
                assert Attribute.CODE.AS4_AGGREGATOR not in codes
        checked += 1
    # not a sweep which ran nothing: the codes exabgp has no keyword for were all sent
    assert checked > 200
