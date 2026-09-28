"""RFC 4724: the Graceful Restart capability and the End-of-RIB marker.

exabgp keeps no forwarding state, so most of this RFC cannot bind it. Two things can: the
bytes of the capability, and the End-of-RIB marker, which has one encoding for IPv4
unicast and a different one for every other family. Sending the wrong one says "I have
finished" about a RIB the peer was not waiting on.

The ledger entries these prove are in qa/rfc/rfc4724.toml.
"""

from __future__ import annotations

import asyncio
from struct import pack
from unittest.mock import AsyncMock, Mock

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message import Message
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.network.error import NetworkError
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

# RFC 4724 4.2: what the Receiving Speaker holds for a restarting peer.  The Restart Time
# is the one the peer advertises, short so that a test can outlive it.
IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)
KEPT = '10.0.0.0/24'
DROPPED = '10.0.1.0/24'
PEER_RESTART_TIME = 1
RESTART_TIME_MARGIN = 0.5


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour(graceful: bool = True, adj_rib_in: bool = False) -> Neighbor:
    block = f'capability {{ graceful-restart {RESTART_TIME}; }}' if graceful else ''
    text = f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as {LOCAL_AS};
    peer-as {PEER_AS};
    adj-rib-in {'true' if adj_rib_in else 'false'};
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


def graceful_session(neighbor: Neighbor, restart_time: int, forwarding: int = Graceful.FORWARDING_STATE) -> Negotiated:
    """A session whose peer advertised Graceful Restart for both families, with this Restart Time.

    The Forwarding State bit is set unless told otherwise: RFC 4724 4.2 has the stale routes
    of a family removed at once when the new OPEN clears it.
    """
    ours = our_capabilities(neighbor, False)
    theirs = Capabilities(ours)
    value = graceful_value(
        0, restart_time, [(AFI.ipv4, SAFI.unicast, forwarding), (AFI.ipv6, SAFI.unicast, forwarding)]
    )
    theirs[Capability.CODE.GRACEFUL_RESTART] = Capabilities.unpack(capability_parameters(value))[
        Capability.CODE.GRACEFUL_RESTART
    ]
    negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(LOCAL_AS), HoldTime(180), RouterID('192.0.2.2'), ours))
    negotiated.received(Open.make_open(Version(4), ASN(PEER_AS), HoldTime(180), RouterID('192.0.2.1'), theirs))
    assert negotiated.received_open is not None
    assert negotiated.received_open.capabilities.announced(Capability.CODE.GRACEFUL_RESTART)
    return negotiated


def announce(negotiated: Negotiated, *prefixes: str) -> Message:
    """An IPv4 unicast UPDATE for /24s, decoded the way the reactor decodes one."""
    # AS_PATH <PEER_AS>, four octets: an EBGP route starts with the peer's AS (RFC 8955 6)
    as_path = bytes([0x40, 0x02, 0x06, 0x02, 0x01]) + pack('!L', PEER_AS)
    attributes = bytes([0x40, 0x01, 0x01, 0x00]) + as_path + bytes([0x40, 0x03, 0x04, 192, 0, 2, 1])
    nlri = b''
    for prefix in prefixes:
        address, mask = prefix.split('/')
        assert mask == '24', 'the encoding below is for /24 only'
        nlri += bytes([24]) + bytes(int(octet) for octet in address.split('.')[:3])
    payload = pack('!H', 0) + pack('!H', len(attributes)) + attributes + nlri
    return Update.unpack_message(payload, negotiated)


def end_of_rib(negotiated: Negotiated) -> Message:
    decoded = Update.unpack_message(eor_payload(*IPV4_UNICAST), negotiated)
    assert isinstance(decoded, EOR)
    return decoded


def held(peer: Peer) -> list[str]:
    """What the adj-RIB-in holds from the peer, stale or not."""
    return sorted(str(route.nlri) for route in peer.neighbor.rib.incoming.cached_routes([IPV4_UNICAST]))


async def session(peer: Peer, negotiated: Negotiated, *messages: Message) -> list[list[str]]:
    """One session, from establishment to the TCP connection being lost.

    The peer sends `messages` and then the connection drops, which Peer._run handles by
    calling _reset: that is the Receiving Speaker detecting termination of the session.
    Returns what the adj-RIB-in held before each message was read, and once more before
    the connection was lost.
    """
    await establish(peer)
    assert peer.proto is not None
    peer.proto.negotiated = negotiated
    peer.proto.close = Mock()

    pending = list(messages)
    snapshots: list[list[str]] = []

    async def read_message() -> Message:
        snapshots.append(held(peer))
        if not pending:
            raise NetworkError('the TCP session was terminated')
        return pending.pop(0)

    peer.proto.read_message = read_message
    try:
        await peer._main()
    except NetworkError as lost:
        peer._reset('closing connection', lost)
    assert len(snapshots) == len(messages) + 1, 'the session ended before the peer had sent everything'
    return snapshots


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
    return EOR.make_eor(afi, safi).pack_message(Mock())[HEADER_LENGTH:]


async def establish(peer: Peer) -> None:
    """Take a Peer to ESTABLISHED over a protocol which answers but sends nothing.

    The Restart State bit is decided by how many sessions this process has held with the
    neighbor, so a test about it has to go through the establishment path rather than
    poke the flag the path sets.
    """
    protocol = AsyncMock()
    protocol.connection = Mock(session=Mock(return_value='test'))
    protocol.negotiated = Mock(holdtime=HoldTime(180), msg_size=4096)
    protocol.validate_open = Mock()
    # a Protocol knows its Peer, which is who the End-of-RIB handler tells the API through
    protocol.peer = peer
    peer.proto = protocol

    await peer._establish()

    assert peer.fsm == FSM.ESTABLISHED, 'the mocked protocol did not reach ESTABLISHED'


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


@pytest.mark.rfc('rfc4724#4.1-restarting-speaker-sets-restart-state')
def test_the_first_open_of_a_process_claims_a_restart() -> None:
    """Deliberate, and the reason FORCE_GRACEFUL exists.

    This run may be a restart of an earlier one, in which case 4.1 requires the bit and a
    peer is holding our routes; or it may be a first start, in which case 4.2 forbids it.
    Nothing here can tell which, because exabgp keeps no state between runs. Setting it
    only asks the peer not to wait for our End-of-RIB, so it is the cheap way to be wrong.
    """
    peer = Peer(neighbour(), Mock())

    graceful = our_capabilities(peer.neighbor, peer._restarted)[Capability.CODE.GRACEFUL_RESTART]

    assert isinstance(graceful, Graceful)
    assert graceful.restart_flag & Graceful.RESTART_STATE


@pytest.mark.rfc('rfc4724#4.2-restart-state-not-set-unless-restarted')
@pytest.mark.asyncio
async def test_a_reconnecting_speaker_does_not_claim_it_has_restarted() -> None:
    """ "In re-establishing the session" is what 4.2 binds, and that case is knowable.

    Once this process has held a session with a neighbor, everything after it is a
    reconnection: a TCP reset, a hold timer, a peer which itself restarted. This speaker
    did not restart, and the bit tells the peer not to wait for our End-of-RIB, so
    claiming it on every reconnection for the life of the process is a claim about our
    state which is false and which the peer acts on.
    """
    peer = Peer(neighbour(), Mock())

    await establish(peer)

    graceful = our_capabilities(peer.neighbor, peer._restarted)[Capability.CODE.GRACEFUL_RESTART]
    assert isinstance(graceful, Graceful)
    assert not graceful.restart_flag & Graceful.RESTART_STATE, (
        'a peer reconnecting within one process advertised the Restart State bit'
    )


@pytest.mark.rfc('rfc4724#4.1-restarting-speaker-sets-restart-state')
@pytest.mark.asyncio
async def test_an_operator_asking_for_a_restart_gets_the_bit_back() -> None:
    """reestablish() is the `restart` command and a reload which changed the neighbor.

    The session is torn down and the RIB rebuilt, so the peer is told rather than left to
    wait on an End-of-RIB for routes it is about to be sent again.
    """
    peer = Peer(neighbour(), Mock())
    await establish(peer)

    peer.reestablish()

    graceful = our_capabilities(peer.neighbor, peer._restarted)[Capability.CODE.GRACEFUL_RESTART]
    assert isinstance(graceful, Graceful)
    assert graceful.restart_flag & Graceful.RESTART_STATE


# ============================================================ 2 and 4 the End-of-RIB marker


@pytest.mark.rfc('rfc4724#4-end-of-rib-must-be-sent')
def test_the_ipv4_unicast_marker_is_an_update_of_the_minimum_length() -> None:
    """Section 2: for IPv4 unicast the marker is an UPDATE with the minimum length.

    Four zero octets: no withdrawn routes, no path attributes, no NLRI.
    """
    message = EOR.make_eor(AFI.ipv4, SAFI.unicast).pack_message(Mock())

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


# ============================================================ 4.2 the Receiving Speaker


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale')
@pytest.mark.asyncio
async def test_routes_from_a_restarting_peer_are_retained_into_the_next_session() -> None:
    """Retained until the peer has had its chance to send them again, not until it reconnects.

    Stale is only visible through what ends it, an End-of-RIB or the Restart Time, which
    are the two tests below. What this one holds to is the retention: the routes are
    still there when the restarted peer is back and has not yet sent a single UPDATE.
    """
    peer = Peer(neighbour(adj_rib_in=True), Mock())
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT, DROPPED))
    assert held(peer) == [KEPT, DROPPED], 'the adj-RIB-in did not hold what the peer sent'

    restarted = await session(peer, negotiated)

    assert restarted[0] == [KEPT, DROPPED], (
        f'the routes of a Graceful Restart peer were not retained across its restart: {restarted[0]}'
    )


@pytest.mark.rfc('rfc4724#4.2-delete-stale-after-restart-time')
@pytest.mark.asyncio
async def test_routes_retained_for_a_peer_which_does_not_return_expire_with_its_restart_time() -> None:
    peer = Peer(neighbour(adj_rib_in=True), Mock())
    negotiated = graceful_session(peer.neighbor, PEER_RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT))
    assert held(peer) == [KEPT], 'the routes were not retained when the session went down'

    await asyncio.sleep(PEER_RESTART_TIME + RESTART_TIME_MARGIN)

    assert held(peer) == [], f'{PEER_RESTART_TIME}s after the session was lost the stale routes are still held'


@pytest.mark.rfc('rfc4724#4.2-remove-stale-on-end-of-rib')
@pytest.mark.asyncio
async def test_the_end_of_rib_removes_what_the_restarted_peer_did_not_send_again() -> None:
    """Before the End-of-RIB the peer may still be sending, so nothing may go early.

    A route missing only after the marker is the whole point of the marker: removing it
    at reconnection, as happens now, ends in the same table by a path which withdraws
    every route of a restarting peer and then announces most of them again.
    """
    peer = Peer(neighbour(adj_rib_in=True), Mock())
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT, DROPPED))
    restarted = await session(peer, negotiated, announce(negotiated, KEPT), end_of_rib(negotiated))

    before_eor, after_eor = restarted[1], restarted[2]
    assert before_eor == [KEPT, DROPPED], f'a stale route was removed before the End-of-RIB: {before_eor}'
    assert after_eor == [KEPT], f'the End-of-RIB left a route the peer did not send again: {after_eor}'


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale', polarity='negative')
@pytest.mark.asyncio
async def test_a_new_open_clearing_the_forwarding_state_bit_removes_the_stale_routes_at_once() -> None:
    """RFC 4724 4.2: retention is for a peer which kept forwarding; one which says it did
    not has its stale routes removed as soon as the new session is up."""
    peer = Peer(neighbour(adj_rib_in=True), Mock())
    retained = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, retained, announce(retained, KEPT))
    restarted = await session(peer, graceful_session(peer.neighbor, RESTART_TIME, forwarding=0))

    assert restarted[0] == [], f'a peer which cleared its Forwarding State bit kept its stale routes: {restarted[0]}'


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale', polarity='negative')
@pytest.mark.asyncio
async def test_a_peer_without_graceful_restart_has_its_routes_cleared_at_the_next_session() -> None:
    """Only a peer which advertised the capability is retained for."""
    peer = Peer(neighbour(adj_rib_in=True), Mock())
    plain = negotiated_session(peer.neighbor)
    plain.received_open.capabilities.pop(Capability.CODE.GRACEFUL_RESTART, None)

    await session(peer, plain, announce(plain, KEPT))
    restarted = await session(peer, plain)

    assert restarted[0] == []


@pytest.mark.asyncio
async def test_a_notification_ends_the_session_without_retaining_anything() -> None:
    """Unmarked: RFC 4724 is about the TCP session being lost; a NOTIFICATION is a clean end."""
    peer = Peer(neighbour(adj_rib_in=True), Mock())
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    await session(peer, negotiated, announce(negotiated, KEPT))
    # the session above ended on a lost TCP connection; do it again, ended by a NOTIFICATION
    peer.neighbor.rib.incoming.clear()
    await establish(peer)
    assert peer.proto is not None
    peer.proto.negotiated = negotiated
    peer.proto.close = Mock()
    peer._reset('notification received', 'a NOTIFICATION, not a NetworkError')

    assert peer.neighbor.rib.incoming.restarting_families() == set()


@pytest.mark.asyncio
async def test_the_api_is_told_when_the_end_of_rib_removes_stale_routes() -> None:
    """Unmarked: the API saw the routes announced, so it is told they are gone."""
    reactor = Mock()
    peer = Peer(neighbour(adj_rib_in=True), reactor)
    peer.neighbor.api['receive-update'] = True
    peer.neighbor.api['receive-parsed'] = True
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT, DROPPED))
    await session(peer, negotiated, announce(negotiated, KEPT), end_of_rib(negotiated))

    told = [str(nlri) for call in reactor.processes.message.call_args_list for nlri in call.args[3].data.withdraws]
    assert told == [DROPPED]


@pytest.mark.asyncio
async def test_the_api_is_told_when_the_restart_time_removes_stale_routes() -> None:
    """Unmarked: a peer which never comes back has its routes withdrawn to the API too."""
    reactor = Mock()
    peer = Peer(neighbour(adj_rib_in=True), reactor)
    peer.neighbor.api['receive-update'] = True
    peer.neighbor.api['receive-parsed'] = True
    negotiated = graceful_session(peer.neighbor, PEER_RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT))
    await asyncio.sleep(PEER_RESTART_TIME + RESTART_TIME_MARGIN)

    told = [str(nlri) for call in reactor.processes.message.call_args_list for nlri in call.args[3].data.withdraws]
    assert told == [KEPT]
