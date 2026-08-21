"""A peer repeating a BGP-LS TLV chose which of its own values the API consumer saw.

LinkState.json() renders each TLV under a fixed key.  A TLV sent twice therefore emitted
that key twice, and every JSON parser resolves a duplicate key by keeping one of them, so
the other was lost with nothing anywhere to say so.  Measured before the fix: 33 of the 38
non-MERGE TLVs collided this way.

That is the advisory's shape once more.  Not injection this time, but the peer deciding
what reaches the process which consumes its routes.

Two rules, and which one applies is the RFC's answer to "may this TLV repeat":

  it may       render it as a list under a plural key, and keep every value.  MERGE is
               this implementation's marker for that, so it is the marker used.
  it may not   RFC 9552 5.3.2: the attribute is malformed and the attribute discard
               approach is used.  LinkState already sets DISCARD, so the route survives
               without its BGP-LS attribute rather than the session being reset.

The three which the RFCs allow to repeat and which were not marked:

  1027 IS-IS Area Identifier   RFC 9552 5.3.1.2, a node may be in several areas
  1158 Prefix-SID              RFC 9085 2.3.1, one per algorithm
  1162 SRv6 Locator            RFC 9514 7.1, one per algorithm

A code nothing has registered is held to neither rule: we cannot claim a TLV we have not
implemented may not repeat, so it merges, which keeps both values without refusing anything.
"""

from __future__ import annotations

import importlib
import json as jsonlib
import pkgutil
from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState


def _populate() -> None:
    import exabgp.bgp.message.update.attribute as package

    for _finder, name, _is_package in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            importlib.import_module(name)
        except ImportError:
            continue


_populate()

MAX_TLV_WIDTH = 40
# a ratchet: raise it as TLVs are added, never lower it to make a red run green
MIN_REGISTERED_TLVS = 45
UNKNOWN_CODES = (9999, 60000)

# name, code, a width it decodes at
REPEATABLE = [
    ('isis area', 1027, 4),
    ('prefix sid', 1158, 8),
    ('srv6 locator', 1162, 22),
]


def attribute() -> type[Attribute]:
    klass = Attribute.klass_by_id(Attribute.CODE.BGP_LS)
    assert klass is not None
    return klass


def tlv(code: int, payload: bytes) -> bytes:
    return pack('!HH', code, len(payload)) + payload


def render(data: bytes) -> dict:
    return jsonlib.loads(attribute().unpack_attribute(data, Negotiated.UNSET).json())


def duplicate_keys(rendered: str) -> set[str]:
    """Names which appear twice inside ONE object, which is what loses a value.

    A regex over the whole document is the wrong tool and says so loudly: two objects in
    one array legitimately carry the same member names, and counting those reports every
    merged TLV as broken.  object_pairs_hook sees each object separately, which is the
    level at which a parser actually drops one of a pair.
    """
    found: set[str] = set()

    def check(pairs: list[tuple[str, object]]) -> dict:
        seen: set[str] = set()
        for key, _value in pairs:
            if key in seen:
                found.add(key)
            seen.add(key)
        return dict(pairs)

    jsonlib.loads(rendered, object_pairs_hook=check)
    return found


def widths(code: int) -> int | None:
    for width in range(1, MAX_TLV_WIDTH):
        try:
            attribute().unpack_attribute(tlv(code, bytes(width)), Negotiated.UNSET).json()
        except Exception:
            continue
        return width
    return None


@pytest.mark.parametrize('name, code, width', REPEATABLE, ids=[row[0] for row in REPEATABLE])
def test_a_tlv_which_may_repeat_keeps_every_value(name: str, code: int, width: int) -> None:
    """Both values, under one key, in the order the peer sent them."""
    document = render(tlv(code, bytes(width)) + tlv(code, bytes(width - 1) + bytes([1])))

    key = LinkState.registered_lsids[code].JSON
    assert key in document, f'{name} rendered nothing under {key}'
    assert len(document[key]) == 2, f'{name} kept {document[key]}, so one of the two was dropped'


@pytest.mark.parametrize('name, code, width', REPEATABLE, ids=[row[0] for row in REPEATABLE])
def test_a_tlv_which_may_repeat_is_a_list_even_when_it_does_not(name: str, code: int, width: int) -> None:
    """A consumer must find the same type whether the peer sent one or three."""
    document = render(tlv(code, bytes(width)))

    key = LinkState.registered_lsids[code].JSON
    assert isinstance(document[key], list), f'{key} is a {type(document[key]).__name__} for a single TLV'
    assert key.endswith('s'), f'{key} holds a list and does not read as a plural'


def test_a_tlv_which_may_not_repeat_makes_the_attribute_malformed() -> None:
    """RFC 9552 5.3.2, and DISCARD means the route survives without the attribute."""
    for code in (1026, 1088, 1092, 1098):
        width = widths(code)
        assert width is not None, f'TLV {code} decodes none of the probe widths'

        with pytest.raises(Notify):
            render(tlv(code, bytes(width)) + tlv(code, bytes(width)))


def test_a_tlv_which_may_not_repeat_is_still_accepted_once() -> None:
    """The refusal must not have closed the path it guards."""
    for code in (1026, 1088, 1092, 1098):
        width = widths(code)
        assert width is not None
        assert render(tlv(code, bytes(width))), f'TLV {code} renders nothing on its own'


@pytest.mark.parametrize('code', UNKNOWN_CODES, ids=[str(c) for c in UNKNOWN_CODES])
def test_an_unimplemented_tlv_is_neither_refused_nor_collapsed(code: int) -> None:
    """We cannot claim a TLV we do not implement may not repeat, so it merges."""
    document = render(tlv(code, bytes(4)) + tlv(code, bytes(3) + bytes([1])))

    key = f'generic-lsid-{code}'
    assert key in document, f'an unknown code rendered under {list(document)} rather than {key}'
    assert len(document[key]) == 2, 'one of two values for an unknown code was dropped'


def test_two_different_unimplemented_tlvs_do_not_share_a_key() -> None:
    """The collapse session 5.0 warned about, reached through the generic path.

    get_ls_class builds a class per unknown code, and the merge groups by JSON name, so a
    synthesised class left on the inherited default would put every unknown code the peer
    sent into one member.  The names come from the code, so they cannot.
    """
    first, second = UNKNOWN_CODES
    document = render(tlv(first, bytes(4)) + tlv(second, bytes(2)))

    assert f'generic-lsid-{first}' in document
    assert f'generic-lsid-{second}' in document


def test_no_tlv_can_make_the_api_emit_the_same_key_twice() -> None:
    """The sweep this whole file came from, over every registered code.

    A duplicate key is valid JSON which every parser resolves by keeping one value, so
    this cannot be left to the reader to notice: either the TLV merges, or it is refused.
    """
    duplicated = []
    for code in sorted(LinkState.registered_lsids):
        width = widths(code)
        if width is None:
            continue
        payload = tlv(code, bytes(width)) + tlv(code, bytes(width - 1) + bytes([1]))
        try:
            rendered = attribute().unpack_attribute(payload, Negotiated.UNSET).json()
        except Notify:
            continue
        repeated = duplicate_keys(rendered)
        if repeated:
            duplicated.append((code, sorted(repeated)))

    assert not duplicated, f'these TLVs emit a duplicate JSON key when sent twice: {duplicated}'


def test_the_registry_sweep_had_a_registry_to_sweep() -> None:
    """test_no_tlv_can_make_the_api_emit_the_same_key_twice walks registered_lsids.

    It reports the TLVs which duplicate a key, so a registry holding three entries reports
    nothing and passes.  The rest of this file fails on a thinned registry only because its
    seeds stop decoding, which is luck rather than a check: make the seeds tolerant and the
    file goes green while covering almost nothing.

    Session 5.0's harder experiment is what found this.  An emptied registry makes almost
    any floor fire; a registry thinned to three entries only makes a well chosen one fire,
    and a half filled registry is the failure which actually happens, from import order.
    """
    assert len(LinkState.registered_lsids) >= MIN_REGISTERED_TLVS, (
        f'only {len(LinkState.registered_lsids)} BGP-LS TLVs are registered, so the duplicate key sweep proves little'
    )
