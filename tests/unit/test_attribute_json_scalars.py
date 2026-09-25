"""An attribute which renders as an integer must reach the consumer as valid JSON.

`AttributeCollection._generate_json` has one branch for every attribute whose
representation is 'integer': MED, LOCAL_PREF, AIGP and OTC. MED and local preference
print as decimal and have always been JSON numbers in the stream, so consumers do
arithmetic on them. AIGP prints as 0x000000000000000a, which unquoted is not JSON and
takes the whole line with it.

`_as_json_scalar` decides which of the two a value is, and it decided with `int()`.
Python's `int()` accepts more than the JSON number grammar of RFC 8259 section 6 does:
'010', '00', '1_000' and '+5' all parse, and all four were emitted bare, which makes the
line unparseable. No attribute renders one of those shapes today, so nothing else in the
suite exercises it; it is tested directly because it is a trap for the next attribute
added to that branch.

Ported from the 5.0 branch, where the same helper is spelled `_is_json_number`.
"""

from __future__ import annotations

import json
import types

import pytest

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.community.extended import (
    ExtendedCommunity,
    ExtendedCommunityIPv6,
)
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.med import MED

# Every attribute whose representation is 'integer', so every one which reaches the
# branch under test. A new one added there is covered by the sweep at the end.
INTEGER_CODES = (
    Attribute.CODE.MED,
    Attribute.CODE.LOCAL_PREF,
    Attribute.CODE.AIGP,
    Attribute.CODE.OTC,
)


def rendered(attribute: Attribute) -> dict[str, object]:
    """The attribute as the JSON API writes it, parsed the way a consumer parses it."""
    collection = AttributeCollection()
    collection.add(attribute)
    parsed: dict[str, object] = json.loads('{' + collection.json() + '}')
    return parsed


# ================================================ the two shapes the branch has to emit


def test_med_and_local_preference_stay_json_numbers() -> None:
    """Quoting either is a break: consumers do arithmetic on them."""
    pairs = ((MED.from_int(100), 'med', 100), (LocalPreference.from_int(200), 'local-preference', 200))
    for attribute, name, expected in pairs:
        parsed = rendered(attribute)
        assert parsed[name] == expected
        assert isinstance(parsed[name], int), f'{name} must stay a JSON number'
        assert not isinstance(parsed[name], bool), f'{name} must be a number rather than a boolean'


def test_aigp_renders_as_a_quoted_string() -> None:
    """AIGP prints as 0x000000000000000a, which is not a JSON number."""
    from exabgp.bgp.message.update.attribute.aigp import AIGP

    attribute = AIGP.unpack_attribute(bytes.fromhex('01000b' + '000000000000000a'), types.SimpleNamespace(aigp=True))
    parsed = rendered(attribute)

    assert parsed['aigp'] == '0x000000000000000a'
    assert isinstance(parsed['aigp'], str), 'AIGP unquoted makes the whole line unparseable'


# ==================================================== the helper which decides which one

JSON_INTEGERS = ['100', '-5', '0', '-0', '  5  ', '5\n']

NOT_JSON_INTEGERS = [
    'NaN',  # json.loads accepts it, RFC 8259 does not
    'Infinity',
    '-Infinity',
    'true',  # bool is a subclass of int
    'null',
    '1e400',  # becomes inf
    '0x0a',  # what AIGP renders
    '010',  # int() takes it, JSON forbids a redundant leading zero
    '00',
    '+5',  # int() takes it, JSON has no leading plus
    '1_000',  # int() takes it, JSON has no digit separator
    '1.5',
    '',
    '"7"',
]


@pytest.mark.parametrize('text', JSON_INTEGERS)
def test_a_json_integer_is_emitted_bare(text: str) -> None:
    assert AttributeCollection._as_json_scalar(text) == text


@pytest.mark.parametrize('text', NOT_JSON_INTEGERS)
def test_anything_else_is_quoted(text: str) -> None:
    assert AttributeCollection._as_json_scalar(text) == json.dumps(text)


@pytest.mark.parametrize('text', JSON_INTEGERS + NOT_JSON_INTEGERS)
def test_whatever_it_emits_parses_as_json(text: str) -> None:
    """The property the two tests above exist for, asserted over both lists at once."""
    line = '{"med": %s}' % AttributeCollection._as_json_scalar(text)

    json.loads(line)


def test_the_helper_can_answer_both_ways() -> None:
    """Otherwise a helper which quoted everything would satisfy half of the above."""
    assert AttributeCollection._as_json_scalar('7') == '7'
    assert AttributeCollection._as_json_scalar('seven') == '"seven"'


def test_every_integer_attribute_is_covered_by_this_file() -> None:
    """A new attribute on the 'integer' branch has to be added to INTEGER_CODES."""
    integer = {code for code, entry in AttributeCollection.representation.items() if entry[0] == 'integer'}

    assert integer == set(INTEGER_CODES), f'the integer attributes changed: {sorted(integer)}'


# ============================================ the hex width of an extended community


@pytest.mark.parametrize('wire', ['0208359d0f6f18f2', '0000000000000001', '0102030405060708'])
def test_an_eight_byte_community_renders_its_own_bytes(wire: str) -> None:
    rendered_text = repr(ExtendedCommunity.unpack_attribute(bytes.fromhex(wire), None))

    if rendered_text.startswith('0x'):
        assert rendered_text[2:].lower() == wire


@pytest.mark.parametrize('wire', ['000b' + '00' * 18, '0102030405060708090a0b0c0d0e0f1011121314'])
def test_a_twenty_byte_community_keeps_its_leading_zeros(wire: str) -> None:
    """'0x{:016X}' was eight bytes wide, and one of the two registries is twenty."""
    rendered_text = repr(ExtendedCommunityIPv6.unpack_attribute(bytes.fromhex(wire), None))

    if rendered_text.startswith('0x'):
        assert rendered_text[2:].lower() == wire
        assert len(rendered_text) == 2 + 40
