"""RFC 4724: the Graceful Restart capability and the End-of-RIB marker.

exabgp keeps no forwarding state, so most of this RFC cannot bind it. Two things can: the
bytes of the capability, and the End-of-RIB marker, which has one encoding for IPv4
unicast and a different one for every other family. Sending the wrong one says "I have
finished" about a RIB the peer was not waiting on.

The ledger entries these prove are in qa/rfc/rfc4724.toml.
"""

from __future__ import annotations

import asyncio
import json
import socket
from collections.abc import Callable
from typing import Any
from struct import pack

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.graceful import Graceful
from exabgp.bgp.message.open.capability.mp import MultiProtocol
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message import KeepAlive
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.message.update.eor import EOR
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.network.error import NetworkError
from exabgp.reactor.network.incoming import Incoming
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests.negotiation import PROCESS, Told, connect, received
from tests.negotiation import messages as negotiation_messages
from tests.negotiation import peer as real_peer


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

# RFC 4271 4.1: the marker every message starts with, and the UPDATE type code
MARKER = bytes([0xFF] * 16)
UPDATE = 2
NOTIFICATION = 3

# RFC 4486 4: the Cease subcode a connection refused under RFC 4271 6.8 is sent
CONNECTION_COLLISION_RESOLUTION = (6, 7)

# The session runs as its own task reading a real socket, so the test polls for it to act
# on what the peer sent, bounded so that a session which never does fails the test.
POLL_SECONDS = 0.01
POLL_ROUNDS = 500


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


def their_capabilities(neighbor: Neighbor) -> Capabilities:
    """What the peer advertises: ours, with its own AS in the four octet AS capability."""
    return Capabilities().new(neighbor, False, local_as=ASN(PEER_AS))


def negotiated_session(neighbor: Neighbor) -> Negotiated:
    capabilities = our_capabilities(neighbor, False)
    negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(LOCAL_AS), HoldTime(180), RouterID('192.0.2.2'), capabilities))
    negotiated.received(
        Open.make_open(Version(4), ASN(PEER_AS), HoldTime(180), RouterID('192.0.2.1'), their_capabilities(neighbor))
    )
    return negotiated


def graceful_session(
    neighbor: Neighbor,
    restart_time: int,
    forwarding: int = Graceful.FORWARDING_STATE,
    offered: list[tuple[AFI, SAFI]] | None = None,
) -> Negotiated:
    """A session whose peer advertised Graceful Restart for both families, with this Restart Time.

    The Forwarding State bit is set unless told otherwise: RFC 4724 4.2 has the stale routes
    of a family removed at once when the new OPEN clears it. `offered` replaces the families
    of the peer's Multiprotocol capability, the Graceful Restart one still naming both.
    """
    ours = our_capabilities(neighbor, False)
    theirs = their_capabilities(neighbor)
    if offered is not None:
        multiprotocol = MultiProtocol()
        multiprotocol.extend(offered)
        theirs[Capability.CODE.MULTIPROTOCOL] = multiprotocol
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


def announce(negotiated: Negotiated, *prefixes: str) -> bytes:
    """An IPv4 unicast UPDATE for /24s, as the peer puts it on the wire.

    Decoded once here with the session, so a payload this test got wrong fails here
    rather than as a route which never arrives.
    """
    # AS_PATH <PEER_AS>, four octets: an EBGP route starts with the peer's AS (RFC 8955 6)
    as_path = bytes([0x40, 0x02, 0x06, 0x02, 0x01]) + pack('!L', PEER_AS)
    attributes = bytes([0x40, 0x01, 0x01, 0x00]) + as_path + bytes([0x40, 0x03, 0x04, 192, 0, 2, 1])
    nlri = b''
    for prefix in prefixes:
        address, mask = prefix.split('/')
        assert mask == '24', 'the encoding below is for /24 only'
        nlri += bytes([24]) + bytes(int(octet) for octet in address.split('.')[:3])
    payload = pack('!H', 0) + pack('!H', len(attributes)) + attributes + nlri
    decoded = Update.unpack_message(payload, negotiated)
    assert len(decoded.data.announces) == len(prefixes), 'the UPDATE built does not announce what was asked'
    return MARKER + pack('!H', HEADER_LENGTH + len(payload)) + bytes([UPDATE]) + payload


def end_of_rib(negotiated: Negotiated) -> bytes:
    """The IPv4 unicast End-of-RIB marker, as the peer puts it on the wire."""
    decoded = Update.unpack_message(eor_payload(*IPV4_UNICAST), negotiated)
    assert isinstance(decoded, EOR)
    return EOR.make_eor(*IPV4_UNICAST).pack_message(negotiated)


def withdrawn(told: Told) -> list[str]:
    """Every route the API was told the peer withdrew, in order."""
    return [str(nlri) for args in told.called('update') for nlri in args[2].withdraws]


def held(peer: Peer) -> list[str]:
    """What the adj-RIB-in holds from the peer, stale or not."""
    return sorted(str(route.nlri) for route in peer.neighbor.rib.incoming.cached_routes([IPV4_UNICAST]))


async def until(condition: Callable[[], bool], what: str) -> None:
    """Let the session run until `condition` holds."""
    for _ in range(POLL_ROUNDS):
        if condition():
            return
        await asyncio.sleep(POLL_SECONDS)
    raise AssertionError(f'{what} did not happen within {POLL_SECONDS * POLL_ROUNDS} seconds')


async def session(peer: Peer, negotiated: Negotiated, *messages: bytes) -> list[list[str]]:
    """One session, from establishment to the TCP connection being lost.

    The peer sends `messages` over a real connection and then closes it, which Peer._run
    handles by calling _reset: that is the Receiving Speaker detecting termination of the
    session. Returns what the adj-RIB-in held before each message was read, and once more
    before the connection was lost.
    """
    theirs = await establish(peer, negotiated)
    assert peer.proto is not None
    # the session the test describes, whatever the OPEN exchange computed from the wire
    peer.proto.negotiated = negotiated

    up = peer.stats['up']
    running = asyncio.ensure_future(peer._main())
    snapshots: list[list[str]] = []
    try:
        await until(lambda: peer.stats['up'] > up or running.done(), 'the session coming up')
        snapshots.append(held(peer))
        for message in messages:
            # an UPDATE is handled in the step which counts it, with no await in between
            count = peer.stats['receive-update']
            theirs.sendall(message)
            await until(
                lambda count=count: peer.stats['receive-update'] > count or running.done(), 'the message being read'
            )
            snapshots.append(held(peer))
    finally:
        theirs.close()

    try:
        await running
    except NetworkError as lost:
        peer._reset('closing connection', lost)
    else:
        raise AssertionError('the session outlived its TCP connection')
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
        value += afi.pack_afi() + safi.pack_safi() + bytes([int(flag)])
    return value


def capability_parameters(*values: bytes) -> bytes:
    """A capability optional parameter block carrying the Graceful Restart capability N times."""
    tlvs = b''.join(bytes([int(Capability.CODE.GRACEFUL_RESTART), len(value)]) + value for value in values)
    parameter = bytes([2, len(tlvs)]) + tlvs
    return bytes([len(parameter)]) + parameter


def eor_payload(afi: AFI, safi: SAFI) -> bytes:
    return EOR.make_eor(afi, safi).pack_message(Negotiated.UNSET)[HEADER_LENGTH:]


async def establish(peer: Peer, negotiated: Negotiated | None = None) -> socket.socket:
    """Take a Peer to ESTABLISHED over a real connection, and return the peer's end of it.

    The peer's end has already sent the OPEN `negotiated` received, and the KEEPALIVE
    which confirms ours. The Restart State bit is decided by how many sessions this
    process has held with the neighbor, so a test about it has to go through the
    establishment path rather than poke the flag the path sets.
    """
    if negotiated is None:
        negotiated = negotiated_session(peer.neighbor)
    assert negotiated.received_open is not None
    protocol = Protocol(peer)
    theirs = connect(protocol)
    theirs.sendall(
        negotiated.received_open.pack_message(negotiated) + KeepAlive.make_keepalive().pack_message(negotiated)
    )
    peer.proto = protocol

    await peer._establish()

    assert peer.fsm == FSM.ESTABLISHED, 'the session did not reach ESTABLISHED'
    return theirs


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


def graceful_json(restart_flags: int, family_flag: int) -> dict[str, Any]:
    value = graceful_value(restart_flags, RESTART_TIME, [(AFI.ipv4, SAFI.unicast, family_flag)])
    graceful = Capabilities.unpack(capability_parameters(value))[Capability.CODE.GRACEFUL_RESTART]
    assert isinstance(graceful, Graceful)
    decoded: dict[str, Any] = json.loads(graceful.json())
    return decoded


def test_the_restart_state_bit_is_named_restart_in_json() -> None:
    """The R bit is the Restart State: it was printed as "forwarding", and F as "restart"."""
    decoded = graceful_json(Graceful.RESTART_STATE, 0)

    assert decoded['restart-flags'] == ['restart']
    assert decoded['address-family-flags'] == {'ipv4/unicast': []}


def test_the_forwarding_state_bit_is_named_forwarding_in_json() -> None:
    decoded = graceful_json(0, Graceful.FORWARDING_STATE)

    assert decoded['restart-flags'] == []
    assert decoded['address-family-flags'] == {'ipv4/unicast': ['forwarding']}


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
    peer, _ = real_peer(neighbour())

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
    peer, _ = real_peer(neighbour())

    (await establish(peer)).close()

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
    peer, _ = real_peer(neighbour())
    (await establish(peer)).close()

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
    message = EOR.make_eor(AFI.ipv4, SAFI.unicast).pack_message(Negotiated.UNSET)

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


# ------------------------------------------- 2 a marker is what is on the wire, not what is left


def from_the_peer() -> Negotiated:
    """An EBGP session reading what the peer sent, with Flow Specification negotiated too."""
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(LOCAL_AS)
    negotiated.peer_as = ASN(PEER_AS)
    negotiated.asn4 = True
    negotiated.families = [IPV4_UNICAST, (AFI.ipv6, SAFI.unicast), (AFI.ipv4, SAFI.flow_ip)]
    return negotiated


def update_body(attributes: bytes) -> bytes:
    """An UPDATE body with no withdrawn routes, these path attributes, and no NLRI."""
    return pack('!H', 0) + pack('!H', len(attributes)) + attributes


# MP_UNREACH_NLRI with a one octet length, as most implementations send the marker
OPTIONAL = 0x80
SHORT_MP_UNREACH_EOR = update_body(
    bytes([OPTIONAL, MP_UNREACH_NLRI, 3]) + AFI.ipv6.pack_afi() + SAFI.unicast.pack_safi()
)

# what decodes to nothing, each for its own reason, none of them an End-of-RIB
EMPTIED_UPDATES = {
    # RFC 7606 7.5: LOCAL_PREF from an external peer is discarded, the UPDATE carried on
    'local-pref-from-ebgp': update_body(bytes([0x40, 0x05, 0x04, 0, 0, 0, 100])),
    # RFC 4271 9: an unrecognised optional non-transitive attribute is ignored
    'unknown-non-transitive': update_body(bytes([OPTIONAL, 0xF0, 0x01, 0x00])),
    # a flow withdrawal whose single component the flow decoder refuses
    'invalid-flow-withdrawal': update_body(
        bytes([OPTIONAL, MP_UNREACH_NLRI, 5]) + AFI.ipv4.pack_afi() + SAFI.flow_ip.pack_safi() + bytes([1, 0xFF])
    ),
}


@pytest.mark.rfc('rfc4724#2-other-family-end-of-rib-is-only-mp-unreach')
def test_a_marker_with_a_one_octet_attribute_length_is_a_marker() -> None:
    """The extended length bit is the sender's choice, so both encodings are the marker."""
    decoded = Update.unpack_message(SHORT_MP_UNREACH_EOR, from_the_peer())

    assert decoded.IS_EOR, f'the marker was decoded as {type(decoded).__name__}'
    assert (decoded.nlris[0].afi, decoded.nlris[0].safi) == (AFI.ipv6, SAFI.unicast)


@pytest.mark.rfc('rfc4724#2-other-family-end-of-rib-is-only-mp-unreach')
def test_the_collection_path_reads_a_marker_with_a_one_octet_attribute_length() -> None:
    """UpdateCollection.unpack_message knew only the extended length encoding of the marker."""
    collection = UpdateCollection.unpack_message(SHORT_MP_UNREACH_EOR, from_the_peer())

    assert collection.IS_EOR, 'the one octet length marker was read as an UPDATE'
    assert (collection.eor_afi, collection.eor_safi) == (AFI.ipv6, SAFI.unicast)


@pytest.mark.rfc('rfc4724#2-ipv4-unicast-end-of-rib-is-minimum-update', polarity='negative')
@pytest.mark.rfc('rfc4724#2-other-family-end-of-rib-is-only-mp-unreach', polarity='negative')
@pytest.mark.parametrize('payload', list(EMPTIED_UPDATES.values()), ids=list(EMPTIED_UPDATES))
def test_an_update_which_decodes_to_nothing_is_not_a_marker(payload: bytes) -> None:
    """Deciding from what the decoder kept made every emptied UPDATE an End-of-RIB.

    The handler then ends the restart of the family, so a peer sending any of these to a
    session holding its stale routes had them removed before it had sent its RIB again.
    """
    decoded = Update.unpack_message(payload, from_the_peer())

    assert not decoded.IS_EOR, f'an UPDATE which decoded to nothing was read as {decoded}'


@pytest.mark.rfc('rfc4724#2-ipv4-unicast-end-of-rib-is-minimum-update')
def test_the_minimum_length_update_is_the_ipv4_unicast_marker() -> None:
    decoded = Update.unpack_message(b'\x00\x00\x00\x00', from_the_peer())

    assert decoded.IS_EOR
    assert (decoded.nlris[0].afi, decoded.nlris[0].safi) == IPV4_UNICAST


@pytest.mark.rfc('rfc4724#2-other-family-end-of-rib-is-only-mp-unreach', polarity='negative')
def test_an_mp_unreach_beside_another_attribute_is_not_a_marker() -> None:
    """ "Contains only the MP_UNREACH_NLRI attribute": an ORIGIN beside it makes it an UPDATE."""
    attributes = bytes([0x40, 0x01, 0x01, 0x00]) + SHORT_MP_UNREACH_EOR[4:]

    decoded = Update.unpack_message(update_body(attributes), from_the_peer())

    assert not decoded.IS_EOR


# ============================================================ 4.2 the Receiving Speaker


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale')
@pytest.mark.asyncio
async def test_routes_from_a_restarting_peer_are_retained_into_the_next_session() -> None:
    """Retained until the peer has had its chance to send them again, not until it reconnects.

    Stale is only visible through what ends it, an End-of-RIB or the Restart Time, which
    are the two tests below. What this one holds to is the retention: the routes are
    still there when the restarted peer is back and has not yet sent a single UPDATE.
    """
    peer, _ = real_peer(neighbour(adj_rib_in=True))
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
    peer, _ = real_peer(neighbour(adj_rib_in=True))
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
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT, DROPPED))
    restarted = await session(peer, negotiated, announce(negotiated, KEPT), end_of_rib(negotiated))

    before_eor, after_eor = restarted[1], restarted[2]
    assert before_eor == [KEPT, DROPPED], f'a stale route was removed before the End-of-RIB: {before_eor}'
    assert after_eor == [KEPT], f'the End-of-RIB left a route the peer did not send again: {after_eor}'


@pytest.mark.rfc('rfc4724#4.2-delete-stale-on-consecutive-restart')
@pytest.mark.asyncio
async def test_a_route_still_stale_when_the_peer_restarts_again_is_deleted() -> None:
    """A second restart before the End-of-RIB used to mark every held route stale again.

    The route the peer did not send in the session between the two restarts was then kept
    through a second Restart Time, and a peer restarting in a loop kept it for ever.
    """
    peer, told = real_peer(neighbour(adj_rib_in=True))
    peer.neighbor.api['receive-update'] = [PROCESS]
    peer.neighbor.api['receive-parsed'] = [PROCESS]
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT, DROPPED))
    await session(peer, negotiated, announce(negotiated, KEPT))
    # KEPT is sent again, or the loss of this session would rightly delete it too
    again = await session(peer, negotiated, announce(negotiated, KEPT))

    assert again[0] == [KEPT], f'a route stale since the previous restart was retained again: {again[0]}'
    assert withdrawn(told) == [DROPPED], f'the API was not told the stale route went: {withdrawn(told)}'


@pytest.mark.rfc('rfc4724#4.2-delete-stale-on-consecutive-restart', polarity='negative')
@pytest.mark.asyncio
async def test_a_route_sent_again_before_the_next_restart_is_retained_again() -> None:
    """Only what is still stale goes: a route the peer sent again is fresh, and kept as stale."""
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT))
    await session(peer, negotiated, announce(negotiated, KEPT))
    again = await session(peer, negotiated)

    assert again[0] == [KEPT], f'a route the peer sent again was not retained across its restart: {again[0]}'
    assert IPV4_UNICAST in peer.neighbor.rib.incoming.restarting_families()


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale', polarity='negative')
@pytest.mark.asyncio
async def test_a_new_open_clearing_the_forwarding_state_bit_removes_the_stale_routes_at_once() -> None:
    """RFC 4724 4.2: retention is for a peer which kept forwarding; one which says it did
    not has its stale routes removed as soon as the new session is up."""
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    retained = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, retained, announce(retained, KEPT))
    restarted = await session(peer, graceful_session(peer.neighbor, RESTART_TIME, forwarding=0))

    assert restarted[0] == [], f'a peer which cleared its Forwarding State bit kept its stale routes: {restarted[0]}'


@pytest.mark.rfc('rfc4724#4.2-remove-stale-on-end-of-rib')
@pytest.mark.asyncio
async def test_the_stale_routes_of_a_family_the_new_session_did_not_negotiate_are_removed_at_once() -> None:
    """Its End-of-RIB, the marker which would end them, cannot come: the family is not on
    the session, and an End-of-RIB for it is ignored. The Graceful Restart capability
    still naming it with the Forwarding State bit does not change that."""
    peer, told = real_peer(neighbour(adj_rib_in=True))
    peer.neighbor.api['receive-update'] = [PROCESS]
    peer.neighbor.api['receive-parsed'] = [PROCESS]
    retained = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, retained, announce(retained, KEPT))
    restarted = await session(peer, graceful_session(peer.neighbor, RESTART_TIME, offered=[(AFI.ipv6, SAFI.unicast)]))

    assert restarted[0] == [], f'the stale routes of a family not negotiated were kept: {restarted[0]}'
    assert withdrawn(told) == [KEPT]


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale', polarity='negative')
@pytest.mark.asyncio
async def test_a_peer_without_graceful_restart_has_its_routes_cleared_at_the_next_session() -> None:
    """Only a peer which advertised the capability is retained for."""
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    plain = negotiated_session(peer.neighbor)
    plain.received_open.capabilities.pop(Capability.CODE.GRACEFUL_RESTART, None)

    await session(peer, plain, announce(plain, KEPT))
    restarted = await session(peer, plain)

    assert restarted[0] == []


@pytest.mark.asyncio
async def test_a_notification_ends_the_session_without_retaining_anything() -> None:
    """Unmarked: RFC 4724 is about the TCP session being lost; a NOTIFICATION is a clean end."""
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    await session(peer, negotiated, announce(negotiated, KEPT))
    # the session above ended on a lost TCP connection; do it again, ended by a NOTIFICATION
    peer.neighbor.rib.incoming.clear()
    theirs = await establish(peer, negotiated)
    assert peer.proto is not None
    peer.proto.negotiated = negotiated
    theirs.close()
    peer._reset('notification received', 'a NOTIFICATION, not a NetworkError')

    assert peer.neighbor.rib.incoming.restarting_families() == set()


@pytest.mark.asyncio
async def test_the_api_is_told_when_the_end_of_rib_removes_stale_routes() -> None:
    """Unmarked: the API saw the routes announced, so it is told they are gone."""
    peer, told = real_peer(neighbour(adj_rib_in=True))
    peer.neighbor.api['receive-update'] = [PROCESS]
    peer.neighbor.api['receive-parsed'] = [PROCESS]
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT, DROPPED))
    await session(peer, negotiated, announce(negotiated, KEPT), end_of_rib(negotiated))

    assert withdrawn(told) == [DROPPED]


@pytest.mark.asyncio
async def test_the_api_is_told_when_the_restart_time_removes_stale_routes() -> None:
    """Unmarked: a peer which never comes back has its routes withdrawn to the API too."""
    peer, told = real_peer(neighbour(adj_rib_in=True))
    peer.neighbor.api['receive-update'] = [PROCESS]
    peer.neighbor.api['receive-parsed'] = [PROCESS]
    negotiated = graceful_session(peer.neighbor, PEER_RESTART_TIME)

    await session(peer, negotiated, announce(negotiated, KEPT))
    await asyncio.sleep(PEER_RESTART_TIME + RESTART_TIME_MARGIN)

    assert withdrawn(told) == [KEPT]


# ------------------------------------------- 4.2 a new connection while the session is established


def accepted_connection() -> tuple[Incoming, socket.socket]:
    """A connection the listener accepted from the peer, over loopback TCP, and the peer's end.

    Incoming() disables Nagle, which a socket pair refuses, so the pair is a TCP one. Building
    the Incoming around a socket pair, with Incoming.__new__, does not work once compiled:
    mypyc's __new__ runs __init__, so the connection is made the way the listener makes it.
    """
    with socket.create_server(('127.0.0.1', 0)) as listener:
        theirs = socket.create_connection(listener.getsockname())
        ours, _ = listener.accept()
    return Incoming(AFI.ipv4, '192.0.2.1', '192.0.2.2', ours), theirs


async def running_session(peer: Peer, negotiated: Negotiated, *messages: bytes) -> socket.socket:
    """Establish a session in the task Peer.run runs it in, and have the peer send `messages`.

    The task is the one handle_connection has to stop: a session the test drives itself
    would have no task to cancel. Returns the peer's end of the connection.
    """
    assert negotiated.received_open is not None
    protocol = Protocol(peer)
    theirs = connect(protocol)
    theirs.sendall(
        negotiated.received_open.pack_message(negotiated) + KeepAlive.make_keepalive().pack_message(negotiated)
    )
    peer.proto = protocol
    asyncio.ensure_future(peer._run_session())
    await until(lambda: peer.stats['up'] > 0, 'the session coming up')
    for message in messages:
        count = peer.stats['receive-update']
        theirs.sendall(message)
        await until(lambda count=count: peer.stats['receive-update'] > count, 'the message being read')
    return theirs


async def ended(peer: Peer, *sockets: socket.socket) -> None:
    """Stop whatever session is still running, and close every end the test opened."""
    if peer._session_task is not None:
        peer._session_task.cancel()
        await asyncio.gather(peer._session_task, return_exceptions=True)
    peer._cancel_restart_timer()
    if peer.proto is not None:
        peer.proto.close('test over')
    for each in sockets:
        each.close()


@pytest.mark.rfc('rfc4724#4.2-new-connection-ends-old-session')
@pytest.mark.rfc('rfc4724#4.2-old-session-closed-without-notification')
@pytest.mark.asyncio
async def test_a_new_connection_from_a_restarting_peer_replaces_its_session_quietly() -> None:
    """The peer restarted and we never saw its TCP session go: its new connection says so.

    It was refused with a Cease while our hold timer ran down, and that expiry then sent
    Hold Timer Expired and dropped the routes Graceful Restart is there to keep.
    """
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    theirs = await running_session(peer, negotiated, announce(negotiated, KEPT))
    old = peer.proto
    session = peer._session_task
    assert old is not None and session is not None
    replacement, connecting = accepted_connection()
    try:
        assert peer.handle_connection(replacement) is None, 'the new connection of a restarting peer was refused'
        await asyncio.sleep(0)
        assert not session.done(), 'the session ended on the TCP handshake, before any OPEN'
        assert negotiated.received_open is not None
        connecting.sendall(negotiated.received_open.pack_message(negotiated))
        await until(lambda: session.done(), 'the old session stopping')

        assert session.cancelled()
        assert peer.proto is not None and peer.proto.connection is replacement
        assert peer.proto.open_read is not None, 'the OPEN read while held was not kept for the new session'
        sent = [kind for kind, _ in negotiation_messages(received(theirs))]
        assert NOTIFICATION not in sent, f'the old session was sent a NOTIFICATION: {sent}'
        assert theirs.recv(1) == b'', 'the old TCP session was not closed'
        assert held(peer) == [KEPT], 'the routes of the restarting peer were not retained'
        assert IPV4_UNICAST in peer.neighbor.rib.incoming.restarting_families()
    finally:
        await ended(peer, theirs, connecting)


@pytest.mark.rfc('rfc4724#4.2-new-connection-ends-old-session', polarity='negative')
@pytest.mark.asyncio
async def test_a_new_connection_from_a_peer_without_graceful_restart_is_refused() -> None:
    """RFC 4271 6.8 still holds for a peer which did not advertise the capability."""
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    # the OPEN is packed when it is made, so the capability goes before, not after
    capabilities = their_capabilities(peer.neighbor)
    capabilities.pop(Capability.CODE.GRACEFUL_RESTART, None)
    plain = negotiated_session(peer.neighbor)
    plain.received(Open.make_open(Version(4), ASN(PEER_AS), HoldTime(180), RouterID('192.0.2.1'), capabilities))
    theirs = await running_session(peer, plain)
    assert peer.proto is not None and peer.proto.negotiated.received_open is not None
    assert not peer.proto.negotiated.received_open.capabilities.announced(Capability.CODE.GRACEFUL_RESTART)
    old = peer.proto
    session = peer._session_task
    assert session is not None
    replacement, connecting = accepted_connection()
    try:
        refusal = peer.handle_connection(replacement)
        assert refusal is not None, 'a new connection replaced a session without Graceful Restart'
        # bounded: a NOTIFICATION fits in one write to an empty socket buffer
        for _, _ in zip(range(100), refusal):
            pass

        refused = [(body[0], body[1]) for kind, body in await answered(connecting) if kind == 3]
        assert refused == [CONNECTION_COLLISION_RESOLUTION]
        assert peer.proto is old and old is not None and old.connection is not None
        assert not session.done()
    finally:
        await ended(peer, theirs, connecting)
        replacement.close()


# ------------------------------------------------- 3 a Restart Time inferred from the hold time


def restart_time_advertised(hold_time: int) -> int:
    """The Restart Time our OPEN carries for `graceful-restart` with no time given."""
    from exabgp.bgp.neighbor.capability import GracefulRestartConfig

    neighbor = Neighbor()
    neighbor.session.local_as = ASN(65001)
    neighbor.hold_time = HoldTime(hold_time)
    neighbor.capability.graceful_restart = GracefulRestartConfig.with_time(0)
    neighbor.infer()
    packed = Capabilities().new(neighbor, False).pack_capabilities()
    graceful = Capabilities.unpack(packed)[Capability.CODE.GRACEFUL_RESTART]
    assert isinstance(graceful, Graceful)
    return graceful.restart_time


@pytest.mark.parametrize(('hold_time', 'expected'), [(180, 180), (4095, 4095), (5000, 4095), (65535, 4095)])
def test_a_restart_time_taken_from_the_hold_time_is_capped_at_twelve_bits(hold_time: int, expected: int) -> None:
    """Unmarked: section 3 gives the field twelve bits and no keyword. A hold time of 5000
    was masked to twelve bits on the wire, which advertised a Restart Time of 904."""
    assert restart_time_advertised(hold_time) == expected


def test_a_restart_time_too_large_for_the_field_is_capped_not_masked() -> None:
    assert Graceful().set(0, 5000, []).extract_capability_bytes()[0][:2] == pack('!H', 4095)


async def a_held_connection_does_not_end_the_session(send: bytes) -> list[tuple[int, int]]:
    """A Graceful Restart session met by a connection which sends `send` and closes.

    Returns the NOTIFICATIONs that connection was answered with, as (code, subcode), after
    checking the established session and its connection were left as they were.
    """
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    theirs = await running_session(peer, negotiated, announce(negotiated, KEPT))
    old = peer.proto
    session = peer._session_task
    assert old is not None and session is not None
    replacement, connecting = accepted_connection()
    try:
        assert peer.handle_connection(replacement) is None
        contender = peer._contender_task
        assert contender is not None, 'the new connection was not held for its OPEN'
        if send:
            connecting.sendall(send)
        connecting.shutdown(socket.SHUT_WR)
        await until(lambda: contender.done(), 'the held connection being dealt with')

        assert not session.done(), 'a connection with no valid OPEN ended the established session'
        assert peer.proto is old and old.connection is not None
        assert held(peer) == [KEPT]
        assert peer.neighbor.rib.incoming.restarting_families() == set()
        return [(body[0], body[1]) for kind, body in await answered(connecting) if kind == 3]
    finally:
        await ended(peer, theirs, connecting)
        replacement.close()


@pytest.mark.rfc('rfc4724#4.2-new-connection-ends-old-session', polarity='negative')
@pytest.mark.asyncio
async def test_a_connection_which_sends_no_open_leaves_the_session_up() -> None:
    """A TCP handshake from the peer's address is not a restart of the peer."""
    assert await a_held_connection_does_not_end_the_session(b'') == []


@pytest.mark.rfc('rfc4724#4.2-new-connection-ends-old-session', polarity='negative')
@pytest.mark.asyncio
async def test_a_connection_whose_open_is_refused_leaves_the_session_up() -> None:
    """An OPEN the session would refuse, here BGP Identifier 0, is answered and changes nothing."""
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    stranger = Open.make_open(
        Version(4), ASN(PEER_AS), HoldTime(180), RouterID('0.0.0.0'), their_capabilities(peer.neighbor)
    )
    assert await a_held_connection_does_not_end_the_session(stranger.pack_message(negotiated)) == [(2, 3)]


@pytest.mark.rfc('rfc4724#4.2-new-connection-ends-old-session', polarity='negative')
@pytest.mark.rfc('rfc4271#6.8-collision-closes-one-connection')
@pytest.mark.asyncio
async def test_a_collision_held_in_opensent_does_not_replace_the_session_established_meanwhile() -> None:
    """A connection held as an OpenSent collision is not a restart of the peer.

    RFC 4724 4.2 is about a connection arriving while the session is established. One which
    arrived in OpenSent is an RFC 4271 6.8 collision, and if ours reaches Established before
    its OPEN is read, "a connection collision with an existing BGP connection that is in the
    Established state causes closing of the newly created connection". It used to replace
    the session just established, as though the peer had restarted.
    """
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    theirs = await running_session(peer, negotiated, announce(negotiated, KEPT))
    old = peer.proto
    session = peer._session_task
    assert old is not None and session is not None and negotiated.received_open is not None
    replacement, connecting = accepted_connection()
    try:
        # the connection arrives while ours is still in OpenSent, with no await in between,
        # and ours is established by the time the held connection's OPEN is read
        established = peer.fsm.state
        peer.fsm.state = FSM.OPENSENT
        assert peer.handle_connection(replacement) is None
        contender = peer._contender_task
        assert contender is not None, 'the connection was not held as a collision'
        peer.fsm.state = established
        assert peer._peer_graceful_restart() is not None, 'the peer advertised Graceful Restart'

        connecting.sendall(negotiated.received_open.pack_message(negotiated))
        await until(lambda: contender.done(), 'the held connection being dealt with')

        assert not session.done(), 'the established session was ended by a collision'
        assert peer.proto is old and old.connection is not None
        refused = [(body[0], body[1]) for kind, body in await answered(connecting) if kind == 3]
        assert refused == [CONNECTION_COLLISION_RESOLUTION]
        assert peer.neighbor.rib.incoming.restarting_families() == set()
    finally:
        await ended(peer, theirs, connecting)
        replacement.close()


async def answered(connecting: socket.socket) -> list[tuple[int, bytes]]:
    """Every BGP message sent to the peer's end of a connection, once we have closed it.

    Over TCP what was written may not have arrived yet when the session has dealt with the
    connection, so the end is read until it sees ours closed, not until it is empty.
    """
    connecting.setblocking(False)
    data = b''
    closed = False

    def arrived() -> bool:
        nonlocal data, closed
        try:
            chunk = connecting.recv(65536)
        except BlockingIOError:
            return False
        closed = not chunk
        data += chunk
        return closed

    await until(arrived, 'our end of the connection being closed')
    return negotiation_messages(data)


async def until_received(connecting: socket.socket, kinds: int) -> list[tuple[int, bytes]]:
    """Read the peer's end of a connection until `kinds` whole BGP messages have arrived."""
    data = b''

    def arrived() -> bool:
        nonlocal data
        data += received(connecting)
        return len(whole_messages(data)) >= kinds

    await until(arrived, f'{kinds} messages arriving')
    return whole_messages(data)


def whole_messages(data: bytes) -> list[tuple[int, bytes]]:
    """The complete BGP messages at the start of `data`, as (type, body)."""
    found = []
    # bounded: each message consumes at least its 19 octet header
    while len(data) >= HEADER_LENGTH:
        length = int.from_bytes(data[16:18], 'big')
        if len(data) < length:
            break
        found.append((data[18], data[HEADER_LENGTH:length]))
        data = data[length:]
    return found


OPEN = 1
KEEPALIVE = 4


@pytest.mark.rfc('rfc4724#4.2-new-connection-ends-old-session')
@pytest.mark.rfc('rfc4724#4.2-old-session-closed-without-notification')
@pytest.mark.asyncio
async def test_a_restarted_peer_waiting_for_our_open_first_replaces_its_session() -> None:
    """A restarted peer which sends its OPEN only once it has ours (DelayOpen) gets through.

    The connection is held until its OPEN is read, and nothing was sent on it: such a peer
    waited, and was dropped after bgp.openwait, on every attempt. Our OPEN now goes out on
    the held connection, and the session it becomes does not send a second one.
    """
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    theirs = await running_session(peer, negotiated, announce(negotiated, KEPT))
    session = peer._session_task
    assert session is not None and negotiated.received_open is not None
    replacement, connecting = accepted_connection()
    try:
        assert peer.handle_connection(replacement) is None
        first = await until_received(connecting, 1)
        assert [kind for kind, _ in first] == [OPEN], 'our OPEN was not sent on the held connection'
        assert not session.done(), 'the session ended before the new connection sent a valid OPEN'

        connecting.sendall(
            negotiated.received_open.pack_message(negotiated) + KeepAlive.make_keepalive().pack_message(negotiated)
        )
        await until(lambda: session.done(), 'the old session stopping')
        assert peer.proto is not None and peer.proto.connection is replacement

        await peer._establish()
        assert peer.fsm == FSM.ESTABLISHED
        after = whole_messages(received(connecting))
        assert [kind for kind, _ in after] == [KEEPALIVE], f'the new session sent {after}, a second OPEN?'
        assert held(peer) == [KEPT], 'the routes of the restarting peer were not retained'
    finally:
        await ended(peer, theirs, connecting)


@pytest.mark.rfc('rfc4724#4.2-new-connection-ends-old-session')
@pytest.mark.asyncio
async def test_mirroring_the_peer_as_reads_the_open_of_a_restarted_peer_first() -> None:
    """With no local-as our AS is the one the peer's OPEN on this connection names.

    So nothing is sent on the held connection before that OPEN is read, as on every session
    mirroring the AS, and the session sends ours once it has read it.
    """
    peer, _ = real_peer(neighbour(adj_rib_in=True))
    negotiated = graceful_session(peer.neighbor, RESTART_TIME)
    theirs = await running_session(peer, negotiated, announce(negotiated, KEPT))
    session = peer._session_task
    assert session is not None and negotiated.received_open is not None
    peer.neighbor.session.local_as = ASN(0)
    replacement, connecting = accepted_connection()
    try:
        assert peer.handle_connection(replacement) is None
        contender = peer._contender_task
        assert contender is not None
        for _ in range(10):
            await asyncio.sleep(POLL_SECONDS)
        assert received(connecting) == b'', 'an OPEN was sent before the AS it mirrors was known'
        assert not contender.done(), 'the held connection was dropped instead of read'

        connecting.sendall(negotiated.received_open.pack_message(negotiated))
        await until(lambda: session.done(), 'the old session stopping')
        assert peer.proto is not None and peer.proto.connection is replacement
        assert peer.proto.open_read is not None and peer.proto.open_sent is None
    finally:
        await ended(peer, theirs, connecting)


PARTIAL = 0x20
TRANSITIVE = 0x40


@pytest.mark.parametrize(
    'flags', [OPTIONAL | PARTIAL, OPTIONAL_EXTENDED | PARTIAL, OPTIONAL | 0x0F], ids=['0xa0', '0xb0', '0x8f']
)
@pytest.mark.rfc('rfc4724#2-other-family-end-of-rib-is-only-mp-unreach')
def test_a_marker_with_the_partial_bit_or_low_bits_set_is_still_a_marker(flags: int) -> None:
    """RFC 7606 3(c) has the Partial bit ignored on receipt, and the low four bits are unused.

    The decoder did ignore them, so the UPDATE was read as an empty MP_UNREACH_NLRI while
    the marker test refused it: the family's restart never ended on that peer's End-of-RIB.
    """
    extended = bool(flags & 0x10)
    length = pack('!H', 3) if extended else bytes([3])
    body = update_body(bytes([flags, MP_UNREACH_NLRI]) + length + AFI.ipv6.pack_afi() + SAFI.unicast.pack_safi())

    decoded = Update.unpack_message(body, from_the_peer())
    collection = UpdateCollection.unpack_message(body, from_the_peer())

    assert decoded.IS_EOR, f'the marker with flags 0x{flags:02x} was decoded as {type(decoded).__name__}'
    assert collection.IS_EOR
    assert (decoded.nlris[0].afi, decoded.nlris[0].safi) == (AFI.ipv6, SAFI.unicast)


@pytest.mark.rfc('rfc4724#2-other-family-end-of-rib-is-only-mp-unreach', polarity='negative')
def test_an_mp_unreach_marked_transitive_is_not_a_marker() -> None:
    """RFC 7606 3(c): an O/T flag conflict is malformed, so it is for the decoder, not a marker."""
    body = update_body(
        bytes([OPTIONAL | TRANSITIVE, MP_UNREACH_NLRI, 3]) + AFI.ipv6.pack_afi() + SAFI.unicast.pack_safi()
    )

    assert EOR.from_body(body) is None
