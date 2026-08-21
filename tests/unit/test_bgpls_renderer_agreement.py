#!/usr/bin/env python3
# encoding: utf-8

"""Every BGP-LS TLV has two renderers, and they must say the same thing

json() and as_dict() are two views of one decoded value. Nothing made them agree
and nothing checked that they did, so a class could format the same content two
different ways and both outputs looked reasonable in isolation. IsisArea does
exactly that: content is an int, as_dict() passes it through, and json() wraps it
in quotes, so the JSON API says "area-id": "4784129" and as_dict() says 4784129.

Source inspection cannot find this. A reviewer looking for a renderer which
re-derives the value from _packed instead of reading content finds nothing here,
because both of IsisArea's renderers read content correctly and merely format it
differently. Only running them and comparing the results shows it.

That is the general lesson: for a pair of hooks over one value, the test has to
be behavioural. Reading the code tells you they both use content; it does not
tell you they agree.

The known disagreement is listed rather than fixed. Changing either side is a
compatibility break on a stable branch, so it is recorded and any NEW one fails.
"""

import json

from struct import pack

from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

# Widths to try per TLV, smallest first: a TLV is exercised at the first width it
# accepts. Without this the sweep reaches almost nothing, because a fixed width
# guess is the wrong shape for most of them.
WIDTHS = (1, 2, 3, 4, 6, 8, 12, 16, 20, 24)

# The floor is a ratchet. A sweep which decodes nothing finds no disagreements
# and reports success, which is indistinguishable from a sweep which works.
# Raise this when more TLVs become reachable; never lower it to go green.
COVERAGE_FLOOR = 24

# Known, deliberately unfixed. Fixing either side changes the type a consumer
# receives: json() would start emitting a number, or as_dict() a string.
#   1027  area-id  json '4784129' (str)  as_dict 4784129 (int)
KNOWN_DISAGREEMENT = {1027}


def negotiated():
    stub = Mock()
    stub.families = []
    stub.asn4 = True
    return stub


def decoded_tlvs():
    """Every registered TLV, decoded at the first width it accepts"""
    for code, _klass in sorted(LinkState.registered_lsids.items(), key=lambda kv: int(kv[0])):
        code = int(code)
        for width in WIDTHS:
            wire = pack('!HH', code, width) + bytes([0x49]) * width
            try:
                attribute = LinkState.unpack(wire, Direction.IN, negotiated())
            except Exception:
                continue
            yield code, attribute
            break


def disagreements(attribute):
    """Keys where the two renderers differ in value or in type"""
    try:
        rendered = json.loads(attribute.json())
        as_dict = attribute.as_dict()
    except Exception as exc:  # noqa: BLE001 - a renderer raising is its own failure
        return [f'a renderer raised {type(exc).__name__}: {exc}']
    differing = []
    for key in set(rendered) | set(as_dict):
        left, right = rendered.get(key), as_dict.get(key)
        if type(left) is not type(right) or left != right:
            differing.append(f'{key}: json={left!r} as_dict={right!r}')
    return differing


class TestTheTwoRenderersAgree:
    def test_no_new_disagreement(self) -> None:
        found = []
        for code, attribute in decoded_tlvs():
            if code in KNOWN_DISAGREEMENT:
                continue
            for detail in disagreements(attribute):
                found.append(f'TLV {code}: {detail}')
        assert not found, found

    def test_the_sweep_reaches_enough_to_mean_something(self) -> None:
        reached = [code for code, _ in decoded_tlvs()]
        assert len(reached) >= COVERAGE_FLOOR, f'only reached {len(reached)}: {reached}'

    def test_neither_renderer_raises(self) -> None:
        # a renderer which raises never reaches the comparison above, so it would
        # otherwise be counted as agreement
        for code, attribute in decoded_tlvs():
            attribute.json()
            attribute.as_dict()


class TestTheKnownDisagreementIsStillExactlyThat:
    """Listed, not forgotten

    If it is ever fixed this fails, which is the prompt to take it off the list
    rather than leave an exemption covering a class which no longer needs one.
    """

    @staticmethod
    def isis_area():
        return LinkState.registered_lsids[1027].unpack(bytes([0x49, 0x00, 0x01]))

    def test_json_says_string_and_as_dict_says_number(self) -> None:
        area = self.isis_area()
        assert json.loads('{%s}' % area.json())['area-id'] == '4784129'
        assert area.as_dict()['area-id'] == 4784129

    def test_and_it_is_the_only_one_exempted(self) -> None:
        # an exemption list which grows silently is how this category comes back
        assert KNOWN_DISAGREEMENT == {1027}


class TestTheSweepCanActuallyFail:
    """A green sweep is evidence only after it has been made to go red

    Running the sweep and getting one result is consistent with the sweep working
    and equally consistent with it half working. Seeding a disagreement of the
    shape it is meant to catch, a format-only difference over identical content,
    is what tells them apart.
    """

    def test_a_format_only_difference_is_caught(self) -> None:
        class Divergent:
            def json(self):
                return '{"probe": "7"}'

            def as_dict(self):
                return {'probe': 7}

        found = disagreements(Divergent())
        assert found, 'the comparison cannot see a str/int difference over one value'
        assert 'probe' in found[0]

    def test_an_agreeing_pair_is_not_flagged(self) -> None:
        class Agreeing:
            def json(self):
                return '{"probe": 7}'

            def as_dict(self):
                return {'probe': 7}

        assert not disagreements(Agreeing())

    def test_a_raising_renderer_is_reported_not_ignored(self) -> None:
        class Raising:
            def json(self):
                raise ValueError('boom')

            def as_dict(self):
                return {}

        found = disagreements(Raising())
        assert found and 'ValueError' in found[0]


@pytest.mark.parametrize('code', sorted({1025, 1026, 1027, 1097, 1098, 1157}))
def test_the_named_and_opaque_tlvs_are_reached(code) -> None:
    """The sweep must include the classes this series actually changed

    A coverage floor is a number; these are the specific TLVs whose renderers
    were touched, and a sweep which silently stopped reaching them would still
    clear the floor.
    """
    assert code in {c for c, _ in decoded_tlvs()}
