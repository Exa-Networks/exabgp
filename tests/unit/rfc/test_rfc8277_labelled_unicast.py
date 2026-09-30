"""RFC 8277: how many labels does an NLRI carry, and what ends the stack.

RFC 3107 left that ambiguous and RFC 8277 exists to close it.  Its answer has two halves:
without the Multiple Labels Capability an NLRI carries exactly one label and the S bit
means nothing (section 2.2); with it, the S bit delimits the stack (section 2.3).  exabgp
sends capability code 8 only when `capability { multiple-labels <count>; }` asks for it,
so a session is a section 2.2 session unless both ends sent it.

Both decoders used to parse the section 2.3 way on every session, and refused any NLRI
whose first field did not terminate the stack.  That cost a session over legal input: a
withdraw whose Compatibility field was neither 0x800000 nor 0x000000 nor S-bit-set was
read as an unterminated label stack and answered with a NOTIFICATION, where RFC 8277 says
in two separate sentences that the field's value is of no significance and must be
ignored.  The length now says where a one field stack ends, so those three sentences are
proven below rather than demonstrated as gaps.

Everything here drives the real registered decoders through `NLRI.unpack_nlri`, which is
the same call the UPDATE parser makes, so a test that passes says something about what a
peer can do to us rather than about a helper.
"""

from __future__ import annotations

from struct import pack
from typing import cast

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import ASN, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.label import LabelBase
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier import Labels, PathInfo, RouteDistinguisher
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib.route import Route
from exabgp.util.types import Buffer

# Section 2.2: the Length field counts bits, and a label contributes 24 of them.
LABEL_BITS = 24
# Section 4.3.2 of RFC 4364; the route distinguisher contributes 64 more to SAFI 128.
RD_BITS = 64

# 10.0.0.0/24, three octets of prefix behind a 24 bit mask.
PREFIX_BITS = 24
PREFIX = bytes([10, 0, 0])

# An arbitrary route distinguisher, type 0, AS 1, assigned number 2.
RD = pack('!HHL', 0, 1, 2)

# Section 2.4: the value RFC 3107 and RFC 8277 both recommend for the Compatibility
# field, and the value RFC 8277 records that some implementations send instead.
COMPATIBILITY_RECOMMENDED = 0x800000
COMPATIBILITY_LEGACY = 0x000000
# A third value, which the RFC permits because the field "is of no significance", and
# which is neither of the two exabgp's decoders recognise.
COMPATIBILITY_ARBITRARY = 0x000010


def label(value: int, *, bottom: bool = True, reserved: int = 0) -> bytes:
    """One 24 bit label field: 20 bits of label, 3 bits of Rsrv, 1 bit of S."""
    return pack('!L', (value << 4) | (reserved << 1) | (1 if bottom else 0))[1:]


def raw(value: int) -> bytes:
    """Three octets holding a value literally, for the fields which are not labels."""
    return pack('!L', value)[1:]


def labelled(stack: bytes, prefix: bytes = PREFIX, prefix_bits: int = PREFIX_BITS) -> bytes:
    """A SAFI 4 NLRI: one length octet in bits, the stack, then the prefix."""
    return bytes([len(stack) * 8 + prefix_bits]) + stack + prefix


def vpn(stack: bytes, rd: bytes = RD, prefix: bytes = PREFIX, prefix_bits: int = PREFIX_BITS) -> bytes:
    """A SAFI 128 NLRI: length in bits over the stack, the RD and the prefix."""
    return bytes([len(stack) * 8 + len(rd) * 8 + prefix_bits]) + stack + rd + prefix


def decode(
    data: bytes,
    afi: AFI = AFI.ipv4,
    safi: SAFI = SAFI.nlri_mpls,
    action: Action = Action.ANNOUNCE,
    addpath: bool = False,
) -> tuple[LabelBase, Buffer]:
    """The registered decoder for the family, called the way the UPDATE parser calls it.

    The cast is the registry's doing: `NLRI.unpack_nlri` dispatches on (afi, safi) and is
    typed to its base class, but both families here are registered to a LabelBase
    subclass, which is where `labels`, `rd` and `cidr` live.
    """
    nlri, rest = NLRI.unpack_nlri(afi, safi, data, action, addpath, Negotiated.UNSET)
    return cast(LabelBase, nlri), rest


# ----------------------------------------------------------------- section 2.2, Rsrv


@pytest.mark.rfc('rfc8277#2.2-rsrv-ignored-on-reception')
def test_a_label_with_a_zero_rsrv_field_decodes_to_its_label_and_prefix() -> None:
    nlri, rest = decode(labelled(label(100)))
    assert rest == b''
    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels is not None
    assert nlri.labels.labels == [100]


@pytest.mark.rfc('rfc8277#2.2-rsrv-ignored-on-reception', polarity='negative')
@pytest.mark.parametrize('reserved', [0b001, 0b010, 0b100, 0b111])
def test_a_label_whose_rsrv_bits_are_set_decodes_identically(reserved: int) -> None:
    """The three Rsrv bits must not reach the label value or the prefix."""
    nlri, rest = decode(labelled(label(100, reserved=reserved)))
    assert rest == b''
    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels is not None
    assert nlri.labels.labels == [100]


@pytest.mark.rfc('rfc8277#2.2-rsrv-ignored-on-reception', polarity='negative')
def test_we_do_not_set_the_rsrv_bits_when_we_build_a_label() -> None:
    """The other half of the sentence: SHOULD be set to zero on transmission."""
    packed = bytes(Labels.make_labels([100, 200]).pack_labels())
    for offset in range(0, len(packed), 3):
        field = int.from_bytes(packed[offset : offset + 3], 'big')
        assert (field >> 1) & 0b111 == 0, 'the Rsrv bits went out non zero'


# ------------------------------------------------------------------ section 2.2, S bit


@pytest.mark.rfc('rfc8277#2.2-s-bit-ignored-on-reception', polarity='negative')
def test_a_single_label_nlri_with_the_s_bit_clear_still_decodes() -> None:
    """Section 2.2 carries exactly one label, so its S bit carries no information.

    The peer is the one breaking the sentence here, by not setting a bit it MUST set, and
    the requirement on us is to carry on regardless.  This used to raise Notify(3,10).
    """
    nlri, rest = decode(labelled(label(100, bottom=False)))
    assert rest == b''
    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels is not None
    assert nlri.labels.labels == [100]


@pytest.mark.rfc('rfc8277#2.2-s-bit-ignored-on-reception')
def test_we_set_the_s_bit_on_the_label_we_transmit() -> None:
    """The transmission half of the same sentence, which exabgp does meet."""
    packed = bytes(Labels.make_labels([100]).pack_labels())
    assert int.from_bytes(packed, 'big') & 1 == 1


# ------------------------------------------------------------------ section 2.3, S bit


@pytest.mark.rfc('rfc8277#2.3-s-bit-zero-except-in-last-label')
def test_a_two_label_stack_ends_at_the_label_whose_s_bit_is_set() -> None:
    nlri, rest = decode(labelled(label(100, bottom=False) + label(200)))
    assert rest == b''
    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.labels is not None
    assert nlri.labels.labels == [100, 200]


@pytest.mark.rfc('rfc8277#2.3-s-bit-zero-except-in-last-label')
def test_we_set_the_s_bit_only_on_the_last_label_we_transmit() -> None:
    packed = bytes(Labels.make_labels([100, 200, 300]).pack_labels())
    bits = [int.from_bytes(packed[offset : offset + 3], 'big') & 1 for offset in range(0, len(packed), 3)]
    assert bits == [0, 0, 1]


@pytest.mark.rfc('rfc8277#2.3-s-bit-zero-except-in-last-label', polarity='negative')
def test_a_label_stack_with_no_bottom_of_stack_bit_is_refused() -> None:
    """Without the bit the stack has no end, and the prefix behind it would be eaten."""
    with pytest.raises(Notify) as raised:
        decode(labelled(label(100, bottom=False) + label(200, bottom=False)))
    assert raised.value.code == 3
    assert raised.value.subcode == 10


@pytest.mark.rfc('rfc8277#2.3-s-bit-zero-except-in-last-label', polarity='negative')
def test_a_vpn_label_stack_with_no_bottom_of_stack_bit_is_refused() -> None:
    """The VPN decoder is a second copy of the loop and has to refuse the same input.

    This is the one where a scanner does real damage: the bytes it would run into are the
    route distinguisher, whose leading zeroes look exactly like the 0x000000 next hop
    convention.
    """
    with pytest.raises(Notify) as raised:
        decode(vpn(label(100, bottom=False) + label(200, bottom=False)), safi=SAFI.mpls_vpn)
    assert raised.value.code == 3
    assert raised.value.subcode == 10


@pytest.mark.rfc('rfc8277#2.3-s-bit-zero-except-in-last-label', polarity='negative')
def test_a_stack_stops_at_the_first_bottom_of_stack_bit_even_when_the_mask_allows_more() -> None:
    """A length which would fit two labels must not make the decoder read two.

    The bytes after the terminated label are prefix, and a decoder which kept going would
    report 0.0.0.0/0 rather than the route the peer sent.
    """
    # The three prefix octets are a well formed label field, so a decoder which kept
    # reading would take them, run out of mask and report 0.0.0.0/0.
    nlri, rest = decode(labelled(label(100), prefix=bytes([0x00, 0x06, 0x41])))
    assert rest == b''
    assert str(nlri.cidr) == '0.6.65.0/24'
    assert nlri.labels is not None
    assert nlri.labels.labels == [100]


# --------------------------------------------------------- section 2.4, Compatibility


@pytest.mark.rfc('rfc8277#2.4-compatibility-ignored-on-reception')
@pytest.mark.parametrize('compatibility', [COMPATIBILITY_RECOMMENDED, COMPATIBILITY_LEGACY])
def test_a_withdraw_with_a_known_compatibility_value_decodes_to_its_prefix(compatibility: int) -> None:
    """The recommended value, and the one RFC 8277 records some implementations send."""
    nlri, rest = decode(labelled(raw(compatibility)), action=Action.WITHDRAW)
    assert rest == b''
    assert str(nlri.cidr) == '10.0.0.0/24'


@pytest.mark.rfc('rfc8277#2.4-compatibility-ignored-on-reception', polarity='negative')
@pytest.mark.rfc('rfc8277#2.4-compatibility-required-ignored')
def test_a_withdraw_with_an_arbitrary_compatibility_value_decodes_to_its_prefix() -> None:
    """RFC 8277 says the field is of no significance, so every value has to work.

    This is the one which cost a session: the three octets were read as a label, only
    0x800000, 0x000000 and a set bottom of stack bit ended the stack, and anything else
    was answered with Notify(3,10).  The length ends a one field stack now.
    """
    nlri, rest = decode(labelled(raw(COMPATIBILITY_ARBITRARY)), action=Action.WITHDRAW)
    assert rest == b''
    assert str(nlri.cidr) == '10.0.0.0/24'


@pytest.mark.rfc('rfc8277#2.4-compatibility-ignored-on-reception', polarity='negative')
def test_a_vpn_withdraw_with_an_arbitrary_compatibility_value_decodes_to_its_prefix() -> None:
    """The VPN decoder is a second copy of the loop, so it has to have learnt the same."""
    nlri, rest = decode(vpn(raw(COMPATIBILITY_ARBITRARY)), safi=SAFI.mpls_vpn, action=Action.WITHDRAW)
    assert rest == b''
    assert str(nlri.cidr) == '10.0.0.0/24'
    assert nlri.rd is not None
    assert str(nlri.rd) == ' rd 1:2'


@pytest.mark.rfc('rfc8277#2.4-compatibility-ignored-on-reception')
def test_the_prefix_length_of_a_withdraw_is_the_nlri_length_less_the_compatibility_field() -> None:
    """Section 2.4: the prefix length is not the NLRI length.

    A decoder which subtracted nothing would announce a /48, and one which subtracted
    twice would announce a /0.  Both are prefixes a peer never sent.
    """
    nlri, _ = decode(labelled(raw(COMPATIBILITY_RECOMMENDED)), action=Action.WITHDRAW)
    assert nlri.cidr.mask == PREFIX_BITS


# ---------------------------------------------------------- section 2.5, implicit withdraw


def route(labels: list[int], prefix: bytes = PREFIX, prefix_bits: int = PREFIX_BITS) -> LabelBase:
    stack = b''.join(label(value, bottom=index == len(labels) - 1) for index, value in enumerate(labels))
    nlri, _ = decode(bytes([len(stack) * 8 + prefix_bits]) + stack + prefix)
    return nlri


@pytest.mark.rfc('rfc8277#2.5-implicit-withdraw-replaces-label')
def test_two_routes_for_one_prefix_with_different_labels_share_a_rib_key() -> None:
    """Which is what makes the second implicitly withdraw the first."""
    assert route([100]).index() == route([200]).index()


@pytest.mark.rfc('rfc8277#2.5-implicit-withdraw-replaces-label')
def test_a_vpn_route_keeps_its_rib_key_when_only_the_label_changes() -> None:
    first, _ = decode(vpn(label(100)), safi=SAFI.mpls_vpn)
    second, _ = decode(vpn(label(200)), safi=SAFI.mpls_vpn)
    assert first.index() == second.index()


@pytest.mark.rfc('rfc8277#2.5-implicit-withdraw-replaces-label', polarity='negative')
def test_a_different_prefix_does_not_share_the_rib_key() -> None:
    assert route([100]).index() != route([100], prefix=bytes([10, 0, 1])).index()


@pytest.mark.rfc('rfc8277#2.5-implicit-withdraw-replaces-label', polarity='negative')
def test_a_different_route_distinguisher_does_not_share_the_rib_key() -> None:
    """Otherwise every VPN would implicitly withdraw every other VPN's route."""
    first, _ = decode(vpn(label(100)), safi=SAFI.mpls_vpn)
    second, _ = decode(vpn(label(100), rd=pack('!HHL', 0, 9, 9)), safi=SAFI.mpls_vpn)
    assert first.index() != second.index()


@pytest.mark.rfc('rfc8277#2.5-different-path-id-does-not-withdraw')
def test_two_labelled_routes_with_different_path_identifiers_do_not_share_a_rib_key() -> None:
    first, _ = decode(pack('!L', 1) + labelled(label(100)), addpath=True)
    second, _ = decode(pack('!L', 2) + labelled(label(100)), addpath=True)
    assert first.index() != second.index()


@pytest.mark.rfc('rfc8277#2.5-different-path-id-does-not-withdraw', polarity='negative')
def test_two_labelled_routes_with_the_same_path_identifier_share_a_rib_key() -> None:
    first, _ = decode(pack('!L', 1) + labelled(label(100)), addpath=True)
    second, _ = decode(pack('!L', 1) + labelled(label(200)), addpath=True)
    assert first.index() == second.index()


# -------------------------------------------------------------------- malformed input

# Every entry is peer input which cannot be a valid NLRI.  The assertion is that each
# raises Notify, which is a NOTIFICATION, rather than a Python exception, which is a
# crash on the receive path.
MALFORMED: list[tuple[str, bytes, SAFI]] = [
    (
        # The length leaves no prefix bits behind the first field, so the section 2.2
        # reading of it is a /0.  That is the default route the old bug manufactured and
        # the one shape the length cannot tell from a stack which ate the prefix.
        'a length which leaves no prefix bits behind an unterminated field',
        bytes([PREFIX_BITS]) + label(100, bottom=False) + label(200) + PREFIX,
        SAFI.nlri_mpls,
    ),
    ('a prefix shorter than the length claims', bytes([LABEL_BITS + 32]) + label(100) + bytes([10, 0]), SAFI.nlri_mpls),
    ('a mask longer than IPv4 allows', bytes([LABEL_BITS + 200]) + label(100) + PREFIX, SAFI.nlri_mpls),
    ('a label stack cut off mid label', bytes([LABEL_BITS + PREFIX_BITS]) + bytes([0x00, 0x06]), SAFI.nlri_mpls),
    (
        'a truncated route distinguisher',
        bytes([LABEL_BITS + RD_BITS + PREFIX_BITS]) + label(100) + RD[:5],
        SAFI.mpls_vpn,
    ),
    ('a VPN length with no room for the RD', bytes([LABEL_BITS + PREFIX_BITS]) + label(100) + PREFIX, SAFI.mpls_vpn),
    ('an empty NLRI', b'', SAFI.nlri_mpls),
    ('a length octet with nothing behind it', bytes([LABEL_BITS + PREFIX_BITS]), SAFI.nlri_mpls),
]


@pytest.mark.parametrize('name,data,safi', MALFORMED, ids=[entry[0] for entry in MALFORMED])
def test_malformed_labelled_nlri_raises_notify_and_not_a_python_exception(name: str, data: bytes, safi: SAFI) -> None:
    with pytest.raises(Notify):
        decode(data, safi=safi)


def test_a_round_trip_through_the_decoder_reproduces_the_wire_bytes() -> None:
    """A decoder which lost the stack would not be able to put it back.

    Not a requirement of its own: RFC 8277 states its wire format declaratively.  It is
    here because it is the cheapest check that the packed-bytes-first storage in
    LabelBase and IPVPNBase really is the bytes which arrived.
    """
    wire = vpn(label(100, bottom=False) + label(200))
    nlri, _ = decode(wire, safi=SAFI.mpls_vpn)
    assert bytes(nlri.pack_nlri(Negotiated.UNSET)) == wire


def test_the_configuration_parser_can_build_a_stack_we_are_not_allowed_to_send() -> None:
    """Evidence for rfc8277#2-single-label-without-capability being a gap and not a note.

    `Labels.make_labels` is what `label` in the configuration parser returns, and there
    is no capability between it and the wire.
    """
    stack = Labels.make_labels([100, 200])
    assert len(stack) == 6
    from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
    from exabgp.bgp.message.update.nlri.cidr import CIDR

    built = IPVPN.from_cidr(
        CIDR.create_cidr(PREFIX + bytes([0]), PREFIX_BITS),
        AFI.ipv4,
        SAFI.mpls_vpn,
        PathInfo.DISABLED,
        labels=stack,
        rd=RouteDistinguisher(RD),
    )
    assert bytes(built.pack_nlri(Negotiated.UNSET)) == vpn(label(100, bottom=False) + label(200))


# ------------------------------------------------- section 2.1, the Multiple Labels Capability
#
# Capability code 8 is decoded by MultipleLabels, Negotiated.labels_limit says how many
# labels a prefix may carry on the session, and pack_nlri keeps no more than that, the top
# of the stack kept.  The tests build the session the way a real one is built, from OPEN
# capabilities decoded off the wire, and generate the UPDATE through
# UpdateCollection.messages, which is what the outgoing RIB calls.

MULTIPROTOCOL = 1
MULTIPLE_LABELS = 8

LABELLED_UNICAST = (AFI.ipv4, SAFI.nlri_mpls)


def triple(count: int, afi: AFI = AFI.ipv4, safi: SAFI = SAFI.nlri_mpls) -> bytes:
    """One <AFI, SAFI, Count> triple of the Multiple Labels Capability."""
    return pack('!HBB', int(afi), int(safi), count)


def capabilities(multiple_labels: bytes | None = None) -> Capabilities:
    """An OPEN's capabilities offering IPv4 labelled unicast, decoded off the wire.

    `multiple_labels` is the value of a Multiple Labels Capability, or None for an OPEN
    which does not carry one.
    """
    fields = [(MULTIPROTOCOL, pack('!HBB', int(AFI.ipv4), 0, int(SAFI.nlri_mpls)))]
    if multiple_labels is not None:
        fields.append((MULTIPLE_LABELS, multiple_labels))
    body = b''.join(bytes([code, len(value)]) + value for code, value in fields)
    parameter = bytes([2, len(body)]) + body
    return Capabilities.unpack(bytes([len(parameter)]) + parameter)


def session(ours: bytes | None, theirs: bytes | None) -> Negotiated:
    """A negotiated outgoing session, each OPEN carrying the given Multiple Labels value."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    negotiated = Negotiated(neighbor, Direction.OUT)
    # decoding what this session sent, or a path written for another rule: RFC 8955 6 has its own tests
    negotiated.neighbor.enforce_first_as = False
    negotiated.sent(Open.make_open(Version(4), ASN(65001), HoldTime(90), RouterID('192.0.2.1'), capabilities(ours)))
    negotiated.received(
        Open.make_open(Version(4), ASN(65002), HoldTime(90), RouterID('192.0.2.2'), capabilities(theirs))
    )
    assert LABELLED_UNICAST in negotiated.families, 'the session did not negotiate labelled unicast'
    return negotiated


def configured(labels: str) -> list[Route]:
    """The routes a static labelled route produces, through the configuration parser."""
    configuration = Configuration([''], text=True)
    line = f'route 10.0.0.0/24 next-hop 192.0.2.1 label {labels}'
    assert configuration.partial('static', line, 'announce'), str(configuration.error)
    routes = configuration.pop_routes()
    assert routes, 'the line parsed to no route at all'
    return routes


def labels_sent(routes: list[Route], negotiated: Negotiated) -> list[list[int]]:
    """The label stack of every NLRI we put on the wire, read back off our own UPDATEs."""
    routed = [RoutedNLRI(route.nlri, route.nexthop) for route in routes]
    stacks: list[list[int]] = []
    for message in UpdateCollection(routed, [], routes[0].attributes).messages(negotiated):
        update = Update.unpack_message(message[19:], negotiated)
        assert isinstance(update, Update), 'what we generated did not decode as an UPDATE'
        for announced in update.parse(negotiated).announces:
            nlri = cast(LabelBase, announced.nlri)
            assert nlri.labels is not None, 'a labelled route went out without a label'
            stacks.append(list(nlri.labels.labels))
    assert stacks, 'no labelled NLRI was generated, so there is nothing to look at'
    return stacks


@pytest.mark.rfc('rfc8277#2-single-label-without-capability')
def test_without_the_capability_a_configured_label_stack_goes_out_as_a_single_label() -> None:
    """Neither OPEN carries code 8, which is every session unless the operator asks."""
    assert labels_sent(configured('[ 100 200 ]'), session(None, None)) == [[100]]


@pytest.mark.rfc('rfc8277#2.1-must-not-send-multiple-labels-uncapable')
def test_a_peer_which_offers_multiple_labels_alone_does_not_let_us_send_two() -> None:
    """The capability has to go both ways: here the peer sends it and we do not."""
    for stack in labels_sent(configured('[ 100 200 ]'), session(None, triple(2))):
        assert len(stack) == 1, f'{stack} bound to one prefix on a session we never sent code 8 on'


@pytest.mark.rfc('rfc8277#2.1-duplicate-triple-ignored')
def test_a_duplicate_triple_does_not_raise_the_count_the_first_one_gave() -> None:
    """The peer says two, then eight, for the same family: two is the only one which counts."""
    negotiated = session(triple(3), triple(2) + triple(8))
    for stack in labels_sent(configured('[ 100 200 300 ]'), negotiated):
        assert len(stack) <= 2, f'{stack} is more than the two labels the first triple allows'


@pytest.mark.rfc('rfc8277#2.1-capability-length-multiple-of-four', polarity='negative')
def test_a_multiple_labels_capability_of_five_octets_is_malformed() -> None:
    with pytest.raises(Notify) as raised:
        capabilities(triple(2) + b'\x00')
    assert raised.value.code == 2


@pytest.mark.rfc('rfc8277#3.2.3-must-not-send-more-labels-than-peer-handles')
def test_we_send_no_more_labels_than_the_peer_said_it_handles() -> None:
    """Both ends exchanged the capability, which leaves only the count to respect."""
    negotiated = session(triple(3), triple(2))
    for stack in labels_sent(configured('[ 100 200 300 ]'), negotiated):
        assert len(stack) <= 2, f'{stack} is more than the two labels the peer announced'


@pytest.mark.rfc('rfc8277#2.1-must-not-send-multiple-labels-uncapable')
def test_a_peer_which_did_not_offer_multiple_labels_is_sent_one_even_when_we_did() -> None:
    """The other direction of the capability: we sent code 8 and the peer did not."""
    assert labels_sent(configured('[ 100 200 ]'), session(triple(3), None)) == [[100]]


@pytest.mark.rfc('rfc8277#3.2.3-must-not-send-more-labels-than-peer-handles')
def test_a_stack_within_what_the_peer_handles_goes_out_whole() -> None:
    """A trim to one label always, or to the count we sent, would pass the tests above."""
    negotiated = session(triple(2), triple(3))
    assert labels_sent(configured('[ 100 200 300 ]'), negotiated) == [[100, 200, 300]]


def test_a_trimmed_stack_ends_with_the_bottom_of_stack_bit_and_a_length_to_match() -> None:
    """Unmarked: what trimming must get right on the wire, read off the bytes themselves.

    The decoder above would find the stack's end from the length even without the S bit,
    so the bytes are what says the last label kept was made the bottom of the stack.
    """
    (route,) = configured('[ 100 200 300 ]')
    packed = bytes(route.nlri.pack_nlri(session(None, None)))
    assert packed[0] == LABEL_BITS + PREFIX_BITS, 'the length still counts the labels dropped'
    assert packed[1:4] == label(100), 'the label kept is not the top of the stack, or lacks the S bit'
    assert packed[4:] == PREFIX


@pytest.mark.rfc('rfc8277#2.1-duplicate-triple-ignored', polarity='negative')
def test_an_ignored_first_triple_still_wins_over_a_later_one() -> None:
    """A Count of one is ignored, and still the first: the later eight does not count."""
    negotiated = session(triple(3), triple(1) + triple(8))
    assert labels_sent(configured('[ 100 200 ]'), negotiated) == [[100]]


@pytest.mark.rfc('rfc8277#2.1-capability-length-multiple-of-four')
@pytest.mark.parametrize('count', [1, 2, 3])
def test_a_multiple_labels_capability_of_whole_triples_is_accepted(count: int) -> None:
    decoded = capabilities(b''.join(triple(2 + index, safi=SAFI.nlri_mpls) for index in range(count)))
    assert decoded.announced(MULTIPLE_LABELS)


@pytest.mark.rfc('rfc8277#2.1-count-zero-or-one-not-sent')
@pytest.mark.parametrize('count', [0, 1])
def test_a_received_count_of_zero_or_one_is_ignored(count: int) -> None:
    negotiated = session(triple(3), triple(count))
    assert negotiated.labels_limit(*LABELLED_UNICAST) == 1


def neighbour_capabilities(statement: str) -> Capabilities:
    """The capabilities of the OPEN a neighbour configured with `statement` sends."""
    text = f"""
neighbor 192.0.2.2 {{
    router-id 192.0.2.1;
    local-address 192.0.2.1;
    local-as 65001;
    peer-as 65002;
    capability {{ {statement} }}
    family {{ ipv4 nlri-mpls; ipv4 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    neighbor = next(iter(configuration.neighbors.values()))
    return Capabilities().new(neighbor, False)


@pytest.mark.rfc('rfc8277#2.1-count-zero-or-one-not-sent', polarity='negative')
@pytest.mark.parametrize('count', ['0', '1', '256'])
def test_a_count_we_must_not_send_is_refused_by_the_configuration(count: str) -> None:
    text = f"""
neighbor 192.0.2.2 {{
    router-id 192.0.2.1;
    local-address 192.0.2.1;
    local-as 65001;
    peer-as 65002;
    capability {{ multiple-labels {count}; }}
    family {{ ipv4 nlri-mpls; }}
}}
"""
    assert not Configuration([text], text=True).reload()


def test_the_capability_is_sent_for_the_labelled_families_only_when_configured() -> None:
    """Unmarked: the knob.  Off, the OPEN is what it always was; on, one triple per
    labelled family, none for a family without labels."""
    assert not neighbour_capabilities('').announced(MULTIPLE_LABELS)
    sent = neighbour_capabilities('multiple-labels 3;')
    assert dict(sent[MULTIPLE_LABELS]) == {LABELLED_UNICAST: 3}


@pytest.mark.rfc('rfc8277#2.1-capability-supports-two-labels')
def test_a_session_which_sent_the_capability_decodes_a_two_label_stack() -> None:
    """What we promise by sending code 8: a peer may then bind two labels to a prefix."""
    negotiated = session(triple(2), triple(2))
    nlri, rest = decode(labelled(label(100, bottom=False) + label(200)))
    assert rest == b''
    assert cast(LabelBase, nlri).labels.labels == [100, 200]
    assert negotiated.labels_limit(*LABELLED_UNICAST) == 2
