"""RFC 9085, BGP-LS Extensions for Segment Routing: the SID of an Adjacency and a Prefix SID.

The ledger these tests are joined to is qa/rfc/rfc9085.toml.

Sections 2.2.1 and 2.2.2 give the Flags and the SID of an Adjacency SID the layout of the
IGP which advertised it, IS-IS, OSPFv2 or OSPFv3, and name the Protocol-ID of the Link
NLRI as what tells them apart.  The BGP-LS Attribute is decoded on its own, before and
apart from the NLRI it describes, and is shared by every NLRI of the UPDATE, so its
decoder cannot see that Protocol-ID.  It reads the flags with the IS-IS layout.

What it can see is the length.  Section 2.2.1 gives one SID per TLV, "Either 7 or 8
octets depending on the label or index encoding of the SID", so a SID of three octets is
a label and one of four an index, whatever the flags say in the wrong layout.  An OSPF
label used to be lost: its V and L flags (0x60 in RFC 8665) read as IS-IS B and V, which
is neither a label nor an index, and the SID went to "undecoded-sids".

Some tests carry no `rfc()` marker: the rules they pin, the length of a SID and the twenty
bits of a label (2.1.1), are stated without an RFC 2119 keyword.
"""

from __future__ import annotations

import json
from struct import pack

import pytest

from exabgp.bgp.message.update.attribute.bgpls.link.adjacencysid import AdjacencySid
from exabgp.bgp.message.update.attribute.bgpls.link.lanadjacencysid import LanAdjacencySid
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixsid import PrefixSid

LABEL = 16001
LABEL_WITH_HIGH_NIBBLE = bytes([0xF0, 0x3E, 0x81])  # 16001 with the four leftmost bits set
INDEX = 100

# RFC 8665 6.1, the OSPFv2 Adj-SID flags: B, V, L, G, P from the top bit
OSPF_V = 0x40
OSPF_L = 0x20
OSPF_G = 0x10
# RFC 8667 2.2.1, the IS-IS Adj-SID flags: F, B, V, L, S, P from the top bit
ISIS_V = 0x20
ISIS_L = 0x10

OSPF_NEIGHBOR = bytes([192, 0, 2, 1])
ISIS_SYSTEM_ID = bytes([1, 2, 3, 4, 5, 6])


def adjacency(flags: int, sid: bytes) -> AdjacencySid:
    return AdjacencySid.unpack_bgpls(pack('!BBH', flags, 10, 0) + sid)


def lan_adjacency(flags: int, neighbor: bytes, sid: bytes) -> dict[str, object]:
    decoded = LanAdjacencySid.unpack_bgpls(pack('!BBH', flags, 10, 0) + neighbor + sid)
    (parsed,) = json.loads('{' + decoded.json() + '}')['sr-adj-lan-sids']
    return parsed


# ---------------------------------------------------------- the SID is never lost


@pytest.mark.parametrize('flags', [OSPF_V | OSPF_L, OSPF_V | OSPF_L | OSPF_G], ids=['label', 'label-group'])
def test_an_ospf_adjacency_label_is_decoded(flags: int) -> None:
    decoded = adjacency(flags, pack('!I', LABEL)[1:])

    assert decoded.sids == [LABEL]
    assert decoded.undecoded == ()


@pytest.mark.parametrize('flags', [0, OSPF_G], ids=['index', 'index-group'])
def test_an_ospf_adjacency_index_is_decoded(flags: int) -> None:
    decoded = adjacency(flags, pack('!I', INDEX))

    assert decoded.sids == [INDEX]
    assert decoded.undecoded == ()


def test_an_isis_adjacency_label_and_index_are_decoded_as_before() -> None:
    assert adjacency(ISIS_V | ISIS_L, pack('!I', LABEL)[1:]).sids == [LABEL]
    assert adjacency(0, pack('!I', INDEX)).sids == [INDEX]


def test_an_ospf_lan_adjacency_reads_a_four_octet_neighbor_and_its_label() -> None:
    """For OSPF the Neighbor ID is a four octet Router-ID, so the TLV is 11 or 12 octets.

    It was read as a six octet IS-IS System ID, which took two octets of the label with it.
    """
    parsed = lan_adjacency(OSPF_V | OSPF_L, OSPF_NEIGHBOR, pack('!I', LABEL)[1:])

    assert parsed['neighbor-id'] == '192.0.2.1'
    assert parsed['sid'] == LABEL
    assert parsed['undecoded'] == []


def test_an_isis_lan_adjacency_keeps_its_system_id_and_index() -> None:
    parsed = lan_adjacency(0, ISIS_SYSTEM_ID, pack('!I', INDEX))

    assert parsed['system-id'] == '010203040506'
    assert parsed['sid'] == INDEX


# ---------------------------------------------------------- a label is the twenty rightmost bits


def test_the_four_leftmost_bits_of_an_adjacency_label_are_not_part_of_it() -> None:
    """2.1.1: "the 20 rightmost bits represent a label".  f03e81 was reported as 15744641."""
    assert adjacency(ISIS_V | ISIS_L, LABEL_WITH_HIGH_NIBBLE).sids == [LABEL]
    assert lan_adjacency(ISIS_V | ISIS_L, ISIS_SYSTEM_ID, LABEL_WITH_HIGH_NIBBLE)['sid'] == LABEL


def test_the_four_leftmost_bits_of_a_prefix_label_are_not_part_of_it() -> None:
    # RFC 8667 2.1.1: V is 0x08 and L 0x04 in the Prefix-SID flags
    decoded = PrefixSid.unpack_bgpls(pack('!BBH', 0x0C, 0, 0) + LABEL_WITH_HIGH_NIBBLE)
    assert decoded.sids == [LABEL]


def test_an_adjacency_label_we_build_is_the_twenty_rightmost_bits() -> None:
    """The encoder shifted the label four bits left, so it read back sixteen times larger."""
    flags = {'F': 0, 'B': 0, 'V': 1, 'L': 1, 'S': 0, 'P': 0}
    built = AdjacencySid.make_adjacencysid(flags=flags, weight=10, sids=[LABEL])
    assert built.sids == [LABEL]

    lan = LanAdjacencySid.make_adjacencysidlan(flags=flags, weight=10, system_id='010203040506', sid=LABEL)
    assert LanAdjacencySid.unpack_bgpls(lan._packed).sr_adj_lan_sids[0]['sid'] == LABEL


# ---------------------------------------------------------- the flags of the IGP which sent them


@pytest.mark.rfc('rfc9085#2.2.1-adjacency-sid-flags-per-protocol')
@pytest.mark.xfail(strict=True, reason='the attribute decoder cannot see the Protocol-ID, see the ledger note')
def test_an_ospf_adjacency_label_is_reported_with_the_ospf_flags() -> None:
    flags = adjacency(OSPF_V | OSPF_L, pack('!I', LABEL)[1:]).flags
    assert (flags.get('V'), flags.get('L'), flags.get('B')) == (1, 1, 0)


@pytest.mark.rfc('rfc9085#2.2.2-lan-adjacency-sid-flags-per-protocol')
@pytest.mark.xfail(strict=True, reason='the attribute decoder cannot see the Protocol-ID, see the ledger note')
def test_an_ospf_lan_adjacency_label_is_reported_with_the_ospf_flags() -> None:
    flags = lan_adjacency(OSPF_V | OSPF_L, OSPF_NEIGHBOR, pack('!I', LABEL)[1:])['flags']
    assert isinstance(flags, dict)
    assert (flags.get('V'), flags.get('L'), flags.get('B')) == (1, 1, 0)
