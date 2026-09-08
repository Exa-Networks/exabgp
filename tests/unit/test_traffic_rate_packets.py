#!/usr/bin/env python3
# encoding: utf-8
"""The RFC 8955 traffic-rate-packets action, backported from main.

Requested on https://github.com/Exa-Networks/exabgp/issues/1426. The NaN fix on this branch
covered `traffic-rate` and not `traffic-rate-packets`, because the latter does not exist
here at all: it was added on main as 8bfc39460 and never came back. Adding it later without
the finiteness check would reintroduce the reported defect in a new community, so the two
arrive together.

Wire format is the same eight bytes as traffic-rate with subtype 0x0C rather than 0x06, so
what is worth pinning is what differs: the subtype, the clamp on a negative rate, and the
configuration keyword.
"""

from __future__ import annotations

import os
from struct import pack

import pytest

os.environ['exabgp_log_enable'] = 'false'

from exabgp.bgp.message.notification import Notify  # noqa: E402
from exabgp.bgp.message.open.asn import ASN  # noqa: E402
from exabgp.bgp.message.update.attribute.community.extended import TrafficRatePackets  # noqa: E402
from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities  # noqa: E402
from exabgp.bgp.message.direction import Direction  # noqa: E402

TRAFFIC_RATE_TYPE = 0x80
PACKETS_SUBTYPE = 0x0C
BYTES_SUBTYPE = 0x06

NOT_A_NUMBER = 0x7F800001
POSITIVE_INFINITY = 0x7F800000
NEGATIVE_INFINITY = 0xFF800000

NON_FINITE_RATES = [NOT_A_NUMBER, POSITIVE_INFINITY, NEGATIVE_INFINITY]
NON_FINITE_IDS = ['nan', '+inf', '-inf']


def community(rate_bits, subtype=PACKETS_SUBTYPE):
    return pack('!BBH', TRAFFIC_RATE_TYPE, subtype, 0) + pack('!L', rate_bits)


def test_it_is_registered_under_its_own_subtype() -> None:
    """0x0C, not 0x06: sharing the subtype would make one shadow the other."""
    decoded = ExtendedCommunities.unpack(community(0x447A0000), Direction.IN, None).communities[0]

    assert isinstance(decoded, TrafficRatePackets)
    assert decoded.rate == 1000.0
    assert repr(decoded) == 'rate-limit:1000:packets'


def test_the_bytes_subtype_still_decodes_as_bytes() -> None:
    """The control: a new registration which stole 0x06 would pass the test above."""
    decoded = ExtendedCommunities.unpack(community(0x447A0000, BYTES_SUBTYPE), Direction.IN, None).communities[0]

    assert not isinstance(decoded, TrafficRatePackets)
    assert repr(decoded) == 'rate-limit:1000'


def test_a_negative_packet_rate_reads_as_discard() -> None:
    """RFC 8955: a rate below zero is not a rate, and zero is the drop-everything value."""
    decoded = TrafficRatePackets.unpack(community(0xBFC00000))  # -1.5

    assert decoded.rate == 0
    assert repr(decoded) == 'rate-limit:0:packets'


@pytest.mark.parametrize('rate_bits', NON_FINITE_RATES, ids=NON_FINITE_IDS)
def test_a_non_finite_packet_rate_is_refused_by_the_decoder(rate_bits) -> None:
    """The #1426 defect, in the community which did not exist when it was fixed.

    `rate` clamps a negative to zero with max(value, 0.0), and a NaN sails through that
    because every comparison against a NaN is false. So the clamp is not the check.
    """
    with pytest.raises(Notify) as raised:
        TrafficRatePackets.unpack(community(rate_bits))

    assert raised.value.code == 3
    assert raised.value.subcode == 9


@pytest.mark.parametrize('rate', [float('nan'), float('inf'), float('-inf')], ids=NON_FINITE_IDS)
def test_a_non_finite_packet_rate_cannot_be_built_either(rate) -> None:
    with pytest.raises(ValueError, match='finite'):
        TrafficRatePackets(ASN(0), rate)


def test_a_negative_packet_rate_cannot_be_built() -> None:
    """main refuses this at construction, so this branch does too."""
    with pytest.raises(ValueError, match='must not be negative'):
        TrafficRatePackets(ASN(0), -1)


def test_it_packs_back_into_what_it_decoded() -> None:
    wire = community(0x447A0000)

    assert bytes(TrafficRatePackets.unpack(wire).pack()) == wire


def test_the_configuration_keyword_matches_main() -> None:
    """`rate-limit <n> packets`, the spelling main settled on.

    main added this as `rate-limit-packets <n>` and later replaced it with a unit on
    `rate-limit`. Backporting the older spelling would make a working 5.0 configuration
    fail on main, which is the wrong way round for a maintenance branch.
    """
    from exabgp.configuration.flow.parser import rate_limit

    class FakeTokeniser:
        def __init__(self, tokens):
            self._tokens = list(tokens)

        def __call__(self):
            return self._tokens.pop(0)

        def peek(self):
            return self._tokens[0] if self._tokens else ''

    communities = rate_limit(FakeTokeniser(['1000', 'packets']))
    assert repr(communities.communities[0]) == 'rate-limit:1000:packets'

    communities = rate_limit(FakeTokeniser(['9600', 'bytes']))
    assert repr(communities.communities[0]) == 'rate-limit:9600'

    # no unit is bytes, which is what every existing configuration says
    communities = rate_limit(FakeTokeniser(['9600']))
    assert repr(communities.communities[0]) == 'rate-limit:9600'
