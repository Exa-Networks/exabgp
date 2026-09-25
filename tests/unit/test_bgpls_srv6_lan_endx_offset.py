"""The SRv6 LAN End.X SID starts after the neighbour's identifier, whose width is protocol specific.

RFC 9514 4.2 lays the TLV out as Endpoint Behavior (2), Flags (1), Algorithm (1), Weight (1),
Reserved (1), then the neighbour's identifier and a 16 octet SRv6 SID. IS-IS names the
neighbour with a 6 octet System-ID and OSPFv3 with a 4 octet Router-ID, so the SID begins at
12 and at 10 respectively.

The OSPF branch read from 6, which is where the Router-ID begins, not the SID. Two things
followed. The Router-ID's four octets were reported as the head of the SID, and the SID's last
four fell past the end of the fixed part, where the sub-TLV walk read them as a sub-TLV header
and invented a member from them. `FIXED_SIZE_OSPF` was 22, which is 6 + 16: it agreed with the
wrong offset rather than with the RFC, so the two faults hid each other and no length check
could catch either. A body one octet short of the SID was accepted and the SID then read past
the end of the buffer, which is the length-before-read rule and not only a wrong offset.

main carried the same pair; this is the 5.0 half.

The assertions come in at two levels on purpose. `unpack_data` is where the offsets live, and
`json()` is what an API consumer receives: a fix which corrected the offsets but left the
renderer reading the old slice would satisfy only one of them.
"""

import json
from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.link.srv6lanendx import (
    FIXED_SIZE_ISIS,
    FIXED_SIZE_OSPF,
    ISIS,
    OSPF,
    Srv6LanEndXISIS,
    Srv6LanEndXOSPF,
    unpack_data,
)
from exabgp.protocol.ip import IPv6

BEHAVIOR = 57
FLAGS = 0x80
ALGORITHM = 0
WEIGHT = 0
RESERVED = 0

# RFC 9514 4.2: behavior 2, flags 1, algorithm 1, weight 1, reserved 1
LEADER_SIZE = 6
SID_SIZE = 16

OSPF_ROUTER_ID = bytes([192, 0, 2, 1])
ISIS_SYSTEM_ID = bytes([0x19, 0x00, 0x95, 0x00, 0x20, 0x02])
SID = bytes.fromhex('fc000000000000000000000000000003')

# what the fixed part of the members is, before any sub-TLV
MEMBERS = ('flags', 'neighbor-id', 'behavior', 'algorithm', 'weight', 'sid')


def head():
    return pack('!HBBBB', BEHAVIOR, FLAGS, ALGORITHM, WEIGHT, RESERVED)


def ospf_body(sid=SID):
    return head() + OSPF_ROUTER_ID + sid


def isis_body(sid=SID):
    return head() + ISIS_SYSTEM_ID + sid


def rendered(klass, body):
    """The member as an API consumer receives it, rather than the decoder's own dict."""
    return json.loads('{' + klass.unpack(body).json() + '}')


def test_the_fixed_sizes_are_the_ones_rfc9514_lays_out():
    """6 octets of leader, then the identifier, then 16 of SID."""
    assert FIXED_SIZE_ISIS == LEADER_SIZE + len(ISIS_SYSTEM_ID) + SID_SIZE
    assert FIXED_SIZE_OSPF == LEADER_SIZE + len(OSPF_ROUTER_ID) + SID_SIZE
    assert len(ospf_body()) == FIXED_SIZE_OSPF, 'the builder here disagrees with the constant'
    assert len(isis_body()) == FIXED_SIZE_ISIS


def test_the_ospf_sid_is_the_sid_and_not_the_router_id():
    """'c000:201:fc00::' is the Router-ID prepended to a SID missing its tail."""
    decoded = unpack_data(Srv6LanEndXOSPF, ospf_body(), OSPF)

    assert decoded['sid'] == 'fc00::3'
    assert decoded['neighbor-id'] == '192.0.2.1'


def test_the_ospf_sid_tail_is_not_walked_as_a_sub_tlv():
    """With the offset four octets short, the SID's last four became a sub-TLV header."""
    decoded = unpack_data(Srv6LanEndXOSPF, ospf_body(), OSPF)

    assert set(decoded) == set(MEMBERS), f'invented members: {set(decoded) - set(MEMBERS)}'


def test_the_ospf_member_an_api_consumer_receives_carries_the_sid():
    """The renderer reads the same slice, so it has to be asked separately."""
    members = rendered(Srv6LanEndXOSPF, ospf_body())['srv6-lan-endx-ospf']

    assert len(members) == 1
    assert members[0]['sid'] == 'fc00::3'
    assert members[0]['neighbor-id'] == '192.0.2.1'
    assert set(members[0]) == set(MEMBERS), f'invented members: {set(members[0]) - set(MEMBERS)}'


def test_the_isis_sid_is_unchanged():
    """The IS-IS branch was right, and must stay right: the two share one function."""
    decoded = unpack_data(Srv6LanEndXISIS, isis_body(), ISIS)

    assert decoded['sid'] == 'fc00::3'
    assert set(decoded) == set(MEMBERS)

    members = rendered(Srv6LanEndXISIS, isis_body())['srv6-lan-endx-isis']
    assert members[0]['sid'] == 'fc00::3'


@pytest.mark.parametrize('protocol', [OSPF, ISIS], ids=['ospf', 'isis'])
def test_a_body_one_octet_short_of_the_sid_is_refused(protocol):
    """A truncated SID must be a Notify, not a SID read from beyond the buffer.

    This is the half a corrected offset alone does not fix: at 22, a 25 octet OSPF body passed
    the length check and the SID slice then ran off the end of the buffer.
    """
    body = ospf_body() if protocol == OSPF else isis_body()
    klass = Srv6LanEndXOSPF if protocol == OSPF else Srv6LanEndXISIS

    with pytest.raises(Notify):
        unpack_data(klass, body[:-1], protocol)


@pytest.mark.parametrize('length', [0, 6, 10, 22, 25])
def test_an_ospf_body_below_the_rfc_minimum_is_refused(length):
    """22 was the old constant, so a body of 22 to 25 octets used to be accepted."""
    with pytest.raises(Notify):
        unpack_data(Srv6LanEndXOSPF, ospf_body()[:length], OSPF)


@pytest.mark.parametrize('length', [0, 6, 12, 22, 27])
def test_an_isis_body_below_the_rfc_minimum_is_refused(length):
    with pytest.raises(Notify):
        unpack_data(Srv6LanEndXISIS, isis_body()[:length], ISIS)


def test_every_octet_of_the_sid_is_read():
    """A SID whose every byte differs cannot round-trip if the offset is wrong."""
    distinct = bytes(range(0x10, 0x20))

    decoded = unpack_data(Srv6LanEndXOSPF, ospf_body(distinct), OSPF)

    assert decoded['sid'] == IPv6.ntop(distinct)
