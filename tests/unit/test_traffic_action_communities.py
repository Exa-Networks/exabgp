"""The traffic-action extended communities, RFC 8955 sections 7.1 and 7.5.

Both faults are the same shape: a field the RFC narrows was reported whole, so the API
described an action the peer could not have asked for.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended.traffic import TrafficMark, TrafficRate


def rate_community(rate):
    """A traffic-rate extended community as it arrives on the wire."""
    return pack('!BBHf', 0x80, 0x06, 1, rate)


def mark_community(octet):
    """A traffic-marking extended community as it arrives on the wire."""
    return pack('!BBLBB', 0x80, 0x09, 0, 0, octet)


# ==================================================== section 7.1, traffic-rate


def test_a_negative_rate_on_the_wire_is_read_as_discard_all():
    """RFC 8955 section 7.1: "On decoding, negative values MUST be treated as zero
    (discard all traffic)."

    Passed on as it arrived, a peer asking for a flow to be discarded was reported as
    `rate-limit:-100`, which is not a rate any consumer of the API can program.
    """
    community = TrafficRate.unpack(rate_community(-100.0))

    assert community.rate == 0.0
    assert repr(community) == 'rate-limit:0'


def test_a_negative_rate_can_not_be_built():
    """RFC 8955 section 7.1: "On encoding, the traffic-rate MUST NOT be negative."

    Its sibling TrafficRatePackets has refused one since it was written; this one did not,
    so `rate-limit -100` in a configuration went out on the wire as a negative float.
    """
    with pytest.raises(ValueError):
        TrafficRate(ASN(0), -100.0)


def test_a_zero_rate_is_still_how_a_discard_is_written():
    """The `discard` action is TrafficRate(0), and the guard must not catch it."""
    assert repr(TrafficRate(ASN(0), 0)) == 'rate-limit:0'


def test_a_rate_which_is_not_negative_is_untouched():
    """The only two rates the captures under qa/ carry."""
    assert repr(TrafficRate.unpack(rate_community(9600.0))) == 'rate-limit:9600'
    assert repr(TrafficRate.unpack(rate_community(0.0))) == 'rate-limit:0'


# ==================================================== section 7.5, traffic-marking


@pytest.mark.parametrize(('octet', 'dscp'), [(0xC1, 1), (0x80, 0), (0x3F, 0x3F), (0x0A, 10), (0x4A, 10)])
def test_a_dscp_carries_only_its_six_low_bits(octet, dscp):
    """RFC 8955 section 7.5: the DSCP is six bits and the two high bits are reserved.

    Returned whole, 0xC1 was reported as `mark 193`, which is not a DSCP: the rest of that
    octet is ECN, a different field of the same header.
    """
    community = TrafficMark.unpack(mark_community(octet))

    assert community.dscp == dscp
    assert repr(community) == 'mark %d' % dscp


def test_the_wire_of_a_marking_community_is_kept_as_it_arrived():
    """Only what exabgp reports changes: the eight octets are passed through."""
    wire = mark_community(0xC1)

    assert bytes(TrafficMark.unpack(wire).pack()) == wire


def test_the_marking_of_conf_flow_msg_is_unchanged():
    """qa/encoding/conf-flow.msg announces `mark 10`, which has no reserved bit set."""
    assert bytes(TrafficMark(10).pack()) == mark_community(10)
