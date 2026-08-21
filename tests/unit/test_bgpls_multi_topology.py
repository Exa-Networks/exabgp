"""Reserved bits a peer sets must not change what a Multi-Topology TLV means.

RFC 9552 5.2.2.1 makes the field four reserved R bits followed by a 12 bit MT-ID, and says
"the Bits R are reserved and MUST be set to 0 when originated and ignored on receipt".

This read all sixteen bits, so a peer which set them reported MT-ID 2 as 61442.  The mask
was in the file already, in a loop commented out directly above the live code: known once,
then lost.  A length check was later added around the raw read, which is the trap session
5.0 named after finding the identical bug on their branch - hardening a decode makes the
decode look chosen, and reviewing the gate never finds it.  The question which finds it is
what the decoder does with the bytes the gate just approved.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

TLV_MULTI_TOPO = 263
NLRI_LINK = 2

RESERVED_BITS = 0xF000
MTID_MAX = 0x0FFF


def link_with(raw: int) -> bytes:
    """A Link NLRI carrying one Multi-Topology descriptor holding exactly these bits."""
    body = bytes([3]) + bytes(8) + pack('!HH', TLV_MULTI_TOPO, 2) + pack('!H', raw)
    return pack('!HH', NLRI_LINK, len(body)) + body


def decoded(raw: int):
    nlri, _ = NLRI.unpack_nlri(AFI.bgpls, SAFI.bgp_ls, link_with(raw), Action.ANNOUNCE, None, None)
    return nlri


@pytest.mark.parametrize('mtid', [0, 1, 2, 100, MTID_MAX], ids=lambda v: f'mt-id {v}')
def test_the_reserved_bits_are_ignored_on_receipt(mtid: int) -> None:
    """The same topology, with and without the bits the RFC says to disregard."""
    clear = decoded(mtid)
    marked = decoded(RESERVED_BITS | mtid)

    assert clear.json() == marked.json(), f'reserved bits changed what MT-ID {mtid} renders as'


@pytest.mark.parametrize('mtid', [0, 1, 2, 100, MTID_MAX], ids=lambda v: f'mt-id {v}')
def test_the_topology_identifier_itself_survives(mtid: int) -> None:
    """A mask which returned zero would satisfy the test above and nothing else.

    MT-ID 4095 is the boundary: masking to fewer than twelve bits truncates it.
    """
    rendered = decoded(mtid).json()

    assert f'"multi-topology-ids": [ {mtid} ]' in rendered, f'MT-ID {mtid} did not survive the mask'


def test_two_topologies_are_still_told_apart() -> None:
    """Ignoring the reserved bits must not have flattened the field it guards."""
    assert decoded(1).json() != decoded(2).json()


def test_the_wire_bytes_are_kept_as_the_peer_sent_them() -> None:
    """Recorded, not fixed: identity here is the packed bytes, so the R bits still split it.

    Masking corrects what the TLV MEANS.  It cannot correct what the NLRI IS, because a
    BGP-LS NLRI is identified by the bytes it arrived as, so the same link in the same
    topology still indexes twice if a peer sets the reserved bits on one advertisement and
    not the other.

    Normalising _packed would fix that and is a change to the packed-bytes-first design
    rather than to this decoder: it would mean storing something other than what arrived,
    for every field where the wire allows a choice we are told to ignore.  That is worth
    deciding deliberately, so it is asserted here as it stands rather than left for someone
    to discover as a surprise.
    """
    clear = decoded(2)
    marked = decoded(RESERVED_BITS | 2)

    assert clear.json() == marked.json(), 'the rendered topology should already agree'
    assert clear.index() != marked.index(), 'identity now ignores the reserved bits: update this test and the RIB note'
