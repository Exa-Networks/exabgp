"""RFC 4724: the Graceful Restart capability and the End-of-RIB marker.

exabgp keeps no forwarding state, so most of this RFC cannot bind it. Two things can: the
bytes of the capability, and the End-of-RIB marker, which has one encoding for IPv4
unicast and a different one for every other family. Sending the wrong one says "I have
finished" about a RIB the peer was not waiting on.

The ledger entries these prove are in qa/rfc/rfc4724.toml.
"""

from __future__ import annotations

from struct import pack
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.peer import Peer
from exabgp.rib import RIB


LOCAL_AS = 65001
PEER_AS = 65002
RESTART_TIME = 120

# RFC 4724 section 3: capability code 64, and the two flag fields whose reserved bits
# must leave as zero and be ignored on arrival.
RESERVED_RESTART_BITS = 0x7  # of the four bit Restart Flags nibble, R is 0x8
RESERVED_FAMILY_BITS = 0x7F  # of the eight bit family flags, F is 0x80

# RFC 4271 section 4.1: the smallest legal UPDATE, which is what an IPv4 unicast
# End-of-RIB marker is.
MINIMUM_UPDATE_LENGTH = 23
HEADER_LENGTH = 19

MP_UNREACH_NLRI = 15
OPTIONAL_EXTENDED = 0x90


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour(graceful: bool = True) -> Neighbor:
    block = f'capability {{ graceful-restart {RESTART_TIME}; }}' if graceful else ''
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as {LOCAL_AS};
    peer-as {PEER_AS};
    {block}
    family {{ ipv4 unicast; ipv6 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    parsed: Neighbor = next(iter(configuration.neighbors.values()))
    return parsed


def our_capabilities(neighbor: Neighbor, restarted: bool) -> Capabilities:
    return Capabilities().new(neighbor, restarted, local_as=ASN(LOCAL_AS))


def negotiated_session(neighbor: Neighbor) -> Negotiated:
    capabilities = our_capabilities(neighbor, False)
    negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(LOCAL_AS), HoldTime(180), RouterID('192.0.2.2'), capabilities))
    negotiated.received(
        Open.make_open(Version(4), ASN(PEER_AS), HoldTime(180), RouterID('192.0.2.1'), Capabilities(capabilities))
    )
    return negotiated


def capability_codes(packed: bytes) -> list[int]:
    """Every capability code in a packed OPEN parameter block, repeats included."""
    codes: list[int] = []
    total = packed[0] if packed else 0
    offset = 1
    while offset < 1 + total:
        kind, length = packed[offset], packed[offset + 1]
        assert kind == 2, 'only the capability optional parameter is expected here'
        end = offset + 2 + length
        inner = offset + 2
        while inner < end:
            codes.append(packed[inner])
            inner += 2 + packed[inner + 1]
        offset = end
    return codes


def graceful_value(restart_flags: int, restart_time: int, families: list[tuple[AFI, SAFI, int]]) -> bytes:
    """A Graceful Restart capability value as a peer would put it on the wire."""
    value = pack('!H', (restart_flags << 12) | restart_time)
    for afi, safi, flag in families:
        value += afi.pack_afi() + safi.pack_safi() + bytes([flag])
    return value


def capability_parameters(*values: bytes) -> bytes:
    """A capability optional parameter block carrying the Graceful Restart capability N times."""
    tlvs = b''.join(bytes([Capability.CODE.GRACEFUL_RESTART, len(value)]) + value for value in values)
    parameter = bytes([2, len(tlvs)]) + tlvs
    return bytes([len(parameter)]) + parameter


def eor_payload(afi: AFI, safi: SAFI) -> bytes:
    return EOR(afi, safi).pack_message(Mock())[HEADER_LENGTH:]


# ============================================================ 3 the capability bytes


@pytest.mark.rfc('rfc4724#3-reserved-bits-are-zero')
def test_we_leave_every_reserved_bit_at_zero() -> None:
    """Both flag fields: the Restart Flags nibble and the per family flags octet."""
    capabilities = our_capabilities(neighbour(), True)
    graceful = capabilities[Capability.CODE.GRACEFUL_RESTART]
    assert isinstance(graceful, Graceful)

    assert graceful.restart_flag & RESERVED_RESTART_BITS == 0, (
        f'a reserved Restart Flags bit was set: {graceful.restart_flag:#x}'
    )
    for family, flag in graceful.items():
        assert flag & RESERVED_FAMILY_BITS == 0, f'{family} carried reserved flag bits: {flag:#x}'


@pytest.mark.rfc('rfc4724#3-reserved-bits-are-zero', polarity='negative')
def test_a_peer_setting_every_reserved_bit_is_parsed_and_ignored() -> None:
    """Ignored, not refused: a peer which sets them must still get a session.

    Rejecting the capability, or keeping the bits and acting on them later, are the two
    ways to get this wrong. The decode has to survive and the bits have to disappear.
    """
    value = graceful_value(0xF, RESTART_TIME, [(AFI.ipv4, SAFI.unicast, 0xFF)])

    capabilities = Capabilities.unpack(capability_parameters(value))
    graceful = capabilities[Capability.CODE.GRACEFUL_RESTART]

    assert isinstance(graceful, Graceful)
    assert graceful.restart_time == RESTART_TIME, 'the reserved bits leaked into the Restart Time'
    assert graceful[(AFI.ipv4, SAFI.unicast)] & RESERVED_FAMILY_BITS == 0, 'a reserved family flag bit was kept'
    assert graceful[(AFI.ipv4, SAFI.unicast)] & Graceful.FORWARDING_STATE, 'the Forwarding State bit was lost with them'


@pytest.mark.rfc('rfc4724#3-single-capability-instance')
def test_the_graceful_restart_capability_is_sent_exactly_once() -> None:
    packed = our_capabilities(neighbour(), False).pack_capabilities()

    codes = capability_codes(packed)
    assert codes.count(Capability.CODE.GRACEFUL_RESTART) == 1, (
        f'the Graceful Restart capability appears {codes.count(Capability.CODE.GRACEFUL_RESTART)} times'
    )


@pytest.mark.rfc('rfc4724#3-receiver-keeps-the-last-instance')
def test_a_single_instance_is_taken_as_it_is() -> None:
    value = graceful_value(Graceful.RESTART_STATE, RESTART_TIME, [(AFI.ipv4, SAFI.unicast, Graceful.FORWARDING_STATE)])

    graceful = Capabilities.unpack(capability_parameters(value))[Capability.CODE.GRACEFUL_RESTART]

    assert isinstance(graceful, Graceful)
    assert graceful.restart_time == RESTART_TIME
    assert list(graceful.families()) == [(AFI.ipv4, SAFI.unicast)]


@pytest.mark.rfc('rfc4724#3-receiver-keeps-the-last-instance', polarity='negative')
def test_the_last_of_several_instances_wins() -> None:
    """Merging them is the tempting wrong answer: the families would be the union of two
    advertisements, and the restart time would be whichever one happened to be read last."""
    first = graceful_value(0, 60, [(AFI.ipv4, SAFI.unicast, Graceful.FORWARDING_STATE)])
    last = graceful_value(Graceful.RESTART_STATE, RESTART_TIME, [(AFI.ipv6, SAFI.unicast, 0)])

    graceful = Capabilities.unpack(capability_parameters(first, last))[Capability.CODE.GRACEFUL_RESTART]

    assert isinstance(graceful, Graceful)
    assert graceful.restart_time == RESTART_TIME, 'the first instance was kept'
    assert list(graceful.families()) == [(AFI.ipv6, SAFI.unicast)], (
        f'the instances were merged rather than the last one kept: {list(graceful.families())}'
    )


# ============================================================ 4.1 and 4.2 the restart bit


@pytest.mark.rfc('rfc4724#4.1-restarting-speaker-sets-restart-state')
def test_a_restarting_speaker_sets_the_restart_state_bit() -> None:
    graceful = our_capabilities(neighbour(), True)[Capability.CODE.GRACEFUL_RESTART]

    assert isinstance(graceful, Graceful)
    assert graceful.restart_flag & Graceful.RESTART_STATE, 'the session is being re-established after a restart'


@pytest.mark.rfc('rfc4724#4.1-restarting-speaker-sets-restart-state', polarity='negative')
def test_the_restart_state_bit_is_not_set_when_nothing_restarted() -> None:
    """The encoder honours the flag it is given. What decides the flag is the next test."""
    graceful = our_capabilities(neighbour(), False)[Capability.CODE.GRACEFUL_RESTART]

    assert isinstance(graceful, Graceful)
    assert not graceful.restart_flag & Graceful.RESTART_STATE


@pytest.mark.rfc('rfc4724#4.2-restart-state-not-set-unless-restarted')
@pytest.mark.xfail(
    strict=True,
    reason='Peer._restarted is initialised to the module constant FORCE_GRACEFUL, which is True, '
    'and only Peer.stop() ever clears it. Every OPEN exabgp sends therefore claims a restart, '
    'including the first of a process which has just started and every reconnection after it.',
)
def test_a_speaker_which_has_not_restarted_does_not_claim_it_has() -> None:
    """The bit tells the peer not to wait for our End-of-RIB before advertising to us.

    Claiming it on a session which is merely reconnecting is a claim about this speaker's
    state that is not true, and it is the peer which acts on it.
    """
    peer = Peer(neighbour(), Mock())

    graceful = our_capabilities(peer.neighbor, peer._restarted)[Capability.CODE.GRACEFUL_RESTART]

    assert isinstance(graceful, Graceful)
    assert not graceful.restart_flag & Graceful.RESTART_STATE, (
        'a peer which has never restarted advertised the Restart State bit'
    )


# ============================================================ 2 and 4 the End-of-RIB marker


@pytest.mark.rfc('rfc4724#4-end-of-rib-must-be-sent')
def test_the_ipv4_unicast_marker_is_an_update_of_the_minimum_length() -> None:
    """Section 2: for IPv4 unicast the marker is an UPDATE with the minimum length.

    Four zero octets: no withdrawn routes, no path attributes, no NLRI.
    """
    message = EOR(AFI.ipv4, SAFI.unicast).pack_message(Mock())

    assert len(message) == MINIMUM_UPDATE_LENGTH, f'the IPv4 unicast marker is {len(message)} bytes'
    assert message[HEADER_LENGTH:] == b'\x00\x00\x00\x00', f'unexpected payload {message[HEADER_LENGTH:]!r}'


@pytest.mark.rfc('rfc4724#4-end-of-rib-must-be-sent')
@pytest.mark.parametrize(
    'afi, safi',
    [(AFI.ipv6, SAFI.unicast), (AFI.ipv4, SAFI.multicast), (AFI.l2vpn, SAFI.evpn)],
    ids=['ipv6-unicast', 'ipv4-multicast', 'l2vpn-evpn'],
)
def test_every_other_family_uses_the_mp_unreach_form(afi: AFI, safi: SAFI) -> None:
    """Section 2: only MP_UNREACH_NLRI, and no withdrawn routes for that <AFI, SAFI>.

    The IPv4 unicast form would be indistinguishable from an IPv4 unicast marker, so a
    peer waiting on this family would never be told we had finished.
    """
    payload = eor_payload(afi, safi)

    withdrawn_length = int.from_bytes(payload[0:2], 'big')
    attribute_length = int.from_bytes(payload[2:4], 'big')
    flags, code, length = payload[4], payload[5], payload[6:8]

    assert withdrawn_length == 0, 'the marker carried withdrawn routes'
    assert attribute_length == len(payload) - 4, 'the marker carried something after its one attribute'
    assert code == MP_UNREACH_NLRI, f'the only attribute must be MP_UNREACH_NLRI, got {code}'
    assert flags == OPTIONAL_EXTENDED, f'MP_UNREACH_NLRI flags {flags:#x} are not optional with an extended length'
    assert int.from_bytes(length, 'big') == 3, 'MP_UNREACH_NLRI must carry the family and nothing else'
    assert payload[8:] == afi.pack_afi() + safi.pack_safi(), 'the marker names the wrong family'


@pytest.mark.rfc('rfc4724#4-end-of-rib-must-be-sent')
@pytest.mark.parametrize(
    'afi, safi',
    [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast), (AFI.l2vpn, SAFI.evpn)],
    ids=['ipv4-unicast', 'ipv6-unicast', 'l2vpn-evpn'],
)
def test_a_marker_we_send_is_read_back_as_a_marker_for_the_same_family(afi: AFI, safi: SAFI) -> None:
    """Both encodings have to survive our own decoder, or we cannot read a peer's."""
    negotiated = negotiated_session(neighbour())

    decoded = Update.unpack_message(eor_payload(afi, safi), negotiated)

    assert isinstance(decoded, EOR), f'a marker for {afi}/{safi} decoded as {type(decoded).__name__}'
    assert (decoded.nlris[0].afi, decoded.nlris[0].safi) == (afi, safi)


@pytest.mark.rfc('rfc4724#4-end-of-rib-must-be-sent', polarity='negative')
def test_an_update_carrying_nlri_is_not_a_marker() -> None:
    """The marker is defined by having nothing in it. A decoder which is too eager here
    reports the end of a peer's RIB while the peer is still sending it."""
    negotiated = negotiated_session(neighbour())
    attributes = bytes([0x40, 0x01, 0x01, 0x00]) + bytes([0x40, 0x02, 0x00]) + bytes([0x40, 0x03, 0x04, 192, 0, 2, 1])
    payload = pack('!H', 0) + pack('!H', len(attributes)) + attributes + bytes([24, 10, 0, 0])

    decoded = Update.unpack_message(payload, negotiated)

    assert not isinstance(decoded, EOR), 'an UPDATE announcing 10.0.0.0/24 was read as an End-of-RIB marker'


@pytest.mark.rfc('rfc4724#4-end-of-rib-must-be-sent', polarity='negative')
def test_an_update_withdrawing_a_prefix_is_not_a_marker() -> None:
    """ "Empty withdrawn NLRI" is part of the definition, so a withdrawal is not a marker."""
    negotiated = negotiated_session(neighbour())
    withdrawn = bytes([24, 10, 0, 0])
    payload = pack('!H', len(withdrawn)) + withdrawn + pack('!H', 0)

    decoded = Update.unpack_message(payload, negotiated)

    assert not isinstance(decoded, EOR), 'an UPDATE withdrawing 10.0.0.0/24 was read as an End-of-RIB marker'
