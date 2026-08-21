#!/usr/bin/env python3
# encoding: utf-8

"""Every attribute the API renders must produce one parseable JSON line

The advisory was about injection. These are the other way a consumer breaks:
a line it cannot parse at all, which it never reports because it never arrives.
"""

import json
import types

import pytest

from exabgp.bgp.message.update.attribute.attributes import Attributes


class TestIntegerAttributesAreQuoted:
    """The branch every integer attribute lands in was marked 'Should never be ran'"""

    def test_aigp_renders_parseable_json(self) -> None:
        from exabgp.bgp.message.update.attribute.aigp import AIGP

        # AIGP str() is 0x000000000000000a, which unquoted is not JSON and takes
        # the whole line with it
        attribute = AIGP.unpack(bytes.fromhex('01000b' + '000000000000000a'), None, types.SimpleNamespace(aigp=True))
        attributes = Attributes()
        attributes.add(attribute)
        parsed = json.loads('{' + attributes.json() + '}')
        assert parsed['aigp'] == '0x000000000000000a'

    def test_med_and_local_preference_stay_json_numbers(self) -> None:
        from exabgp.bgp.message.update.attribute.med import MED
        from exabgp.bgp.message.update.attribute.localpref import LocalPreference

        # they render as decimal and have always been NUMBERS in the stream.
        # Quoting them is a break: consumers do arithmetic on these.
        for attribute, name, expected in ((MED(100), 'med', 100), (LocalPreference(200), 'local-preference', 200)):
            attributes = Attributes()
            attributes.add(attribute)
            parsed = json.loads('{' + attributes.json() + '}')
            assert parsed[name] == expected
            assert isinstance(parsed[name], int), f'{name} must stay a JSON number'


class TestExtendedCommunityHexWidth:
    """'0x{:016X}' is eight bytes wide, and one of the two registries is twenty"""

    @pytest.mark.parametrize(
        'wire',
        [
            '0208359d0f6f18f2',
            '0000000000000001',
            '0102030405060708',
        ],
    )
    def test_v4_hex_reproduces_the_wire(self, wire) -> None:
        from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

        rendered = repr(ExtendedCommunity.unpack(bytes.fromhex(wire)))
        if rendered.startswith('0x'):
            assert rendered[2:].lower() == wire

    @pytest.mark.parametrize(
        'wire',
        [
            '000b' + '00' * 18,
            '0102030405060708090a0b0c0d0e0f1011121314',
        ],
    )
    def test_v6_hex_keeps_its_leading_zeros(self, wire) -> None:
        from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunityIPv6

        rendered = repr(ExtendedCommunityIPv6.unpack(bytes.fromhex(wire)))
        if rendered.startswith('0x'):
            # a twenty byte community used to lose its leading zeros to a
            # sixteen digit format
            assert rendered[2:].lower() == wire
            assert len(rendered) == 2 + 40
