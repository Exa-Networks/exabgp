"""RFC 5492 sections 3 and 5: refusing a peer which does not advertise a capability we need.

The ledger these tests are joined to is qa/rfc/rfc5492.toml.

`asn4 require;` in a capability block means: advertise ASN4, and end the session with an
Unsupported Capability NOTIFICATION, (2, 7), when the peer's OPEN does not carry it.  The
Data field lists what was missing, each capability encoded as in our own OPEN, and the
peering is not re-established until the operator acts.
"""

from __future__ import annotations

import asyncio
import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.notification import Notification, Notify
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.asn4 import ASN4 as ASN4Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests import negotiation

OPEN_MESSAGE_ERROR = 2
UNSUPPORTED_OPTIONAL_PARAMETER = 4
UNSUPPORTED_CAPABILITY = 7

# RFC 4271 4.2: the Optional Parameters Length octet follows the 19 octet header and the
# nine octets of version, My Autonomous System, Hold Time and BGP Identifier
OPTIONAL_PARAMETERS_LENGTH_OFFSET = 28

# How long one establishment against a scripted peer may take: each ends on the first
# message the peer sends, so this is only reached when the test is about to fail.
SESSION_SECONDS = 5.0

ASN4 = Capability.CODE.FOUR_BYTES_ASN
ROUTE_REFRESH = Capability.CODE.ROUTE_REFRESH
EXTENDED_MESSAGE = Capability.CODE.EXTENDED_MESSAGE

# What our OPEN carries for each, as <code, length, value>: local-as 65001 is 0x0000fde9
ASN4_TLV = bytes([int(ASN4), 4]) + (65001).to_bytes(4, 'big')
ROUTE_REFRESH_TLV = bytes([int(ROUTE_REFRESH), 0])
EXTENDED_MESSAGE_TLV = bytes([int(EXTENDED_MESSAGE), 0])


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def configuration(capability: str) -> Configuration:
    return Configuration(
        [
            f"""neighbor 192.0.2.1 {{
                router-id 192.0.2.2;
                local-address 192.0.2.2;
                local-as 65001;
                peer-as 65002;
                family {{ ipv4 unicast; }}
                capability {{ {capability} }}
            }}"""
        ],
        text=True,
    )


def parsed_neighbor(capability: str) -> Neighbor:
    config = configuration(capability)
    assert config.reload(), str(config.error)
    (neighbor,) = config.neighbors.values()
    return neighbor


def negotiate(neighbor: Neighbor, withheld: set[int]) -> Negotiated:
    """Our OPEN, and a peer OPEN carrying everything ours does except the withheld codes."""
    sent = Capabilities().new(neighbor, False)
    received = Capabilities()
    for code, capability in sent.items():
        if code not in withheld:
            received[code] = capability
    if ASN4 in received:
        # the peer's OPEN, not a copy of ours: RFC 6793 4.1 reads its AS from the capability
        received[ASN4] = ASN4Capability(neighbor.session.peer_as.value)
    negotiated = Negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), neighbor.session.local_as, HoldTime(90), RouterID('192.0.2.2'), sent))
    negotiated.received(
        Open.make_open(Version(4), neighbor.session.peer_as, HoldTime(90), RouterID('192.0.2.1'), received)
    )
    return negotiated


# =========================================================== configuration


@pytest.mark.parametrize(
    'name,code',
    [
        ('asn4', Capability.CODE.FOUR_BYTES_ASN),
        ('route-refresh', Capability.CODE.ROUTE_REFRESH),
        ('extended-message', Capability.CODE.EXTENDED_MESSAGE),
        ('operational', Capability.CODE.OPERATIONAL),
        ('software-version', Capability.CODE.SOFTWARE_VERSION),
        ('nexthop', Capability.CODE.NEXTHOP),
        ('link-local-nexthop', Capability.CODE.LINK_LOCAL_NEXTHOP),
    ],
)
def test_require_advertises_the_capability_and_records_it(name: str, code: int) -> None:
    neighbor = parsed_neighbor(f'{name} require;')

    assert code in neighbor.capability.required
    assert code in Capabilities().new(neighbor, False), f'{name} require did not advertise {name}'


@pytest.mark.parametrize('value', ['enable', 'disable', 'true', 'false'])
def test_enable_and_disable_require_nothing(value: str) -> None:
    neighbor = parsed_neighbor(f'asn4 {value}; route-refresh {value};')

    assert not neighbor.capability.required


def test_a_neighbor_without_a_capability_block_requires_nothing() -> None:
    neighbor = parsed_neighbor('')

    assert not neighbor.capability.required


@pytest.mark.parametrize(
    'line,wanted',
    [
        ('asn4 require-it;', "'require-it' is not valid"),
        ('multi-session require;', "'require' is not a valid boolean"),
        ('link-local-prefer require;', "'require' is not a valid boolean"),
        ('aigp require;', "'require' is not a valid boolean"),
        ('add-path require;', "'require' is not a valid add-path option"),
    ],
)
def test_require_is_refused_where_it_means_nothing(line: str, wanted: str) -> None:
    config = configuration(line)

    assert not config.reload(), f'{line} was accepted'
    assert wanted in str(config.error), str(config.error)


def test_require_changes_the_neighbor_so_a_reload_reestablishes() -> None:
    assert parsed_neighbor('asn4 require;') != parsed_neighbor('asn4 enable;')
    assert parsed_neighbor('asn4 require;') == parsed_neighbor('asn4 require;')


def test_require_survives_a_round_trip_through_the_configuration_dump() -> None:
    neighbor = parsed_neighbor('asn4 require; route-refresh enable;')

    dumped = str(neighbor)

    assert 'asn4 require;' in dumped
    assert 'route-refresh enable;' in dumped


# =========================================================== 3 and 5, the NOTIFICATION


@pytest.mark.rfc('rfc5492#3-may-refuse-a-peer-without-a-capability')
@pytest.mark.rfc('rfc5492#3-notification-must-name-the-capabilities')
@pytest.mark.rfc('rfc5492#5-data-field-lists-the-capabilities')
def test_a_missing_required_capability_is_refused_with_its_tlv_in_the_data() -> None:
    neighbor = parsed_neighbor('asn4 require;')

    notify = negotiate(neighbor, {ASN4}).unsupported_capability()

    assert notify is not None, 'a peer without a required capability was accepted'
    assert (notify.code, notify.subcode) == (OPEN_MESSAGE_ERROR, UNSUPPORTED_CAPABILITY)
    assert notify.has_defined_data
    assert notify.data == ASN4_TLV


@pytest.mark.rfc('rfc5492#3-notification-must-name-the-capabilities')
@pytest.mark.rfc('rfc5492#5-data-field-lists-the-capabilities')
def test_every_missing_capability_is_listed_and_only_those() -> None:
    neighbor = parsed_neighbor('asn4 require; route-refresh require; extended-message require;')

    notify = negotiate(neighbor, {ASN4, EXTENDED_MESSAGE}).unsupported_capability()

    assert notify is not None
    assert notify.data == ASN4_TLV + EXTENDED_MESSAGE_TLV, 'the Data field is not the missing TLVs as we sent them'


@pytest.mark.rfc('rfc5492#3-notification-must-name-the-capabilities', polarity='negative')
@pytest.mark.rfc('rfc5492#5-data-field-lists-the-capabilities', polarity='negative')
def test_a_peer_advertising_every_required_capability_is_accepted() -> None:
    """The half which finds bugs: refusing every peer also puts a TLV in every Data field."""
    neighbor = parsed_neighbor('asn4 require; route-refresh require;')

    negotiated = negotiate(neighbor, set())

    assert negotiated.unsupported_capability() is None
    assert negotiated.validate(neighbor) is None


@pytest.mark.rfc('rfc5492#3-may-refuse-a-peer-without-a-capability', polarity='negative')
def test_a_capability_enabled_but_not_required_is_not_grounds_for_refusal() -> None:
    """The MAY is taken only where the operator asked: without require the session runs."""
    neighbor = parsed_neighbor('asn4 enable; route-refresh enable;')

    assert negotiate(neighbor, {ASN4, ROUTE_REFRESH}).unsupported_capability() is None


ENHANCED_ROUTE_REFRESH = Capability.CODE.ENHANCED_ROUTE_REFRESH
ENHANCED_ROUTE_REFRESH_TLV = bytes([int(ENHANCED_ROUTE_REFRESH), 0])


def test_route_refresh_require_asks_for_both_capabilities() -> None:
    """`route-refresh` configures both capabilities: `require` requires both of the peer."""
    neighbor = parsed_neighbor('route-refresh require;')

    assert negotiate(neighbor, set()).unsupported_capability() is None
    for withheld, data in ((ROUTE_REFRESH, ROUTE_REFRESH_TLV), (ENHANCED_ROUTE_REFRESH, ENHANCED_ROUTE_REFRESH_TLV)):
        notify = negotiate(neighbor, {withheld}).unsupported_capability()
        assert notify is not None
        assert notify.data == data


def test_route_refresh_require_normal_asks_for_the_base_capability_only() -> None:
    """We advertise Enhanced Route Refresh beside it, a peer which lacks only that is fine."""
    neighbor = parsed_neighbor('route-refresh enable; route-refresh-normal require;')

    assert negotiate(neighbor, {ENHANCED_ROUTE_REFRESH}).unsupported_capability() is None
    notify = negotiate(neighbor, {ROUTE_REFRESH}).unsupported_capability()
    assert notify is not None
    assert notify.data == ROUTE_REFRESH_TLV


def test_route_refresh_require_enhanced_asks_for_the_enhanced_capability_only() -> None:
    neighbor = parsed_neighbor('route-refresh enable; route-refresh-enhanced require;')

    assert negotiate(neighbor, {ROUTE_REFRESH}).unsupported_capability() is None
    notify = negotiate(neighbor, {ENHANCED_ROUTE_REFRESH}).unsupported_capability()
    assert notify is not None
    assert notify.data == ENHANCED_ROUTE_REFRESH_TLV


def test_validate_open_raises_the_unsupported_capability() -> None:
    neighbor = parsed_neighbor('asn4 require;')
    peer, _ = negotiation.peer(neighbor)
    protocol = Protocol(peer)
    protocol.negotiated = negotiate(neighbor, {ASN4})

    with pytest.raises(Notify) as caught:
        protocol.validate_open()

    assert (caught.value.code, caught.value.subcode) == (OPEN_MESSAGE_ERROR, UNSUPPORTED_CAPABILITY)
    assert caught.value.data == ASN4_TLV


# =========================================================== a session over a real socket
#
# Peer and Protocol are compiled, and a compiled method can not be replaced, so the
# establishment is not stubbed to raise: the peer end of a socket pair answers our OPEN
# with what the test says it sent, and Peer._run() meets it the way it would on the wire.


def peer_open(neighbor: Neighbor, *, withheld: set[int] | None = None, router_id: str = '192.0.2.1') -> bytes:
    """The OPEN the peer end sends: our own capabilities less the withheld, as router_id."""
    negotiated = negotiate(neighbor, withheld or set())
    assert negotiated.received_open is not None
    capabilities = negotiated.received_open.capabilities
    received = Open.make_open(Version(4), neighbor.session.peer_as, HoldTime(90), RouterID(router_id), capabilities)
    return received.pack_message(negotiated)


def peer_notification(code: int, subcode: int) -> bytes:
    """The NOTIFICATION the peer end answers our OPEN with."""
    return Notification.make_notification(code, subcode).pack_message(negotiation.negotiated())


async def run_against(neighbor: Neighbor, answer: bytes) -> Peer:
    """Run one establishment of a peer whose far end sends answer, as a connection it accepted."""
    peer, _ = negotiation.peer(neighbor)
    protocol = Protocol(peer)
    theirs = negotiation.connect(protocol)
    try:
        # as Peer.handle_connection() does with an accepted connection: no _connect()
        peer.proto = protocol
        theirs.sendall(answer)
        # bounded: a peer which is not refused waits out its hold time for a KEEPALIVE
        await asyncio.wait_for(peer._run(), SESSION_SECONDS)
    finally:
        theirs.close()
    return peer


async def next_open(peer: Peer) -> bytes:
    """The OPEN the peer sends on its next connection, as the peer end receives it."""
    retry = Protocol(peer)
    theirs = negotiation.connect(retry)
    try:
        await retry.new_open()
        ((kind, body),) = negotiation.messages(negotiation.received(theirs))
    finally:
        theirs.close()
    assert kind == Message.CODE.OPEN, kind
    return body


# =========================================================== 3, no automatic re-establishment


@pytest.mark.rfc('rfc5492#3-terminated-peering-not-re-established')
@pytest.mark.asyncio
async def test_a_peering_refused_for_a_capability_is_not_restarted() -> None:
    neighbor = parsed_neighbor('asn4 require;')

    peer = await run_against(neighbor, peer_open(neighbor, withheld={ASN4}))

    assert not peer._restart, 'the reactor would reconnect to a peer refused for a missing capability'


@pytest.mark.rfc('rfc5492#3-terminated-peering-not-re-established', polarity='negative')
@pytest.mark.asyncio
async def test_a_peering_ended_for_another_reason_is_still_restarted() -> None:
    neighbor = parsed_neighbor('asn4 require;')

    # every capability, but an invalid BGP Identifier: refused with (2, 3)
    peer = await run_against(neighbor, peer_open(neighbor, router_id='0.0.0.0'))

    assert peer._restart, 'stopping every peer after any NOTIFICATION also passes the test above'


# =========================================================== 3, falling back to no capabilities


@pytest.mark.rfc('rfc5492#3-reconnect-without-the-capabilities-parameter')
@pytest.mark.asyncio
async def test_after_unsupported_optional_parameter_the_next_open_has_no_capabilities() -> None:
    """A pre-RFC 2842 speaker answers an OPEN carrying capabilities with (2, 4).

    The session is not stopped for it, the reactor retries, and the OPEN it retries with
    SHOULD carry no Capabilities Optional Parameter at all, or the peer refuses it again
    for ever.  What is asserted is the wire: an Optional Parameters Length of zero.
    """
    neighbor = parsed_neighbor('asn4 enable; route-refresh enable;')

    peer = await run_against(neighbor, peer_notification(OPEN_MESSAGE_ERROR, UNSUPPORTED_OPTIONAL_PARAMETER))

    assert peer._restart, 'the peering was stopped rather than retried'
    sent = await next_open(peer)
    assert sent[OPTIONAL_PARAMETERS_LENGTH_OFFSET - Message.HEADER_LEN] == 0, (
        f'the retried OPEN still carries parameters: {sent.hex()}'
    )


@pytest.mark.rfc('rfc5492#3-reconnect-without-the-capabilities-parameter', polarity='negative')
@pytest.mark.asyncio
async def test_after_another_open_error_the_next_open_still_has_its_capabilities() -> None:
    """Only (2, 4) says the Capabilities parameter was the problem."""
    neighbor = parsed_neighbor('asn4 enable; route-refresh enable;')

    peer = await run_against(neighbor, peer_notification(OPEN_MESSAGE_ERROR, 2))

    sent = await next_open(peer)
    assert sent[OPTIONAL_PARAMETERS_LENGTH_OFFSET - Message.HEADER_LEN] != 0, (
        'the capabilities were dropped over another error'
    )
