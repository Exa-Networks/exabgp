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
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState


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
