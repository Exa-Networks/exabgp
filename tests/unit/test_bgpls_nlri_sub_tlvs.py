#!/usr/bin/env python3
# encoding: utf-8

"""A BGP-LS descriptor sub-TLV is sized entirely by the peer

link.py reads a sub-TLV header and hands the decoder a slice whose length comes
from the peer's own tlv_length, with nothing checking it against what the
decoder needs. Eight of them then read a fixed width off that slice:

    ifaceaddr, neighaddr   four bytes or sixteen, and NO else, so anything
                           else left addr unbound and an UnboundLocalError
                           escaped the decoder
    linkid                 eight bytes, no gate at any length
    multitopology          two bytes
    ospfroute              one byte, same missing else
    ipreach                a prefix length byte

None of it was reachable by the existing fuzzing: random bytes essentially never
assemble a well framed 0x0103 header, so a green sweep said nothing about this
code. Instrumenting the whole suite before these tests, IfaceAddr.unpack was
entered TWICE and LinkIdentifier.unpack ONCE, out of 6510 tests.

Found by the session working main, where the same defects fire from json() in
the API writer because their BGP-LS NLRIs parse lazily. On this branch they
parse eagerly, so the failure was at the decoder, which is the right place: the
reactor turns it into a NOTIFICATION the peer receives instead of a traceback
nobody reads. That difference is worth keeping, and the test below pins it.
"""

import json
from struct import pack

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS
from exabgp.protocol.family import AFI, SAFI

# a well formed local node descriptor, so the NLRI reaches its sub-TLVs at all
LOCAL_NODE = pack('!HH', 256, 8) + pack('!HH', 512, 4) + b'\x00\x00\xff\xfd'

# a well formed IP reachability TLV. A prefix NLRI without one is refused before
# any other sub-TLV is read, so a prefix sub-TLV cannot be tested on its own:
# the test would pass for the wrong reason.
IP_REACHABILITY = pack('!HH', 265, 2) + bytes([24, 192])

LINK, PREFIX = 2, 3

ADDRESS_TLVS = [259, 260, 261, 262]
FIXED_WIDTH_TLVS = [(258, 8), (263, 2)]


def nlri_bytes(nlri_type, *sub_tlvs):
    body = b'\x03' + b'\x00' * 8 + LOCAL_NODE + b''.join(sub_tlvs)
    return pack('!HH', nlri_type, len(body)) + body


def decode(wire):
    result = BGPLS.unpack_nlri(AFI.bgpls, SAFI.bgp_ls, wire, Action.ANNOUNCE, False)
    return result[0] if isinstance(result, tuple) else result


class TestAMalformedSubTlvIsRefused:
    @pytest.mark.parametrize('tlv', ADDRESS_TLVS)
    @pytest.mark.parametrize('length', [0, 1, 3, 5, 8, 15, 17])
    def test_an_address_which_is_neither_four_nor_sixteen_bytes(self, tlv, length) -> None:
        wire = nlri_bytes(LINK, pack('!HH', tlv, length) + b'\x00' * length)
        with pytest.raises(Notify):
            decode(wire)

    @pytest.mark.parametrize('tlv,needed', FIXED_WIDTH_TLVS)
    @pytest.mark.parametrize('short', [0, 1])
    def test_a_fixed_width_field_which_is_not_there(self, tlv, needed, short) -> None:
        length = max(needed - 1 - short, 0)
        wire = nlri_bytes(LINK, pack('!HH', tlv, length) + b'\x00' * length)
        with pytest.raises(Notify):
            decode(wire)

    def test_an_ospf_route_type_which_is_not_one_byte(self) -> None:
        # a prefix sub-TLV, so it needs the reachability TLV beside it
        for length in (0, 2, 4):
            wire = nlri_bytes(PREFIX, IP_REACHABILITY, pack('!HH', 264, length) + b'\x00' * length)
            with pytest.raises(Notify):
                decode(wire)


class TestTheErrorComesFromTheDecoder:
    """Not from json(), which is the API writer and far too late

    A gate alone would satisfy every assertion above while still raising inside
    the writer. This is the assertion which says WHERE, and without it the
    late-error regression is invisible.
    """

    @pytest.mark.parametrize('tlv', ADDRESS_TLVS)
    def test_unpack_nlri_raises_rather_than_the_renderer(self, tlv) -> None:
        wire = nlri_bytes(LINK, pack('!HH', tlv, 5) + b'\x00' * 5)
        raised_at_decode = False
        try:
            nlri = decode(wire)
        except Notify:
            raised_at_decode = True
            nlri = None
        assert raised_at_decode, f'TLV {tlv} was accepted; the error would surface in the API writer'
        assert nlri is None


class TestTheGoodPathStillWorks:
    """A gate which also broke well formed input satisfies every test above"""

    def test_an_ipv4_interface_address_survives(self) -> None:
        wire = nlri_bytes(LINK, pack('!HH', 259, 4) + bytes([192, 0, 2, 1]))
        nlri = decode(wire)
        assert nlri is not None
        assert '192.0.2.1' in nlri.json()

    def test_an_ipv6_neighbour_address_survives(self) -> None:
        address = bytes([0x20, 0x01, 0x0D, 0xB8]) + b'\x00' * 12
        wire = nlri_bytes(LINK, pack('!HH', 262, 16) + address)
        nlri = decode(wire)
        assert nlri is not None
        assert '2001:db8::' in nlri.json()

    def test_a_link_identifier_survives(self) -> None:
        wire = nlri_bytes(LINK, pack('!HH', 258, 8) + pack('!LL', 7, 9))
        nlri = decode(wire)
        assert nlri is not None
        rendered = nlri.json()
        assert '"link-local-id": 7' in rendered
        assert '"link-remote-id": 9' in rendered

    def test_a_multi_topology_identifier_survives(self) -> None:
        wire = nlri_bytes(LINK, pack('!HH', 263, 2) + pack('!H', 42))
        nlri = decode(wire)
        assert nlri is not None
        assert 42 in json.loads(nlri.json())['multi-topology-ids']

    def test_an_ospf_route_type_survives(self) -> None:
        wire = nlri_bytes(PREFIX, IP_REACHABILITY, pack('!HH', 264, 1) + bytes([2]))
        nlri = decode(wire)
        assert nlri is not None
        assert json.loads(nlri.json())['ospf-route-type']


class TestAWellFormedValueIsNotSilentlyDropped:
    """A gate says what is refused, never that what is accepted was kept

    LinkIdentifier.unpack built its object without a packed form, __len__ read
    that missing form as 0, and so every well formed identifier tested false in

        self.link_ids = link_ids if link_ids else []

    and was replaced by an empty list. The sub-TLV decoded correctly, the wire
    was accepted, no exception was raised anywhere, and the value simply never
    reached the API. Every assertion above passes with the bug present, because
    refusing bad input and keeping good input are different properties.

    str() on such an object raised TypeError too, iterating None.
    """

    def test_a_link_identifier_reaches_the_nlri(self) -> None:
        wire = nlri_bytes(LINK, pack('!HH', 258, 8) + pack('!LL', 7, 9))
        nlri = decode(wire)
        assert nlri.link_ids, 'the identifier decoded, then was dropped for being falsy'
        assert nlri.link_ids[0].local_id == 7
        assert nlri.link_ids[0].remote_id == 9

    def test_a_link_identifier_can_be_rendered(self) -> None:
        wire = nlri_bytes(LINK, pack('!HH', 258, 8) + pack('!LL', 7, 9))
        identifier = decode(wire).link_ids[0]
        assert str(identifier)
        assert repr(identifier)
        assert hash(identifier) is not None
        assert identifier.pack() is not None

    def test_it_reaches_as_dict_too(self) -> None:
        # json() and as_dict() are two renderers over one value, and a value
        # dropped at the source is missing from both
        wire = nlri_bytes(LINK, pack('!HH', 258, 8) + pack('!LL', 7, 9))
        assert decode(wire).as_dict()['link-identifiers'] == [{'link-local-id': 7, 'link-remote-id': 9}]


class TestTheRenderedNlriIsValidJson:
    """The whole point of the advisory this branch is closing

    Un-dropping the identifier was not enough on its own: its json() emitted a
    bare '"link-local-id": 7, "link-remote-id": 9' with no braces, which link.py
    joins inside a [ ] array. One identifier or ten, the result was a JSON array
    holding loose keys, and the API stream stopped parsing. A substring
    assertion is happy with that, so parse the document instead.
    """

    @pytest.mark.parametrize(
        'sub_tlv',
        [
            pack('!HH', 258, 8) + pack('!LL', 7, 9),
            pack('!HH', 259, 4) + bytes([192, 0, 2, 1]),
            pack('!HH', 260, 4) + bytes([192, 0, 2, 2]),
            pack('!HH', 261, 16) + bytes([0x20, 0x01, 0x0D, 0xB8]) + b'\x00' * 12,
            pack('!HH', 262, 16) + bytes([0x20, 0x01, 0x0D, 0xB8]) + b'\x00' * 12,
            pack('!HH', 263, 2) + pack('!H', 42),
        ],
    )
    def test_a_link_nlri_parses(self, sub_tlv) -> None:
        json.loads(decode(nlri_bytes(LINK, sub_tlv)).json())

    def test_a_prefix_nlri_parses(self) -> None:
        wire = nlri_bytes(PREFIX, IP_REACHABILITY, pack('!HH', 264, 1) + bytes([2]))
        json.loads(decode(wire).json())

    def test_two_identifiers_do_not_flatten_into_one_object(self) -> None:
        # the shape which made the missing braces unambiguous
        from exabgp.bgp.message.update.nlri.bgpls.tlvs.linkid import LinkIdentifier

        rendered = '[ %s ]' % ', '.join(_.json() for _ in (LinkIdentifier(7, 9), LinkIdentifier(1, 2)))
        assert json.loads(rendered) == [
            {'link-local-id': 7, 'link-remote-id': 9},
            {'link-local-id': 1, 'link-remote-id': 2},
        ]
