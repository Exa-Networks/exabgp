"""A BGP-LS peer could crash the API writer by mis-sizing a link descriptor.

The Link NLRI descriptor loop hands each sub-tlv a slice sized entirely by the peer's own
tlv_length, with no gate.  Four of the decoders it calls assigned their result inside an
`if`/`elif` on that length and had no `else`, so any other length left the name unbound;
three more read a fixed-width field off a payload which could be shorter.

None of that fired in unpack_nlri, because the descriptors parse lazily.  The message was
ACCEPTED, and the UnboundLocalError or struct.error surfaced later, in json(), inside the
API writer.  That is the blast radius of GHSA-jcrv-p53f-v5w5 reached a different way: a
peer choosing what happens to the process that consumes its routes.

Random-bytes fuzzing could not find it.  tests/unit/test_input_validation.py already drove
BGPLS.unpack_nlri with os.urandom and called json(), which is the right design, but random
bytes essentially never assemble a well-framed 0x0103 TLV header.  These seeds are framed.

Two rules are pinned here:
  - a length the decoder cannot read is a Notify, not a raw exception
  - it is raised at the boundary, out of unpack_nlri, not later out of json()
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

TLV_LINK_ID = 258
TLV_IPV4_IFACE = 259
TLV_IPV4_NEIGH = 260
TLV_IPV6_IFACE = 261
TLV_IPV6_NEIGH = 262
TLV_MULTI_TOPO = 263
TLV_OSPF_ROUTE = 264
TLV_IP_REACH = 265

NLRI_LINK = 2
NLRI_PREFIX_V4 = 3

# a prefix NLRI without its IP Reachability TLV is refused before any sub-tlv is read, so
# the OSPF route type can only be reached with a well formed one alongside it
IP_REACH_COMPANION = pack('!HH', TLV_IP_REACH, 4) + bytes([24, 192, 0, 2])

# name, NLRI type, sub-tlv code, the payload lengths this decoder can read, companion TLVs
READABLE: list[tuple[str, int, int, set[int], bytes]] = [
    ('ipv4 interface address', NLRI_LINK, TLV_IPV4_IFACE, {4, 16}, b''),
    ('ipv6 interface address', NLRI_LINK, TLV_IPV6_IFACE, {4, 16}, b''),
    ('ipv4 neighbor address', NLRI_LINK, TLV_IPV4_NEIGH, {4, 16}, b''),
    ('ipv6 neighbor address', NLRI_LINK, TLV_IPV6_NEIGH, {4, 16}, b''),
    ('link identifier', NLRI_LINK, TLV_LINK_ID, set(range(8, 20)), b''),
    ('multi topology', NLRI_LINK, TLV_MULTI_TOPO, set(range(2, 20)), b''),
    ('ospf route type', NLRI_PREFIX_V4, TLV_OSPF_ROUTE, {1}, IP_REACH_COMPANION),
    ('ip reachability', NLRI_PREFIX_V4, TLV_IP_REACH, set(range(1, 20)), b''),
]

IDS = [row[0] for row in READABLE]

MAX_TESTED_LENGTH = 20


def descriptor(nlri_type: int, tlv_type: int, payload: bytes, companion: bytes = b'') -> bytes:
    """A well framed BGP-LS NLRI carrying the sub-tlv under test, and whatever it needs."""
    body = bytes([3]) + bytes(8) + pack('!HH', tlv_type, len(payload)) + payload + companion
    return pack('!HH', nlri_type, len(body)) + body


@pytest.mark.parametrize('name, nlri_type, tlv_type, readable, companion', READABLE, ids=IDS)
def test_a_length_the_decoder_cannot_read_is_a_protocol_error(
    name: str, nlri_type: int, tlv_type: int, readable: set[int], companion: bytes
) -> None:
    """Every length, not only the ones a decoder likes.  Notify or a value, never a crash."""
    refused = 0
    for length in range(MAX_TESTED_LENGTH):
        data = descriptor(nlri_type, tlv_type, bytes(length), companion)
        try:
            nlri, _ = NLRI.unpack_nlri(AFI.bgpls, SAFI.bgp_ls, data, Action.ANNOUNCE, None, None)
        except Notify:
            refused += 1
            assert length not in readable, f'{name} refuses {length} bytes, which it can read'
            continue
        assert length in readable, f'{name} accepted {length} bytes, which it cannot read'
        nlri.json()

    assert refused, f'{name} refused no length, so this test pins nothing'


@pytest.mark.parametrize('name, nlri_type, tlv_type, readable, companion', READABLE, ids=IDS)
def test_the_error_reaches_the_peer_rather_than_the_api_writer(
    name: str, nlri_type: int, tlv_type: int, readable: set[int], companion: bytes
) -> None:
    """Raised out of unpack_nlri, where it becomes a NOTIFICATION.

    A Notify raised from json() instead is a session torn down inside the API writer, with
    the peer's message already accepted and nothing left to tell the peer what was wrong.
    """
    for length in sorted(set(range(MAX_TESTED_LENGTH)) - readable):
        data = descriptor(nlri_type, tlv_type, bytes(length), companion)
        with pytest.raises(Notify):
            NLRI.unpack_nlri(AFI.bgpls, SAFI.bgp_ls, data, Action.ANNOUNCE, None, None)


@pytest.mark.parametrize(
    'name, nlri_type, tlv_type, payload',
    [
        ('ipv4 interface address', NLRI_LINK, TLV_IPV4_IFACE, bytes([192, 0, 2, 1])),
        ('ipv4 neighbor address', NLRI_LINK, TLV_IPV4_NEIGH, bytes([192, 0, 2, 2])),
        ('ipv6 interface address', NLRI_LINK, TLV_IPV6_IFACE, bytes([0x20, 0x01, 0x0D, 0xB8] + [0] * 11 + [1])),
    ],
    ids=['ipv4 interface address', 'ipv4 neighbor address', 'ipv6 interface address'],
)
def test_a_well_formed_descriptor_still_decodes_to_its_address(
    name: str, nlri_type: int, tlv_type: int, payload: bytes
) -> None:
    """The gate must not have narrowed what a working router already sends.

    Asserting the address, not merely that something decoded: a decoder which returned the
    wrong address would satisfy every other test in this file.
    """
    from exabgp.protocol.ip import IP

    data = descriptor(nlri_type, tlv_type, payload)
    nlri, _ = NLRI.unpack_nlri(AFI.bgpls, SAFI.bgp_ls, data, Action.ANNOUNCE, None, None)

    expected = str(IP.create_ip(payload))
    assert expected in nlri.json(), f'{name} lost {expected} on the way to the API'
