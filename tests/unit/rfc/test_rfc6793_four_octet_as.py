"""RFC 6793, BGP Support for Four-Octet Autonomous System (AS) Number Space.

The ledger these tests are joined to is qa/rfc/rfc6793.toml.

The document has two halves. Generating updates for a two-octet peer is arithmetic exabgp
gets right: AS_TRANS in the AS_PATH, AS4_PATH beside it with no confederation segment in
it, and neither of them when every AS number is mappable. Reading updates back is the half
which took the longest to get right, and the xfail markers left below are all on it.

Everything drives the real attribute parser: wire bytes into AttributeCollection.unpack,
or a real ASPath and Aggregator into pack_attribute against a real Negotiated.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.open.capability import ASN4, Capabilities, Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.aspath import (
    CONFED_SEQUENCE,
    SEQUENCE,
    SET,
    ASPath,
)
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IPv4
from exabgp.util.enumeration import TriState

TRANSITIVE = Attribute.Flag.TRANSITIVE
OPTIONAL_TRANSITIVE = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

# 100000 and 200000 need four octets. 65001 and 65010 are mappable: their two high order
# octets are zero, so they survive a trip through a two-octet AS_PATH unharmed.
NON_MAPPABLE = ASN(100000)
ALSO_NON_MAPPABLE = ASN(200000)
MAPPABLE = ASN(65001)
ALSO_MAPPABLE = ASN(65010)

SPEAKER = IPv4.from_string('192.0.2.1')


def session(asn4: bool, direction: Direction = Direction.IN) -> Negotiated:
    """A session where four-octet support was, or was not, negotiated by both ends."""
    negotiated = Negotiated.make_negotiated(Neighbor(), direction)
    negotiated.local_as = ASN(65001)
    negotiated.peer_as = ASN(65002)
    negotiated.asn4 = asn4
    negotiated.families = [(AFI.ipv4, SAFI.unicast)]
    return negotiated


def negotiate(local: int, my_autonomous_system: int, capability_as: int | None) -> Negotiated:
    """Run the real OPEN negotiation, so peer_as is decided by negotiated.py not by us."""
    neighbor = Neighbor()
    neighbor.session.local_as = ASN(local)
    sent = Capabilities()
    sent[Capability.CODE.FOUR_BYTES_ASN] = ASN4(local)
    received = Capabilities()
    if capability_as is not None:
        received[Capability.CODE.FOUR_BYTES_ASN] = ASN4(capability_as)
    negotiated = Negotiated(neighbor, Direction.IN)
    negotiated.sent(Open.make_open(Version(4), ASN(local).trans(), HoldTime(90), RouterID('192.0.2.1'), sent))
    negotiated.received(
        Open.make_open(Version(4), ASN(my_autonomous_system), HoldTime(90), RouterID('192.0.2.2'), received)
    )
    return negotiated


def advertised_asn(capabilities: Capabilities) -> int:
    """The AS number in the four-octet capability, narrowed for the type checker."""
    capability = capabilities[Capability.CODE.FOUR_BYTES_ASN]
    assert isinstance(capability, ASN4), 'the four-octet capability decoded to something else'
    return int(capability)


def attribute(code: int, flag: int, payload: bytes) -> bytes:
    """One path attribute, in the non-extended encoding."""
    assert len(payload) < 256, 'the tests here stay inside the one octet length form'
    return bytes([flag, code, len(payload)]) + payload


def segment(segment_type: int, asns: list[ASN], octets: int) -> bytes:
    """One AS path segment, packed with two or four octet AS numbers."""
    packer = '!L' if octets == 4 else '!H'
    return bytes([segment_type, len(asns)]) + b''.join(pack(packer, int(asn)) for asn in asns)


def as_path(asns: list[ASN], octets: int) -> bytes:
    return attribute(Attribute.CODE.AS_PATH, TRANSITIVE, segment(SEQUENCE.ID, asns, octets))


def as4_path(payload: bytes) -> bytes:
    return attribute(Attribute.CODE.AS4_PATH, OPTIONAL_TRANSITIVE, payload)


def aggregator(asn: int, octets: int) -> bytes:
    packer = '!L' if octets == 4 else '!H'
    return attribute(Attribute.CODE.AGGREGATOR, OPTIONAL_TRANSITIVE, pack(packer, asn) + SPEAKER.pack_ip())


def as4_aggregator(payload: bytes) -> bytes:
    return attribute(Attribute.CODE.AS4_AGGREGATOR, OPTIONAL_TRANSITIVE, payload)


def parse(wire: bytes, asn4: bool = False) -> AttributeCollection:
    return AttributeCollection.unpack(wire, session(asn4))


def path_of(attributes: AttributeCollection) -> ASPath:
    decoded = attributes[Attribute.CODE.AS_PATH]
    assert isinstance(decoded, ASPath), 'the AS_PATH did not decode to an AS path'
    return decoded


def counted(path: ASPath) -> int:
    """The number of AS numbers in a path, by the rule of RFC 4271 section 9.1.2.2.

    An AS_SET counts as one however many members it holds, and a confederation segment
    counts as none. RFC 6793 section 4.2.3 names this count twice, so the reconstruction
    tests have to use it rather than a plain len().
    """
    total = 0
    for content in path.aspath:
        if isinstance(content, SET):
            total += 1
        elif isinstance(content, SEQUENCE):
            total += len(content)
    return total


def malformed_marked(attributes: AttributeCollection) -> bool:
    """True when the parser decided an attribute in this UPDATE was malformed."""
    return Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in attributes or Attribute.CODE.INTERNAL_DISCARD in attributes


def attributes_of(packed: bytes) -> list[int]:
    """The attribute codes present in a run of packed attributes, in order."""
    codes: list[int] = []
    offset = 0
    while offset < len(packed):
        codes.append(packed[offset + 1])
        offset += 3 + packed[offset + 2]
    return codes


# =========================================================== 4.1, the capability


@pytest.mark.rfc('rfc6793#4.1-advertise-the-capability')
def test_a_speaker_supporting_four_octet_as_numbers_advertises_it() -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ALSO_NON_MAPPABLE
    neighbor.capability.asn4 = TriState.TRUE

    capabilities = Capabilities.unpack(Capabilities().new(neighbor, False).pack_capabilities())

    assert Capability.CODE.FOUR_BYTES_ASN in capabilities


@pytest.mark.rfc('rfc6793#4.1-advertise-the-capability', polarity='negative')
def test_a_speaker_which_declines_four_octet_support_does_not_advertise_it() -> None:
    """And it may not then hold an AS number it could not encode: that is refused outright."""
    neighbor = Neighbor()
    neighbor.session.local_as = MAPPABLE
    neighbor.capability.asn4 = TriState.FALSE

    capabilities = Capabilities.unpack(Capabilities().new(neighbor, False).pack_capabilities())
    assert Capability.CODE.FOUR_BYTES_ASN not in capabilities

    four_octet = Neighbor()
    four_octet.session.local_as = ALSO_NON_MAPPABLE
    four_octet.capability.asn4 = TriState.FALSE
    with pytest.raises(ValueError):
        Capabilities().new(four_octet, False)


@pytest.mark.rfc('rfc6793#4.1-capability-value-carries-the-as-number')
def test_the_capability_value_is_our_as_number_in_four_octets() -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ALSO_NON_MAPPABLE
    neighbor.capability.asn4 = TriState.TRUE

    packed = Capabilities().new(neighbor, False)[Capability.CODE.FOUR_BYTES_ASN].extract_capability_bytes()

    assert packed == [pack('!L', int(ALSO_NON_MAPPABLE))]
    decoded = Capabilities.unpack(Capabilities().new(neighbor, False).pack_capabilities())
    assert advertised_asn(decoded) == int(ALSO_NON_MAPPABLE)


@pytest.mark.rfc('rfc6793#4.1-capability-value-carries-the-as-number', polarity='negative')
@pytest.mark.parametrize('length', [0, 1, 3, 5, 8], ids=['empty', 'one', 'three', 'five', 'eight'])
def test_a_capability_value_which_cannot_be_an_as_number_is_refused(length: int) -> None:
    """Reading an AS number out of the wrong number of octets invents a peer identity."""
    body = bytes([Capability.CODE.FOUR_BYTES_ASN, length]) + bytes(length)
    parameter = bytes([2, len(body)]) + body

    with pytest.raises(Notify):
        Capabilities.unpack(bytes([len(parameter)]) + parameter)


@pytest.mark.rfc('rfc6793#4.1-capability-value-in-lieu-of-my-as')
def test_the_capability_value_is_used_when_my_as_is_as_trans() -> None:
    """The case the RFC was written for: a four-octet peer with no two-octet number."""
    negotiated = negotiate(local=65001, my_autonomous_system=int(AS_TRANS), capability_as=int(ALSO_NON_MAPPABLE))

    assert negotiated.peer_as == ALSO_NON_MAPPABLE


@pytest.mark.rfc('rfc6793#4.1-capability-value-in-lieu-of-my-as', polarity='negative')
@pytest.mark.xfail(
    strict=True,
    reason='negotiated.py substitutes the capability value only when My Autonomous System is AS_TRANS, so a peer whose two fields disagree is taken at its two-octet word',
)
def test_the_capability_value_wins_when_my_as_disagrees_with_it() -> None:
    """ "In lieu of" has no condition on it. Where the two fields differ, the capability rules."""
    negotiated = negotiate(local=65001, my_autonomous_system=65002, capability_as=int(ALSO_NON_MAPPABLE))

    assert negotiated.peer_as == ALSO_NON_MAPPABLE, f'we took the My Autonomous System field, {negotiated.peer_as}'


@pytest.mark.rfc('rfc6793#4.1-four-octet-encoding-in-both-directions')
def test_four_octet_entities_are_sent_and_assumed_on_a_negotiated_session() -> None:
    new = session(True, Direction.OUT)
    path = ASPath.make_aspath([SEQUENCE([NON_MAPPABLE, MAPPABLE])], asn4=True)

    packed = path.pack_attribute(new)
    assert attributes_of(packed) == [Attribute.CODE.AS_PATH], 'a four-octet session needs nothing beside AS_PATH'
    assert packed[3:] == segment(SEQUENCE.ID, [NON_MAPPABLE, MAPPABLE], 4)

    aggregated = Aggregator.make_aggregator(ALSO_NON_MAPPABLE, SPEAKER).pack_attribute(new)
    assert attributes_of(aggregated) == [Attribute.CODE.AGGREGATOR]
    assert aggregated[3:] == pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip()

    read = parse(packed + aggregated, asn4=True)
    assert [int(asn) for asn in path_of(read).as_seq] == [int(NON_MAPPABLE), int(MAPPABLE)]
    received = read[Attribute.CODE.AGGREGATOR]
    assert isinstance(received, Aggregator) and received.asn == ALSO_NON_MAPPABLE


@pytest.mark.rfc('rfc6793#4.1-four-octet-encoding-in-both-directions', polarity='negative')
def test_two_octet_entities_are_assumed_when_the_capability_was_not_exchanged() -> None:
    """Assuming four octets everywhere would read one peer's path as another's."""
    read = parse(as_path([MAPPABLE, ALSO_MAPPABLE], 2) + aggregator(int(ALSO_MAPPABLE), 2), asn4=False)

    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), int(ALSO_MAPPABLE)]
    received = read[Attribute.CODE.AGGREGATOR]
    assert isinstance(received, Aggregator) and received.asn == ALSO_MAPPABLE


@pytest.mark.rfc('rfc6793#4.1-no-as4-attributes-between-new-speakers')
def test_we_send_no_as4_attributes_to_a_four_octet_peer() -> None:
    new = session(True, Direction.OUT)

    path = ASPath.make_aspath([SEQUENCE([NON_MAPPABLE, MAPPABLE])], asn4=True).pack_attribute(new)
    aggregated = Aggregator.make_aggregator(ALSO_NON_MAPPABLE, SPEAKER).pack_attribute(new)

    codes = attributes_of(path) + attributes_of(aggregated)
    assert Attribute.CODE.AS4_PATH not in codes, 'we sent AS4_PATH to a NEW speaker'
    assert Attribute.CODE.AS4_AGGREGATOR not in codes, 'we sent AS4_AGGREGATOR to a NEW speaker'


@pytest.mark.rfc('rfc6793#4.1-discard-as4-from-a-new-speaker')
def test_as4_attributes_from_a_four_octet_peer_are_discarded() -> None:
    wire = (
        as_path([MAPPABLE, ASN(65002)], 4)
        + as4_path(segment(SEQUENCE.ID, [NON_MAPPABLE], 4))
        + as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip())
    )

    read = parse(wire, asn4=True)

    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), 65002], 'the AS4_PATH rewrote the AS path'
    assert Attribute.CODE.AS4_AGGREGATOR not in read, 'the AS4_AGGREGATOR was kept'


@pytest.mark.rfc('rfc6793#4.1-discard-as4-from-a-new-speaker', polarity='negative')
def test_as4_attributes_from_a_four_octet_peer_do_not_cost_the_update() -> None:
    """Discard, not withdraw: the rest of the UPDATE must survive them."""
    wire = (
        attribute(Attribute.CODE.ORIGIN, TRANSITIVE, bytes([0]))
        + as_path([MAPPABLE, ASN(65002)], 4)
        + as4_path(segment(SEQUENCE.ID, [NON_MAPPABLE], 4))
    )

    read = parse(wire, asn4=True)

    assert not malformed_marked(read), 'the UPDATE was withdrawn over an attribute the RFC says to drop'
    assert Attribute.CODE.ORIGIN in read, 'processing did not continue past the AS4_PATH'


# =========================================================== 4.2.1, AS_TRANS in the OPEN


@pytest.mark.rfc('rfc6793#4.2.1-as-trans-without-a-two-octet-as')
def test_our_open_carries_as_trans_when_our_as_needs_four_octets() -> None:
    neighbor = Neighbor()
    neighbor.session.local_as = ALSO_NON_MAPPABLE
    neighbor.capability.asn4 = TriState.TRUE
    capabilities = Capabilities().new(neighbor, False)
    message = Open.make_open(
        Version(4), ALSO_NON_MAPPABLE.trans(), HoldTime(90), RouterID('192.0.2.1'), capabilities
    ).pack_message(Negotiated.UNSET)

    decoded = Open.unpack_message(message[19:], Negotiated.UNSET)

    assert decoded.asn == AS_TRANS, 'a four-octet AS number was written into My Autonomous System'
    assert advertised_asn(decoded.capabilities) == int(ALSO_NON_MAPPABLE)


@pytest.mark.rfc('rfc6793#4.2.1-as-trans-without-a-two-octet-as', polarity='negative')
def test_our_open_carries_our_own_as_when_it_fits_in_two_octets() -> None:
    """AS_TRANS is not a default. A speaker which owns a two-octet number must use it."""
    neighbor = Neighbor()
    neighbor.session.local_as = MAPPABLE
    neighbor.capability.asn4 = TriState.TRUE
    capabilities = Capabilities().new(neighbor, False)
    message = Open.make_open(
        Version(4), MAPPABLE.trans(), HoldTime(90), RouterID('192.0.2.1'), capabilities
    ).pack_message(Negotiated.UNSET)

    decoded = Open.unpack_message(message[19:], Negotiated.UNSET)

    assert decoded.asn == MAPPABLE, 'we hid a perfectly good two-octet AS number behind AS_TRANS'


# =========================================================== 4.2.2, generating updates


@pytest.mark.rfc('rfc6793#4.2.2-as-path-two-octet-to-an-old-speaker')
def test_the_as_path_we_send_an_old_speaker_is_two_octet_with_as_trans() -> None:
    old = session(False, Direction.OUT)
    path = ASPath.make_aspath([SEQUENCE([NON_MAPPABLE, MAPPABLE])], asn4=True)

    packed = path.pack_attribute(old)

    length = packed[2]
    assert packed[3 : 3 + length] == segment(SEQUENCE.ID, [AS_TRANS, MAPPABLE], 2), (
        'the AS_PATH sent to a two-octet peer was not two-octet with AS_TRANS in it'
    )


@pytest.mark.rfc('rfc6793#4.2.2-as-path-two-octet-to-an-old-speaker', polarity='negative')
def test_we_do_not_downgrade_the_as_path_for_a_four_octet_speaker() -> None:
    """A peer which asked for four octets must not be handed AS_TRANS and a lossy path."""
    new = session(True, Direction.OUT)
    path = ASPath.make_aspath([SEQUENCE([NON_MAPPABLE, MAPPABLE])], asn4=True)

    packed = path.pack_attribute(new)

    assert packed[3:] == segment(SEQUENCE.ID, [NON_MAPPABLE, MAPPABLE], 4)
    assert pack('!H', int(AS_TRANS)) not in packed[3:], 'AS_TRANS was sent to a four-octet peer'


@pytest.mark.rfc('rfc6793#4.2.2-as4-path-unless-all-mappable')
def test_a_non_mappable_as_number_brings_an_as4_path_with_it() -> None:
    old = session(False, Direction.OUT)
    path = ASPath.make_aspath([SEQUENCE([NON_MAPPABLE, MAPPABLE])], asn4=True)

    packed = path.pack_attribute(old)

    assert attributes_of(packed) == [Attribute.CODE.AS_PATH, Attribute.CODE.AS4_PATH]
    as4_value = packed[3 + packed[2] + 3 :]
    assert as4_value == segment(SEQUENCE.ID, [NON_MAPPABLE, MAPPABLE], 4), (
        'the AS4_PATH did not carry the real AS numbers in four octets'
    )


@pytest.mark.rfc('rfc6793#4.2.2-as4-path-unless-all-mappable', polarity='negative')
def test_a_path_of_mappable_as_numbers_carries_no_as4_path() -> None:
    """The half which finds bugs: always sending AS4_PATH passes the positive test."""
    old = session(False, Direction.OUT)
    path = ASPath.make_aspath([SEQUENCE([MAPPABLE, ALSO_MAPPABLE])], asn4=True)

    packed = path.pack_attribute(old)

    assert attributes_of(packed) == [Attribute.CODE.AS_PATH], 'AS4_PATH was sent for an all-mappable path'


@pytest.mark.rfc('rfc6793#4.2.2-exclude-confed-segments-from-as4-path')
def test_confederation_segments_are_left_out_of_the_as4_path_we_build() -> None:
    old = session(False, Direction.OUT)
    path = ASPath.make_aspath([CONFED_SEQUENCE([ALSO_MAPPABLE]), SEQUENCE([NON_MAPPABLE])], asn4=True)

    packed = path.pack_attribute(old)

    as4_value = packed[3 + packed[2] + 3 :]
    assert as4_value == segment(SEQUENCE.ID, [NON_MAPPABLE], 4), (
        f'the AS4_PATH we built is not the path with its confederation segments removed: {as4_value.hex()}'
    )


@pytest.mark.rfc('rfc6793#4.2.2-exclude-confed-segments-from-as4-path', polarity='negative')
def test_a_path_without_confederation_segments_keeps_all_of_them() -> None:
    """Excluding confederation segments must not turn into excluding anything else."""
    old = session(False, Direction.OUT)
    path = ASPath.make_aspath([SEQUENCE([NON_MAPPABLE]), SET([MAPPABLE])], asn4=True)

    packed = path.pack_attribute(old)

    assert segment(SEQUENCE.ID, [NON_MAPPABLE], 4) in packed
    assert segment(SET.ID, [MAPPABLE], 4) in packed


@pytest.mark.rfc('rfc6793#4.2.2-as4-aggregator-for-a-non-mappable-as')
def test_a_non_mappable_aggregator_becomes_as_trans_plus_as4_aggregator() -> None:
    old = session(False, Direction.OUT)

    packed = Aggregator.make_aggregator(ALSO_NON_MAPPABLE, SPEAKER).pack_attribute(old)

    assert attributes_of(packed) == [Attribute.CODE.AGGREGATOR, Attribute.CODE.AS4_AGGREGATOR]
    assert packed[3:9] == pack('!H', int(AS_TRANS)) + SPEAKER.pack_ip()
    assert packed[12:] == pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip()


@pytest.mark.rfc('rfc6793#4.2.2-as4-aggregator-for-a-non-mappable-as', polarity='negative')
def test_a_four_octet_peer_gets_the_real_aggregator_and_no_as_trans() -> None:
    new = session(True, Direction.OUT)

    packed = Aggregator.make_aggregator(ALSO_NON_MAPPABLE, SPEAKER).pack_attribute(new)

    assert attributes_of(packed) == [Attribute.CODE.AGGREGATOR]
    assert packed[3:] == pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip()


@pytest.mark.rfc('rfc6793#4.2.2-no-as4-aggregator-for-a-mappable-as')
def test_a_mappable_aggregator_sends_no_as4_aggregator() -> None:
    old = session(False, Direction.OUT)

    packed = Aggregator.make_aggregator(ALSO_MAPPABLE, SPEAKER).pack_attribute(old)

    assert attributes_of(packed) == [Attribute.CODE.AGGREGATOR]
    assert packed[3:] == pack('!H', int(ALSO_MAPPABLE)) + SPEAKER.pack_ip()


@pytest.mark.rfc('rfc6793#4.2.2-no-as4-aggregator-for-a-mappable-as', polarity='negative')
def test_the_as4_aggregator_is_still_sent_when_the_as_is_not_mappable() -> None:
    """Never sending it would satisfy the MUST NOT and lose the aggregating AS number."""
    old = session(False, Direction.OUT)

    packed = Aggregator.make_aggregator(NON_MAPPABLE, SPEAKER).pack_attribute(old)

    assert Attribute.CODE.AS4_AGGREGATOR in attributes_of(packed)


# =========================================================== 4.2.3, processing updates


@pytest.mark.rfc('rfc6793#4.2.3-be-ready-for-as4-path')
def test_an_as4_path_beside_an_as_path_is_accepted_and_used() -> None:
    wire = as_path([MAPPABLE, AS_TRANS, AS_TRANS], 2) + as4_path(
        segment(SEQUENCE.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4)
    )

    read = parse(wire)

    assert not malformed_marked(read), 'an AS4_PATH the RFC says to expect was refused'
    assert [int(asn) for asn in path_of(read).as_seq] == [
        int(MAPPABLE),
        int(NON_MAPPABLE),
        int(ALSO_NON_MAPPABLE),
    ]


@pytest.mark.rfc('rfc6793#4.2.3-be-ready-for-as4-path', polarity='negative')
def test_an_as_path_arriving_alone_is_left_exactly_as_it_came() -> None:
    """Being ready for an AS4_PATH must not mean acting as if one always arrived."""
    read = parse(as_path([MAPPABLE, ALSO_MAPPABLE], 2))

    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), int(ALSO_MAPPABLE)]
    assert Attribute.CODE.AS4_PATH not in read


@pytest.mark.rfc('rfc6793#4.2.3-be-ready-for-as4-aggregator')
def test_an_as4_aggregator_beside_an_aggregator_is_accepted() -> None:
    wire = aggregator(int(AS_TRANS), 2) + as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip())

    read = parse(wire)

    assert not malformed_marked(read), 'an AS4_AGGREGATOR the RFC says to expect was refused'
    received = read[Attribute.CODE.AS4_AGGREGATOR]
    assert isinstance(received, Aggregator) and received.asn == ALSO_NON_MAPPABLE


@pytest.mark.rfc('rfc6793#4.2.3-be-ready-for-as4-aggregator', polarity='negative')
def test_an_aggregator_arriving_alone_gains_no_as4_aggregator() -> None:
    read = parse(aggregator(int(ALSO_MAPPABLE), 2))

    assert Attribute.CODE.AS4_AGGREGATOR not in read, 'an AS4_AGGREGATOR nobody sent was invented'
    received = read[Attribute.CODE.AGGREGATOR]
    assert isinstance(received, Aggregator) and received.asn == ALSO_MAPPABLE


@pytest.mark.rfc('rfc6793#4.2.3-aggregator-not-as-trans')
def test_a_real_aggregator_as_makes_both_as4_attributes_ignored() -> None:
    wire = (
        as_path([MAPPABLE, AS_TRANS], 2)
        + as4_path(segment(SEQUENCE.ID, [NON_MAPPABLE], 4))
        + aggregator(int(ALSO_MAPPABLE), 2)
        + as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip())
    )

    read = parse(wire)

    assert Attribute.CODE.AS4_AGGREGATOR not in read, 'the AS4_AGGREGATOR was not ignored'
    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), int(AS_TRANS)], 'the AS4_PATH was not ignored'


@pytest.mark.rfc('rfc6793#4.2.3-aggregator-not-as-trans', polarity='negative')
def test_a_real_aggregator_as_is_the_one_we_report() -> None:
    """The second bullet, and the one exabgp does honour: AGGREGATOR is taken as it came."""
    wire = aggregator(int(ALSO_MAPPABLE), 2) + as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip())

    read = parse(wire)

    received = read[Attribute.CODE.AGGREGATOR]
    assert isinstance(received, Aggregator) and received.asn == ALSO_MAPPABLE


@pytest.mark.rfc('rfc6793#4.2.3-aggregator-is-as-trans')
def test_an_as_trans_aggregator_is_ignored_in_favour_of_the_as4_one() -> None:
    wire = aggregator(int(AS_TRANS), 2) + as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip())

    read = parse(wire)

    assert Attribute.CODE.AGGREGATOR not in read, 'AS_TRANS is a placeholder, not an aggregating node'


@pytest.mark.rfc('rfc6793#4.2.3-aggregator-is-as-trans', polarity='negative')
def test_the_as4_aggregator_keeps_the_as_number_the_peer_sent() -> None:
    """Whatever we do with the pair, the four-octet AS number must not be altered."""
    wire = aggregator(int(AS_TRANS), 2) + as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip())

    read = parse(wire)

    received = read[Attribute.CODE.AS4_AGGREGATOR]
    assert isinstance(received, Aggregator) and received.asn == ALSO_NON_MAPPABLE
    assert str(received.speaker) == '192.0.2.1'


@pytest.mark.rfc('rfc6793#4.2.3-ignore-as4-path-when-as-path-is-shorter')
def test_a_longer_as4_path_than_as_path_is_ignored() -> None:
    """An AS4_PATH longer than the AS_PATH cannot be a suffix of it, so it is nonsense."""
    wire = as_path([MAPPABLE, AS_TRANS], 2) + as4_path(
        segment(SEQUENCE.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE, ASN(300000)], 4)
    )

    read = parse(wire)

    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), int(AS_TRANS)]


@pytest.mark.rfc('rfc6793#4.2.3-ignore-as4-path-when-as-path-is-shorter', polarity='negative')
def test_an_as4_path_no_longer_than_the_as_path_is_not_ignored() -> None:
    """Ignoring it always would pass the positive test and lose every four-octet AS number."""
    wire = as_path([MAPPABLE, AS_TRANS], 2) + as4_path(segment(SEQUENCE.ID, [NON_MAPPABLE], 4))

    read = parse(wire)

    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), int(NON_MAPPABLE)]


def reconstruction_cases() -> list[tuple[str, bytes, bytes, int]]:
    """AS_PATH, AS4_PATH and the AS number count the reconstruction has to end up with."""
    return [
        (
            'a sequence shorter than the AS_PATH',
            segment(SEQUENCE.ID, [MAPPABLE, AS_TRANS, AS_TRANS], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
            3,
        ),
        (
            'a sequence as long as the AS_PATH',
            segment(SEQUENCE.ID, [AS_TRANS, AS_TRANS], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
            2,
        ),
        (
            'an AS4_PATH holding only a set',
            segment(SEQUENCE.ID, [MAPPABLE, AS_TRANS], 2),
            segment(SET.ID, [NON_MAPPABLE], 4),
            2,
        ),
        (
            'an AS4_PATH holding a set after a sequence',
            segment(SEQUENCE.ID, [MAPPABLE, AS_TRANS, AS_TRANS], 2) + segment(SET.ID, [ALSO_MAPPABLE], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE], 4) + segment(SET.ID, [ALSO_NON_MAPPABLE], 4),
            4,
        ),
        (
            'an AS4_PATH holding a set of two, which is one AS number and not two',
            segment(SEQUENCE.ID, [MAPPABLE, AS_TRANS], 2),
            segment(SET.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
            2,
        ),
    ]


@pytest.mark.rfc('rfc6793#4.2.3-construct-by-prepending')
def test_the_reconstructed_path_has_as_many_as_numbers_as_the_as_path() -> None:
    """One test over every shape, because the rule names one number and it is this one."""
    wrong: list[str] = []

    for what, two_octet, four_octet, expected in reconstruction_cases():
        read = parse(attribute(Attribute.CODE.AS_PATH, TRANSITIVE, two_octet) + as4_path(four_octet))
        count = counted(path_of(read))
        if count != expected:
            wrong.append(f'{what}: {count} AS numbers where the AS_PATH had {expected} ({path_of(read).string()})')

    assert not wrong, 'the reconstruction changed the length of the path for ' + '; '.join(wrong)


@pytest.mark.rfc('rfc6793#4.2.3-construct-by-prepending', polarity='negative')
def test_the_reconstruction_never_makes_the_path_longer_than_the_as_path() -> None:
    """A peer must not be able to lengthen its own path by what it puts in AS4_PATH."""
    for what, two_octet, four_octet, expected in reconstruction_cases():
        read = parse(attribute(Attribute.CODE.AS_PATH, TRANSITIVE, two_octet) + as4_path(four_octet))
        assert counted(path_of(read)) <= expected, f'{what} produced a path longer than the AS_PATH'


# =========================================================== 6, error handling


@pytest.mark.rfc('rfc6793#6-no-confed-segments-in-as4-path')
def test_no_as4_path_we_send_carries_a_confederation_segment() -> None:
    old = session(False, Direction.OUT)
    path = ASPath.make_aspath([CONFED_SEQUENCE([ALSO_MAPPABLE]), SEQUENCE([NON_MAPPABLE])], asn4=True)

    packed = path.pack_attribute(old)

    as4_offset = 3 + packed[2]
    body = packed[as4_offset + 3 :]
    assert body[0] not in (CONFED_SEQUENCE.ID, 0x04), f'a confederation segment went out in an AS4_PATH: {body.hex()}'


@pytest.mark.rfc('rfc6793#6-discard-confed-segments-from-as4-path')
def test_confederation_segments_in_a_received_as4_path_are_discarded() -> None:
    wire = as_path([MAPPABLE, AS_TRANS], 2) + as4_path(
        segment(CONFED_SEQUENCE.ID, [ALSO_MAPPABLE], 4) + segment(SEQUENCE.ID, [NON_MAPPABLE], 4)
    )

    read = parse(wire)

    assert int(ALSO_MAPPABLE) not in [int(asn) for asn in path_of(read).as_seq], (
        f'a confederation AS number reached the path we publish: {path_of(read).string()}'
    )


@pytest.mark.rfc('rfc6793#6-discard-confed-segments-from-as4-path', polarity='negative')
def test_an_as4_path_without_confederation_segments_is_processed_whole() -> None:
    """Discarding those segments must not become discarding the attribute."""
    wire = as_path([MAPPABLE, AS_TRANS], 2) + as4_path(segment(SEQUENCE.ID, [NON_MAPPABLE], 4))

    read = parse(wire)

    assert not malformed_marked(read)
    assert int(NON_MAPPABLE) in [int(asn) for asn in path_of(read).as_seq]


def malformed_as4_paths() -> list[tuple[str, bytes]]:
    """One AS4_PATH value per condition section 6 lists as making it malformed."""
    return [
        ('a length below six, too small for one AS number', bytes([SEQUENCE.ID, 1]) + b'\x00\x00'),
        ('a length which is not a multiple of two', bytes([SEQUENCE.ID, 1]) + b'\x00\x00\x00'),
        ('a path segment length of zero', bytes([SEQUENCE.ID, 0])),
        (
            'a path segment length inconsistent with the attribute length',
            bytes([SEQUENCE.ID, 4]) + pack('!L', int(NON_MAPPABLE)),
        ),
        ('a path segment type which is not defined', bytes([9, 1]) + pack('!L', int(NON_MAPPABLE))),
    ]


@pytest.mark.rfc('rfc6793#6-as4-path-malformed-conditions')
def test_each_condition_the_section_lists_makes_the_as4_path_malformed() -> None:
    accepted: list[str] = []

    for what, payload in malformed_as4_paths():
        read = parse(as_path([MAPPABLE], 2) + as4_path(payload))
        if not malformed_marked(read):
            accepted.append(what)

    assert not accepted, 'an AS4_PATH the section calls malformed was accepted: ' + '; '.join(accepted)


@pytest.mark.rfc('rfc6793#6-as4-path-malformed-conditions', polarity='negative')
def test_a_well_formed_as4_path_is_not_called_malformed() -> None:
    """Calling everything malformed would satisfy the conditions and lose every path."""
    for payload in (
        segment(SEQUENCE.ID, [NON_MAPPABLE], 4),
        segment(SET.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
        segment(SEQUENCE.ID, [NON_MAPPABLE], 4) + segment(SET.ID, [ALSO_NON_MAPPABLE], 4),
    ):
        read = parse(as_path([MAPPABLE, AS_TRANS], 2) + as4_path(payload))
        assert not malformed_marked(read), f'a well formed AS4_PATH was refused: {payload.hex()}'


@pytest.mark.rfc('rfc6793#6-discard-a-malformed-as4-path')
def test_a_malformed_as4_path_is_dropped_and_the_update_goes_on() -> None:
    """Section 6 picked attribute discard on purpose: the AS_PATH is still good."""
    wire = (
        attribute(Attribute.CODE.ORIGIN, TRANSITIVE, bytes([0]))
        + as_path([MAPPABLE, ALSO_MAPPABLE], 2)
        + as4_path(bytes([9, 1]) + pack('!L', int(NON_MAPPABLE)))
    )

    read = parse(wire)

    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in read, 'the whole UPDATE was withdrawn'
    assert Attribute.CODE.ORIGIN in read, 'processing did not continue past the malformed attribute'
    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), int(ALSO_MAPPABLE)]


@pytest.mark.rfc('rfc6793#6-discard-a-malformed-as4-path', polarity='negative')
def test_a_well_formed_as4_path_is_not_discarded() -> None:
    wire = as_path([MAPPABLE, AS_TRANS], 2) + as4_path(segment(SEQUENCE.ID, [NON_MAPPABLE], 4))

    read = parse(wire)

    assert int(NON_MAPPABLE) in [int(asn) for asn in path_of(read).as_seq], 'a good AS4_PATH was thrown away'


@pytest.mark.rfc('rfc6793#6-as4-aggregator-malformed-length')
@pytest.mark.parametrize('length', [0, 4, 6, 7, 9, 12], ids=['0', '4', '6', '7', '9', '12'])
def test_an_as4_aggregator_of_any_length_but_eight_is_malformed(length: int) -> None:
    read = parse(attribute(Attribute.CODE.ORIGIN, TRANSITIVE, bytes([0])) + as4_aggregator(bytes(length)))

    assert Attribute.CODE.AS4_AGGREGATOR not in read, f'an AS4_AGGREGATOR of {length} octets was accepted'


@pytest.mark.rfc('rfc6793#6-as4-aggregator-malformed-length', polarity='negative')
def test_an_as4_aggregator_of_eight_octets_is_not_malformed() -> None:
    """Calling every length malformed would satisfy the SHALL and drop every aggregator."""
    read = parse(as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip()))

    received = read[Attribute.CODE.AS4_AGGREGATOR]
    assert isinstance(received, Aggregator) and received.asn == ALSO_NON_MAPPABLE


@pytest.mark.rfc('rfc6793#6-discard-a-malformed-as4-aggregator')
def test_a_malformed_as4_aggregator_is_dropped_and_the_update_goes_on() -> None:
    wire = (
        attribute(Attribute.CODE.ORIGIN, TRANSITIVE, bytes([0]))
        + as_path([MAPPABLE, ALSO_MAPPABLE], 2)
        + as4_aggregator(pack('!H', int(ALSO_MAPPABLE)) + SPEAKER.pack_ip())
    )

    read = parse(wire)

    assert Attribute.CODE.AS4_AGGREGATOR not in read, 'the malformed attribute was kept'
    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW not in read, 'the whole UPDATE was withdrawn'
    assert Attribute.CODE.ORIGIN in read, 'processing did not continue past the malformed attribute'
    assert [int(asn) for asn in path_of(read).as_seq] == [int(MAPPABLE), int(ALSO_MAPPABLE)]


@pytest.mark.rfc('rfc6793#6-discard-a-malformed-as4-aggregator', polarity='negative')
def test_a_well_formed_as4_aggregator_is_not_discarded() -> None:
    read = parse(
        attribute(Attribute.CODE.ORIGIN, TRANSITIVE, bytes([0]))
        + as4_aggregator(pack('!L', int(ALSO_NON_MAPPABLE)) + SPEAKER.pack_ip())
    )

    assert Attribute.CODE.AS4_AGGREGATOR in read, 'a good AS4_AGGREGATOR was discarded'
    assert Attribute.CODE.INTERNAL_DISCARD not in read


@pytest.mark.rfc('rfc6793#4.2.3-construct-by-prepending')
def test_an_as_set_counts_as_one_however_many_members_it_holds() -> None:
    """The counting rule of RFC 4271 9.1.2.2, which decides how much leading part to keep.

    Counting the members instead would make this AS4_PATH two AS numbers long, as long as
    the AS_PATH, and nothing of the AS_PATH would be prepended: AS 65001 would be deleted
    from a path it really is on. The length test above catches the count; this one names
    the AS number the count decides the fate of.
    """
    read = parse(
        attribute(Attribute.CODE.AS_PATH, TRANSITIVE, segment(SEQUENCE.ID, [MAPPABLE, AS_TRANS], 2))
        + as4_path(segment(SET.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4))
    )

    path = path_of(read)
    assert [int(asn) for asn in path.as_seq] == [int(MAPPABLE)], (
        f'the leading part of the AS_PATH was not kept: {path.string()}'
    )
    assert sorted(int(asn) for asn in path.as_set) == [int(NON_MAPPABLE), int(ALSO_NON_MAPPABLE)]


@pytest.mark.rfc('rfc6793#4.2.3-construct-by-prepending')
def test_an_as4_path_holding_only_a_set_still_replaces_the_as_trans() -> None:
    """Right length is not the point of the rule, it is the test for having followed it.

    AS_TRANS is the placeholder a two octet speaker writes where a four octet ASN was,
    and the AS4_PATH is how the real number travels beside it. A reconstruction which
    ends up the right length but leaves AS_TRANS in place has published 23456 as a
    transit AS, which is the one outcome the whole mechanism exists to avoid.

    Fixing the length bug did not fix this: the merge takes sequences from sequences and
    sets from sets, so an AS4_PATH whose only segment is a set is matched against an
    AS_PATH which has no set, and contributes nothing. RFC 6793 4.2.3 counts AS numbers
    over the whole path and prepends across segment kinds, which this shape cannot do.
    """
    read = parse(
        attribute(Attribute.CODE.AS_PATH, TRANSITIVE, segment(SEQUENCE.ID, [MAPPABLE, AS_TRANS], 2))
        + as4_path(segment(SET.ID, [NON_MAPPABLE], 4))
    )

    assert AS_TRANS not in path_of(read).as_seq, (
        f'the AS_TRANS placeholder survived the reconstruction: {path_of(read).string()}'
    )
