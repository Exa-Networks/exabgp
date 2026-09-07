"""Property based tests covering every registered attribute and extended community decoder.

`tests/fuzz/test_nlri_decoder_properties.py` holds every NLRI decoder to the rule that what
it accepts, it must be able to render: a decoded NLRI has to survive `json()`, `str()`,
`repr()`, `index()` and `hash()`.  Nothing held the *attribute* decoders to the same rule,
and that is the gap issue #1426 fell through.  A `traffic-rate` extended community carrying
a NaN decoded happily and then raised `ValueError` out of `'rate-limit:%d' % self.rate`,
inside the API writer, outside the decode boundary, where no NOTIFICATION can be sent.

The rule is the same one, stated for attributes: **an attribute section which decodes must
render.**  Whether the bytes are accepted is the decoder's business, and
`AttributeCollection.parse` deliberately treats `IndexError` and `ValueError` out of a
decoder as the RFC 7606 discard and treat-as-withdraw paths.  What happens *after* a
successful decode is not negotiable.

The rendering is driven through `AttributeCollection`, not through the attribute object, on
purpose.  The collection decides per attribute code whether the JSON comes from `json()` or
from `str()`, so an attribute which raises `NotImplementedError: must implement json()`
called directly may be perfectly renderable in the only place it is ever rendered.  Asking
the object is a test of the test; asking the collection is the path `Processes.message()`
takes, which is where #1426 died.

Note what a sweep over `st.binary()` alone would have done here, because it is the trap
TIGER_STYLE section 5 warns about.  An extended community is looked up by its first two
bytes, so random bytes land on a registered subtype roughly once in sixty five thousand
draws: two hundred examples per code would have swept the traffic-rate decoder zero times
and reported a clean run.  The community strategies below therefore *build* a header for
each registered (type, subtype) and fuzz only the value, which is what puts the decoder
under test rather than the dispatch in front of it.
"""

from __future__ import annotations

import json as jsonlib

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest
from hypothesis import given, strategies as st

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunityIPv6

pytestmark = pytest.mark.fuzz

# The (attribute id, flag) pairs the parser will dispatch on, in a stable order.
REGISTERED_ATTRIBUTES = sorted(Attribute.registered_attributes)
ATTRIBUTE_IDS = [f'{aid}/0x{flag:02X}' for aid, flag in REGISTERED_ATTRIBUTES]

# The (type & 0x0F, subtype) pairs an extended community is dispatched on.
REGISTERED_COMMUNITIES = sorted(ExtendedCommunity.registered_extended)
COMMUNITY_IDS = [f'0x{low:02X}/0x{subtype:02X}' for low, subtype in REGISTERED_COMMUNITIES]

REGISTERED_COMMUNITIES_IPV6 = sorted(ExtendedCommunityIPv6.registered_extended)
COMMUNITY_IPV6_IDS = [f'0x{low:02X}/0x{subtype:02X}' for low, subtype in REGISTERED_COMMUNITIES_IPV6]

# Ratchets: raise them as decoders are added, never lower them.  A parametrised sweep over
# a registry which failed to fill does not fail, it silently shrinks to a fraction of the
# codes and still reports green.
MIN_ATTRIBUTES = 22
MIN_COMMUNITIES = 24
MIN_COMMUNITIES_IPV6 = 2

EXTENDED_LENGTH = 0x10
OPTIONAL_TRANSITIVE = 0xC0

EXTENDED_COMMUNITY_VALUE_SIZE_BYTES = 6
EXTENDED_COMMUNITY_IPV6_VALUE_SIZE_BYTES = 18

EXTENDED_COMMUNITY = int(Attribute.CODE.EXTENDED_COMMUNITY)
IPV6_EXTENDED_COMMUNITY = int(Attribute.CODE.IPV6_EXTENDED_COMMUNITY)

# Uniform bytes are a poor way to build the values which break a decoder.  An IEEE-754
# single is a NaN or an infinity only when its exponent is all ones, which needs one of two
# values in one byte and one of two in the next: measured at 0.39% of draws, so two hundred
# examples find it 54% of the time.  Removing the traffic-rate fix and watching this file go
# red was therefore a coin toss, which is the same as not watching.  Half the draws come
# from the byte values which sit on the boundaries instead.
INTERESTING_BYTES = [0x00, 0x01, 0x7F, 0x80, 0xFF]


def payload(min_size_bytes: int, max_size_bytes: int) -> st.SearchStrategy[bytes]:
    """Uniform bytes or boundary bytes, so the awkward values are actually reached."""
    return st.one_of(
        st.binary(min_size=min_size_bytes, max_size=max_size_bytes),
        st.lists(st.sampled_from(INTERESTING_BYTES), min_size=min_size_bytes, max_size=max_size_bytes).map(bytes),
    )


def negotiated() -> Any:
    """A session just complete enough for the decoders which look at one."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value=False)
    neighbor.session = Mock()
    neighbor.session.local_address = None

    session = Mock()
    session.neighbor = neighbor
    session.families = [(1, 1)]
    session.asn4 = True
    session.aigp = False
    session.msg_size = 4096
    session.nexthop = []
    session.required = Mock(return_value=False)
    session.addpath = Mock()
    session.addpath.receive = Mock(return_value=False)
    session.addpath.send = Mock(return_value=False)
    return session


def section(flag: int, aid: int, value: bytes) -> bytes:
    """One attribute, framed the way it arrives inside an UPDATE."""
    if flag & EXTENDED_LENGTH:
        return bytes([flag, aid]) + pack('!H', len(value)) + value
    return bytes([flag, aid, len(value)]) + value


def parses(fragment: str) -> None:
    """A json() fragment must be readable by the API consumer it is written to.

    The fragments are members of a larger object, so they are wrapped before parsing.
    """
    for candidate in (fragment, '{' + fragment + '}', '[' + fragment + ']'):
        try:
            jsonlib.loads(candidate)
            return
        except ValueError:
            continue
    raise AssertionError(f'json() returned something no JSON parser accepts: {fragment[:200]}')


def decodes(flag: int, aid: int, value: bytes) -> AttributeCollection | None:
    """The attributes the reactor would hold, or None when the peer's bytes were refused.

    Notify closes the session with a NOTIFICATION.  IndexError and ValueError are the
    RFC 7606 discard and treat-as-withdraw paths `AttributeCollection.parse` catches on
    purpose.  All three are the decoder doing its job.
    """
    try:
        return AttributeCollection().parse(section(flag, aid, value), negotiated())
    except (Notify, IndexError, ValueError):
        return None


def renders(attributes: AttributeCollection, what: str) -> None:
    """Every rendering the API and the log reach for, none of which may raise.

    What is pinned is not the text, it is that no exception escapes: whatever the decoder
    accepted, the process must be able to print it without dying somewhere the peer cannot
    be told about.
    """
    try:
        parses(attributes.json())
        parses(attributes.json(include_nexthop=True))
        str(attributes)
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001 - which exception escapes is the whole point
        raise AssertionError(f'{what} decoded but {type(exc).__name__} escaped its rendering: {exc}') from exc


@pytest.mark.parametrize('registered', REGISTERED_ATTRIBUTES, ids=ATTRIBUTE_IDS)
@given(value=payload(0, 64))
def test_a_decoded_attribute_can_be_rendered(registered: tuple[int, int], value: bytes) -> None:
    """What an attribute decoder accepts, the API writer must be able to print."""
    aid, flag = registered
    attributes = decodes(flag, aid, value)
    if attributes is None:
        return
    renders(attributes, f'attribute {aid} with value {value.hex()}')


@pytest.mark.parametrize('registered', REGISTERED_COMMUNITIES, ids=COMMUNITY_IDS)
@given(
    high_nibble=st.integers(min_value=0, max_value=0x0F),
    value=payload(EXTENDED_COMMUNITY_VALUE_SIZE_BYTES, EXTENDED_COMMUNITY_VALUE_SIZE_BYTES),
)
def test_a_decoded_extended_community_can_be_rendered(
    registered: tuple[int, int], high_nibble: int, value: bytes
) -> None:
    """The header is built rather than drawn, so the decoder under test is actually entered.

    Dispatch masks the type with 0x0F, so the high nibble is drawn as well: traffic-rate is
    registered as (0x00, 0x06) and arrives on the wire as 0x80 0x06.
    """
    low, subtype = registered
    community = bytes([(high_nibble << 4) | low, subtype]) + value
    attributes = decodes(OPTIONAL_TRANSITIVE, EXTENDED_COMMUNITY, community)
    if attributes is None:
        return
    renders(attributes, f'extended community {community.hex()}')


@pytest.mark.parametrize('registered', REGISTERED_COMMUNITIES_IPV6, ids=COMMUNITY_IPV6_IDS)
@given(
    high_nibble=st.integers(min_value=0, max_value=0x0F),
    value=payload(EXTENDED_COMMUNITY_IPV6_VALUE_SIZE_BYTES, EXTENDED_COMMUNITY_IPV6_VALUE_SIZE_BYTES),
)
def test_a_decoded_ipv6_extended_community_can_be_rendered(
    registered: tuple[int, int], high_nibble: int, value: bytes
) -> None:
    """RFC 5701 communities are twenty bytes and get the same treatment."""
    low, subtype = registered
    community = bytes([(high_nibble << 4) | low, subtype]) + value
    attributes = decodes(OPTIONAL_TRANSITIVE, IPV6_EXTENDED_COMMUNITY, community)
    if attributes is None:
        return
    renders(attributes, f'ipv6 extended community {community.hex()}')


@pytest.mark.registry_floor
def test_the_registries_this_file_parametrises_from_are_whole() -> None:
    """A parametrised sweep over a half filled registry shrinks, it does not fail.

    The registries fill by import side effect, so a module which imports only what it names
    sweeps a fraction of the codes and the summary line reads exactly the same.
    """
    assert len(REGISTERED_ATTRIBUTES) >= MIN_ATTRIBUTES, (
        f'only {len(REGISTERED_ATTRIBUTES)} attributes are registered, so this file sweeps a fraction of them'
    )
    assert len(REGISTERED_COMMUNITIES) >= MIN_COMMUNITIES, (
        f'only {len(REGISTERED_COMMUNITIES)} extended communities are registered, so this file sweeps a fraction'
    )
    assert len(REGISTERED_COMMUNITIES_IPV6) >= MIN_COMMUNITIES_IPV6, (
        f'only {len(REGISTERED_COMMUNITIES_IPV6)} ipv6 extended communities are registered'
    )
