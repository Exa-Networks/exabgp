"""The BGP-LS merge groups by JSON key, which is only safe while every key is real.

LinkState.json() collects the TLVs which set MERGE and groups them by their JSON name, so
that the alias pairs registered under two codes each (1028/1029 local router id, 1030/1031
remote router id) land in one array rather than emitting the same key twice.

Session 5.0 found the trap in the version of this which groups on TLV code instead: the
registration decorator builds a distinct class per code, so the two aliases are siblings
and never compare equal, and the merge silently never fired for the exact pair it exists
to join.  Grouping by JSON name is the fix, and it carries its own trap: a MERGE class
which never sets JSON inherits BaseLS.JSON, and every such class would group together
under one meaningless key.

Neither shows up in the recorded fixtures, because none of them carries two of these TLVs
at once.  A green sweep proves the property held for the data it saw, never that the
mechanism you believe is holding it is the one doing the work.
"""

from __future__ import annotations

import importlib
import json as jsonlib
import pkgutil
from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState, jsonable


def _populate() -> None:
    import exabgp.bgp.message.update.attribute as package

    for _finder, name, _is_package in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            importlib.import_module(name)
        except ImportError:
            continue


_populate()

MERGE_CODES = sorted(code for code, klass in LinkState.registered_lsids.items() if getattr(klass, 'MERGE', False))
MERGE_IDS = [f'{code}-{LinkState.registered_lsids[code].__name__}' for code in MERGE_CODES]

# the pairs which are deliberately one key under two codes
ALIAS_PAIRS = [(1028, 1029), (1030, 1031)]

TLV_HEADER = 4
MAX_TLV_WIDTH = 40


def attribute() -> type[Attribute]:
    klass = Attribute.klass_by_id(Attribute.CODE.BGP_LS)
    assert klass is not None
    return klass


def render(tlvs: bytes) -> str:
    return attribute().unpack_attribute(tlvs, Negotiated.UNSET).json()


def smallest_decodable(code: int) -> bytes | None:
    """The shortest payload this TLV accepts, so the test does not guess its width."""
    # the widths a MERGE TLV can hold, from one byte to the SRv6 LAN End.X sub-TLVs,
    # which need 26 and 28 and are the reason this searches rather than guessing
    for length in range(1, MAX_TLV_WIDTH):
        payload = pack('!HH', code, length) + bytes(length)
        try:
            attribute().unpack_attribute(payload, Negotiated.UNSET).json()
        except Exception:
            continue
        return payload
    return None


def test_no_merge_class_groups_under_the_unset_key() -> None:
    """A MERGE class with no JSON name would be grouped with every other one.

    This is the whole safety condition for grouping by name, and it is one forgotten
    class attribute away from silently collapsing unrelated TLVs into a single member.
    """
    unnamed = [
        (code, klass.__name__)
        for code, klass in sorted(LinkState.registered_lsids.items())
        if getattr(klass, 'MERGE', False) and getattr(klass, 'JSON', BaseLS.JSON) == BaseLS.JSON
    ]

    assert not unnamed, f'MERGE classes with no JSON name, which would group together: {unnamed}'


def test_only_the_alias_pairs_share_a_grouping_key() -> None:
    """Two codes under one key is deliberate for the aliases and a bug for anything else."""
    shared: dict[str, list[int]] = {}
    for code, klass in sorted(LinkState.registered_lsids.items()):
        if getattr(klass, 'MERGE', False):
            shared.setdefault(klass.JSON, []).append(code)

    unexpected = {key: codes for key, codes in shared.items() if len(codes) > 1 and tuple(codes) not in ALIAS_PAIRS}
    assert not unexpected, f'MERGE classes sharing a key which are not a registered alias pair: {unexpected}'


@pytest.mark.parametrize('code', MERGE_CODES, ids=MERGE_IDS)
def test_a_single_merged_tlv_still_renders_as_a_list(code: int) -> None:
    """The property which makes the merge type safe, and which recovering data does not check.

    A consumer reading a merged member has to find a list whether one TLV arrived or three.
    A merge which only builds a list once it has two would give the same key two different
    types depending on what the peer sent.
    """
    payload = smallest_decodable(code)
    if payload is None:
        pytest.skip(f'TLV {code} decodes none of the probe widths')

    document = jsonlib.loads(render(payload))
    key = LinkState.registered_lsids[code].JSON
    assert key in document, f'TLV {code} rendered nothing under {key}'
    assert isinstance(document[key], list), f'{key} is a {type(document[key]).__name__} for a single TLV, not a list'


@pytest.mark.parametrize('first, second', ALIAS_PAIRS, ids=['local router id', 'remote router id'])
def test_the_alias_pair_lands_in_one_array_rather_than_two_keys(first: int, second: int) -> None:
    """The case 5.0's TLV-code grouping could never reach, since the aliases are siblings.

    Both codes arrive with different values, and both values have to come out.  Emitting
    the key twice is valid JSON which every parser resolves by keeping one of them, so the
    other is lost with nothing to say so.
    """
    one, other = smallest_decodable(first), smallest_decodable(second)
    if one is None or other is None:
        pytest.skip(f'{first} or {second} decodes none of the probe widths')

    # make the second value differ, so losing one is visible
    other = other[:-1] + bytes([1])

    rendered = render(one + other)
    document = jsonlib.loads(rendered)

    key = LinkState.registered_lsids[first].JSON
    assert key in document, f'{key} is missing entirely'
    assert isinstance(document[key], list), f'{key} is not a list'
    assert len(document[key]) == 2, f'{key} holds {document[key]}, so one of the two aliases was dropped'


# Every TLV has two renderers over one value: its own json(), and content, which is what
# LinkState.json() groups when the class merges.  Nothing made them agree.
#
# Twelve classes disagreed: nine FlagLS subclasses and three SRv6 ones rendered a decoded
# object from json() while content returned the raw wire bytes, and NodeOpaque rendered hex
# while content returned the bytes.  None of it showed, because json() is what the API calls
# and content is only reached through the merge, which none of those classes used.
#
# That left each of them one MERGE = True away from putting wire bytes into the API stream,
# which is exactly what happened the day PrefixSid and Srv6Locator were marked repeatable.
# Session 5.0 raised the general case after finding IsisArea disagreed the same way.

MAX_SEED_WIDTH = 40

# The opaque TLVs disagree for a reason which is not drift: content is the packed-bytes
# accessor and the tests assert it as such, while json() renders the hex of those bytes.
# Aligning them means choosing how opaque peer bytes reach the API, and the three do not
# agree today: 1025 renders hex, 1097 and 1157 go through jsonable(), which decodes bytes
# as text and loses anything which is not valid UTF-8 to a replacement character.  That is
# a change to what a consumer receives, so it is recorded here rather than made silently.
ENCODING_UNDECIDED = {1025}


def smallest_instance(code: int) -> BaseLS | None:
    """A decoded TLV at the shortest width its own decoder accepts."""
    klass = LinkState.registered_lsids[code]
    for width in range(1, MAX_SEED_WIDTH):
        try:
            instance = klass.unpack_bgpls(bytes(width))
        except Exception:
            continue
        instance.json()
        return instance
    return None


@pytest.mark.parametrize('code', MERGE_CODES, ids=MERGE_IDS)
def test_what_the_api_emits_for_a_merged_tlv_is_what_content_says(code: int) -> None:
    """The merge renders content, so content is what a merging class must hold.

    A class whose content is the wire bytes puts the wire bytes in the API the moment it
    merges.  Asserting against the attribute's rendered output rather than the TLV's own
    json() is deliberate: LinkState.json() is the path which actually reaches a consumer.
    """
    instance = smallest_instance(code)
    if instance is None:
        pytest.skip(f'TLV {code} decodes none of the seed widths')

    payload = pack('!HH', code, len(instance._packed)) + bytes(instance._packed)
    document = jsonlib.loads(render(payload))

    key = LinkState.registered_lsids[code].JSON
    assert document[key] == [jsonable(instance.content)], f'{key} does not carry what content holds'


def test_no_tlv_renders_something_its_content_does_not_hold() -> None:
    """The other side of the pair, for the classes which do not merge.

    They are the ones which can acquire the defect: their content is unused today, so
    nothing notices it drifting until somebody marks the class repeatable.  Checking it
    now is what makes marking one a one line change rather than a silent regression.
    """
    mismatched = []
    for code, klass in sorted(LinkState.registered_lsids.items()):
        if getattr(klass, 'MERGE', False) or getattr(klass, 'GENERIC', False):
            continue
        if code in ENCODING_UNDECIDED:
            continue
        instance = smallest_instance(code)
        if instance is None:
            continue
        rendered = jsonlib.loads('{' + instance.json() + '}')
        key = klass.JSON if klass.JSON in rendered else next(iter(rendered), None)
        if key is None:
            continue
        if rendered[key] != jsonable(instance.content):
            mismatched.append((code, klass.__name__))

    assert not mismatched, f'these TLVs render something their content does not hold: {mismatched}'
