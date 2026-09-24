"""RFC 1997: the one sentence in it which binds the bytes exabgp puts on the wire.

RFC 1997 is four pages and says less than its reputation suggests.  It has three
capitalised MUST NOTs, all about not re-advertising a route carrying a well-known
community, which exabgp cannot breach because it never re-advertises anything.  What it
does not have, anywhere, is the rule it is usually cited for: that the COMMUNITIES
attribute length is a multiple of four.  The document states the encoding flatly - "The
attribute consists of a set of four octet values" - with no keyword, so there is no
requirement in RFC 1997 to record for it.  The normative form of that rule is RFC 7606
section 7.8.  The last two tests in this file still pin the behaviour, without an
`rfc()` marker, because the behaviour is worth a regression test wherever the sentence
that demands it lives.

That leaves one recordable obligation with teeth:

    The rest of the community attribute values shall be encoded using an autonomous
    system number in the first two octets.

"The rest" is what survives the two reserved ranges named in the sentence before it, so
the well-known values are outside its scope, and `ASN:value` in the configuration is how
exabgp implements it.

Two of the tests below are `xfail`.  `_community` bounds both halves of `ASN:value`
against `Community.MAX`, which is 0xFFFFFFFF, when each half is sixteen bits.  Nothing in
the function is sixteen bit aware, so the check never fires for a value which overflows
its half, and the two failures fall out of the same wrong constant:

    community 1:65536   is encoded as 0x00020000 and reported back as 2:0
    community 65536:1   escapes the configuration parser as a struct.error

The first is the serious one.  A typo in a configuration file does not produce an error,
it produces a community belonging to a different autonomous system, announced to every
peer, and the daemon reports the value it invented rather than the value that was typed.
"""

from __future__ import annotations

import re
from struct import pack

import pytest

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.community import Communities, Community
from exabgp.configuration.static.parser import _community

from rfc.community_wire import parse, withdrawn

COMMUNITY = int(Attribute.CODE.COMMUNITY)
COMMUNITY_SIZE_BYTES = 4

# RFC 1997: "The community attribute values ranging from 0x0000000 through 0x0000FFFF
# and 0xFFFF0000 through 0xFFFFFFFF are hereby reserved."  Everything outside these is
# what "the rest" in the requirement refers to.
RESERVED_LOW_LAST = 0x0000FFFF
RESERVED_HIGH_FIRST = 0xFFFF0000

# <asn>:<value> pairs which are all outside the reserved ranges, so all in scope.
ASSIGNABLE = [
    (1, 0),
    (64496, 1234),
    (65000, 666),
    (65534, 65535),
]

WELL_KNOWN = [
    ('no-export', Community.NO_EXPORT),
    ('no-advertise', Community.NO_ADVERTISE),
    ('no-export-subconfed', Community.NO_EXPORT_SUBCONFED),
    ('blackhole', Community.BLACKHOLE),
]

CANONICAL = re.compile(r'^\d+:\d+$')


@pytest.mark.rfc('rfc1997#values-encoded-with-asn')
@pytest.mark.parametrize('asn,value', ASSIGNABLE, ids=[f'{a}:{v}' for a, v in ASSIGNABLE])
def test_a_configured_community_carries_the_asn_in_the_first_two_octets(asn: int, value: int) -> None:
    """`<asn>:<value>` in the configuration puts that ASN, and no other, in octets 0 and 1."""
    packed = bytes(_community(f'{asn}:{value}').community)

    assert len(packed) == COMMUNITY_SIZE_BYTES
    assert int.from_bytes(packed[:2], 'big') == asn, (
        f'{asn}:{value} was encoded as {packed.hex()}, whose first two octets are '
        f'AS {int.from_bytes(packed[:2], "big")} rather than the AS which was configured'
    )
    assert int.from_bytes(packed[2:], 'big') == value


@pytest.mark.rfc('rfc1997#values-encoded-with-asn')
@pytest.mark.parametrize('asn,value', ASSIGNABLE, ids=[f'{a}:{v}' for a, v in ASSIGNABLE])
def test_a_community_off_the_wire_is_read_back_as_the_same_asn(asn: int, value: int) -> None:
    """The decode direction of the same rule: octets 0 and 1 are read as the ASN.

    A packer and a reader which disagree about where the ASN lives would each pass their
    own half of this file, so the round trip is the assertion that matters.
    """
    rendered = repr(Community(pack('!HH', asn, value)))

    assert CANONICAL.match(rendered), f'{rendered!r} is not <asn>:<value>'
    assert rendered == f'{asn}:{value}'


@pytest.mark.rfc('rfc1997#values-encoded-with-asn')
@pytest.mark.parametrize('name,packed', WELL_KNOWN, ids=[name for name, _ in WELL_KNOWN])
def test_a_reserved_value_is_not_given_the_asn_reading(name: str, packed: bytes) -> None:
    """The requirement says "the rest", so the reserved ranges are outside it.

    All five well-known values live in 0xFFFF0000-0xFFFFFFFF.  Reading 0xFFFFFF01 as
    "AS 65535, community 65281" would be applying the ASN convention where the RFC
    excludes it, and would put a reserved value into an operator's AS namespace.
    """
    value = int.from_bytes(packed, 'big')

    assert value >= RESERVED_HIGH_FIRST or value <= RESERVED_LOW_LAST, f'{name} is not in a range RFC 1997 reserves'
    assert repr(Community(packed)) == name, 'a reserved value was rendered as an ASN pair'


@pytest.mark.rfc('rfc1997#values-encoded-with-asn', polarity='negative')
def test_a_value_too_large_for_its_half_does_not_overflow_into_the_asn() -> None:
    """16 bits of value must not carry into the 16 bits of ASN above it.

    This is the failure which matters, because it is silent.  `community 1:65536` is
    accepted, announced to every peer as 0x00020000, and reported back through the API as
    2:0, so the operator is told a community they did not configure, belonging to an AS
    they do not hold.
    """
    with pytest.raises(ValueError):
        _community('1:65536')


@pytest.mark.rfc('rfc1997#values-encoded-with-asn', polarity='negative')
def test_an_asn_too_large_for_two_octets_is_refused_by_the_parser() -> None:
    """A 32 bit ASN does not fit the first two octets, so the configuration is invalid.

    EXA_STYLE 1.2: bad operator configuration raises `ValueError` with the parser
    context.  `struct.error` is neither, and `configuration/core/section.py` only catches
    `ValueError`, so this one leaves the parser as an unhandled exception rather than as
    a message naming the line which is wrong.
    """
    with pytest.raises(ValueError):
        _community('65536:1')


# ---------------------------------------------------------------------------
# No rfc() marker below this line.  RFC 1997 nowhere states the multiple-of-four rule
# with a keyword; RFC 7606 section 7.8 does, and that ledger is elsewhere.  The tests
# stay because the code they cover is here.


@pytest.mark.parametrize('count', [1, 2, 8])
def test_a_whole_number_of_communities_is_accepted(count: int) -> None:
    value = bytes(count * COMMUNITY_SIZE_BYTES)
    collection = parse(COMMUNITY, value)

    assert not withdrawn(collection), f'{len(value)} bytes of COMMUNITY were refused'
    decoded = collection[Attribute.CODE.COMMUNITY]
    assert isinstance(decoded, Communities)
    assert len(decoded.communities) == count


@pytest.mark.parametrize('length', [0, 1, 3, 5, 7, 9])
def test_a_length_which_is_not_a_whole_number_of_communities_withdraws_the_route(length: int) -> None:
    """Treat-as-withdraw, not a NOTIFICATION: this is an optional transitive attribute.

    Zero is in the list on purpose.  `Communities.from_packet` accepts it, because
    0 % 4 == 0; what refuses it is `VALID_ZERO` being false on the class, checked by
    `AttributeCollection.parse` before the decoder is reached.  Split across two places
    like that, the zero case is the one a refactor drops.
    """
    assert withdrawn(parse(COMMUNITY, bytes(length))), f'{length} bytes of COMMUNITY were accepted'
