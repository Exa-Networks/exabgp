#!/usr/bin/env python3
# encoding: utf-8

"""A FlowSpec NLRI must render as one parseable JSON object

FlowSpec is the family the advisory names as the one that matters: the API
consumers are DDoS mitigation and filter-injection controllers. A line they
cannot parse is a filter they do not install, and nothing reports it.
"""

import json

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.protocol.family import AFI, SAFI

FAMILIES = [(AFI.ipv4, SAFI.flow_ip), (AFI.ipv4, SAFI.flow_vpn), (AFI.ipv6, SAFI.flow_ip), (AFI.ipv6, SAFI.flow_vpn)]


def rendered(afi, safi, wire):
    result = Flow.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, False)
    nlri = result[0] if isinstance(result, tuple) else result
    return None if nlri is None else nlri.json()


class TestFlowJsonAlwaysParses:
    @pytest.mark.parametrize(
        'wire,what',
        [
            (bytes.fromhex('00'), 'a flow with no rule at all'),
            (bytes.fromhex('050C00008002'), 'a fragment rule which renders empty'),
            (bytes.fromhex('050900008002'), 'a tcp-flags rule which renders empty'),
            (bytes.fromhex('06038106048119'), 'an ordinary two rule flow'),
            (bytes.fromhex('040C900001'), 'a two byte fragment value'),
        ],
    )
    def test_parses(self, wire, what) -> None:
        emitted = rendered(AFI.ipv4, SAFI.flow_ip, wire)
        if emitted is None:
            pytest.skip(f'{what}: the decoder rejected it, nothing to render')
        json.loads('{"nlri": %s}' % emitted)

    def test_an_ordinary_flow_is_unchanged(self) -> None:
        # byte for byte what 5.0.12 emitted, so a consumer sees no difference
        # the length byte must agree with the rules behind it: 05 here declared
        # five bytes for six, and the truncated port used to decode as "=0", a
        # match the peer never sent
        emitted = rendered(AFI.ipv4, SAFI.flow_ip, bytes.fromhex('06038106048119'))
        assert emitted == '{ "protocol": [ "=tcp" ], "port": [ "=25" ], "string": "flow protocol =tcp port =25" }'

    def test_a_declared_zero_and_a_missing_value_differ_by_one_byte(self) -> None:
        """The malformed and the well formed form are one byte apart

        06 03 81 06 04 81 00   six declared bytes and a real 00: the peer DID
                               send a zero, and "port =0" is the truth
        05 03 81 06 04 81      five declared bytes for six, so the port value is
                               not there at all, and "port =0" would be invented

        A fixture written with the wrong one pins the bug as the expected
        output, which is how this defect survived its own regression test.
        """
        well_formed = rendered(AFI.ipv4, SAFI.flow_ip, bytes.fromhex('06038106048100'))
        assert well_formed is not None
        assert '"=0"' in well_formed

        assert rendered(AFI.ipv4, SAFI.flow_ip, bytes.fromhex('050381060481')) is None

    @pytest.mark.parametrize('afi,safi', FAMILIES)
    def test_every_flow_family(self, afi, safi) -> None:
        for wire in (bytes.fromhex('00'), bytes.fromhex('050C00008002')):
            emitted = rendered(afi, safi, wire)
            if emitted is None:
                continue
            json.loads('{"nlri": %s}' % emitted)
