#!/usr/bin/env python3
# encoding: utf-8

"""The reserved bits of an MT-ID are not part of the MT-ID

RFC 9552 5.2.2.1, for the Multi-Topology Identifier TLV: the Type is 263, "the
length is 2*n, and n is the number of MT-IDs carried in the TLV", each field
being four reserved R bits followed by a 12 bit MT-ID. For IS-IS, "the Bits R
are reserved and MUST be set to 0 (as per Section 7.2 of RFC5120) when
originated and ignored on receipt".

They were not ignored. The decoder read the whole 16 bit field, so a peer
setting the reserved bits reported MT-ID 61442 where the topology is 2. That is
not cosmetic: link.py puts topology_ids in both __eq__ and __hash__, so the same
link in the same topology compared unequal to itself, and hashed differently,
depending on bits the RFC tells us to disregard.

The mask was already written down, in the loop commented out directly above the
live code:

    # tids.append(payload & 0x0FFF)

so the original author knew. The live path dropped it. Adding a length gate
around that path earlier in this series made it look deliberate, which is the
hazard the session working main named: hardening code ratifies its current
behaviour, and a gate written around a decode says nothing about whether the
decode is right.
"""

from struct import pack


import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MTID


def mtid(value):
    return MTID.unpack(pack('!H', value))


class TestTheReservedBitsAreIgnored:
    @pytest.mark.parametrize('reserved', [0x0, 0x1, 0x7, 0xF])
    def test_whatever_the_peer_puts_in_them(self, reserved) -> None:
        assert mtid((reserved << 12) | 2).topologies == 2

    def test_the_full_twelve_bits_survive(self) -> None:
        # the mask must not eat the MT-ID itself: 0x0FFF is the largest
        assert mtid(0x0FFF).topologies == 0x0FFF
        assert mtid(0xFFFF).topologies == 0x0FFF

    def test_zero_is_still_zero(self) -> None:
        assert mtid(0).topologies == 0

    @pytest.mark.parametrize('topology', [0, 1, 2, 100, 4094, 4095])
    def test_a_conformant_peer_is_unaffected(self, topology) -> None:
        # R bits zero, which is what the RFC requires of a sender, so masking
        # must change nothing at all for anyone doing it properly
        assert mtid(topology).topologies == topology


class TestItChangesIdentity:
    """Why the mask matters beyond the rendered number

    topology_ids feeds the link NLRI's __eq__ and __hash__, so two descriptions
    of one link differing only in bits we are told to ignore were two different
    links as far as the RIB was concerned.
    """

    def test_two_mtids_differing_only_in_reserved_bits_are_equal(self) -> None:
        assert mtid(0xF002) == mtid(0x0002)

    def test_equal_mtids_hash_equal(self) -> None:
        """Python requires a == b to imply hash(a) == hash(b)

        Masking created this hazard rather than removing it. Before the mask,
        __eq__ compared raw 16 bit values and __hash__ hashed str(self), which
        renders the packed bytes: both said "different", wrongly but
        consistently. Masking made __eq__ say "same" while __hash__ still
        reached the bytes, so the invariant broke and a set or dict keyed on
        these would hold one link twice and a lookup could miss it.
        """
        assert mtid(0xF002) == mtid(0x0002)
        assert hash(mtid(0xF002)) == hash(mtid(0x0002))
        assert len({mtid(0xF002), mtid(0x0002)}) == 1

    def test_the_link_nlri_indexes_once(self) -> None:
        # the consequence at the level that matters: topology_ids feeds the link
        # NLRI's __eq__ AND __hash__, so both halves have to agree or the RIB
        # holds the same link under two keys
        from struct import pack

        from exabgp.bgp.message.action import Action
        from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
        from exabgp.protocol.family import AFI, SAFI

        local = pack('!HH', 256, 8) + pack('!HH', 512, 4) + b'\x00\x00\xff\xfd'

        def link(topology):
            body = b'\x03' + b'\x00' * 8 + local + pack('!HH', 263, 2) + pack('!H', topology)
            nlri, _ = BGPLS.unpack_nlri(
                AFI.bgpls, SAFI.bgp_ls, pack('!HH', 2, len(body)) + body, Action.ANNOUNCE, False
            )
            return nlri

        clean, reserved = link(0x0002), link(0xF002)
        assert clean == reserved
        assert hash(clean) == hash(reserved)
        assert len({clean, reserved}) == 1
        assert len({clean, link(0x0003)}) == 2

    def test_and_different_topologies_still_differ(self) -> None:
        # the gate must not make everything equal, which masking too hard would
        assert mtid(2) != mtid(3)

    def test_comparing_with_something_else_answers(self) -> None:
        # __eq__ read other.topologies with nothing checking what other was, so
        # this raised AttributeError instead of answering. Removing the guard
        # again fails this test, which is what makes it the load bearing half.
        #
        # The class also spelled its inequality __neq__, which Python never
        # calls. That was dead code rather than a defect: != already fell back
        # to negating __eq__ and behaved correctly. Renaming it to __ne__ is
        # verified to change nothing, so it is tidying, not a fix.
        assert (mtid(2) == 42) is False
        assert (mtid(2) != 42) is True
        assert (mtid(2) == None) is False  # noqa: E711 - the operator is the point


class TestTheLengthGate:
    def test_a_field_which_is_not_there(self) -> None:
        for payload in (b'', b'\x00'):
            with pytest.raises(Notify):
                MTID.unpack(payload)

    def test_the_smallest_valid_tlv_decodes(self) -> None:
        assert MTID.unpack(pack('!H', 7)).topologies == 7


class TestWhatIsKnownAndNotFixed:
    """A longer TLV is truncated rather than refused or read

    RFC 9552 5.2.2.1 allows 2*n bytes in general, but says that "in a Link or
    Prefix Descriptor, only a single MT-ID TLV containing the MT-ID of the
    topology where the link or the prefix is reachable is allowed", and both
    users of this class on this branch are descriptors. So a longer TLV is
    malformed here, and it is currently accepted with everything past the first
    MT-ID discarded in silence.

    Left alone on purpose. Refusing it narrows what the branch accepts, which is
    a compatibility change on a stable release, and reading all of them turns a
    number into a list. Pinned so the behaviour is visible and changing it is a
    decision rather than a side effect.
    """

    def test_only_the_first_mtid_is_read(self) -> None:
        assert MTID.unpack(pack('!HH', 2, 7)).topologies == 2
        assert MTID.unpack(pack('!HHH', 2, 7, 9)).topologies == 2

    def test_the_masking_applies_to_the_one_it_reads(self) -> None:
        assert MTID.unpack(pack('!HH', 0xF002, 7)).topologies == 2
