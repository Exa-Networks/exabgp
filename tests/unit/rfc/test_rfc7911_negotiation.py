"""RFC 7911 section 4 and 5: when ADD-PATH is on, and for which direction.

The decode side of RFC 7911 is covered by
tests/unit/test_addpath_path_identifier_is_consumed.py, which is what found eight
families reading the identifier as part of the NLRI. This file is the other half: the
rules that decide whether those four octets are there at all.

That decision is asymmetric and easy to get backwards. ADD-PATH is negotiated per
direction and per family, and a speaker may only SEND multiple paths for a family if it
advertised send AND the peer advertised receive. Getting it wrong in one direction does
not fail loudly: it produces an UPDATE the peer reads from the wrong offset, which is the
same damage the decode bug caused, arriving from the other end.
"""

from __future__ import annotations

from struct import pack

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated, RequirePath
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB
from exabgp.rib.route import Route
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.family import AFI, SAFI

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)

DISABLED = 0
RECEIVE = 1
SEND = 2
SEND_RECEIVE = 3


class Opened:
    """The capabilities of one OPEN, which is all RequirePath.setup reads."""

    def __init__(self, send_receive: int | None) -> None:
        self.capabilities: dict[int, AddPath] = {}
        if send_receive is not None:
            self.capabilities[Capability.CODE.ADD_PATH] = AddPath([IPV4_UNICAST], send_receive)


def negotiate(ours: int | None, theirs: int | None) -> RequirePath:
    """What the two OPENs agree, from our point of view.

    `ours` is what our own OPEN advertised and `theirs` what the peer's did. RequirePath
    calls the peer's OPEN `received_open` and ours `sent_open`.
    """
    require = RequirePath()
    require.setup(Opened(theirs), Opened(ours))
    return require


# every combination of what the two ends can say, and what RFC 7911 5 makes of it
AGREEMENTS = [
    # ours, theirs, may we send, may we receive
    (SEND_RECEIVE, SEND_RECEIVE, True, True),
    (SEND, RECEIVE, True, False),
    (RECEIVE, SEND, False, True),
    (SEND, SEND, False, False),
    (RECEIVE, RECEIVE, False, False),
    (SEND_RECEIVE, RECEIVE, True, False),
    (SEND_RECEIVE, SEND, False, True),
    (SEND, SEND_RECEIVE, True, False),
    (RECEIVE, SEND_RECEIVE, False, True),
    (DISABLED, SEND_RECEIVE, False, False),
    (SEND_RECEIVE, DISABLED, False, False),
    (None, SEND_RECEIVE, False, False),
    (SEND_RECEIVE, None, False, False),
    (None, None, False, False),
]
AGREEMENT_IDS = ['ours={} theirs={}'.format(ours, theirs) for ours, theirs, _, _ in AGREEMENTS]


@pytest.mark.rfc('rfc7911#5-send-requires-both-directions')
@pytest.mark.parametrize('ours,theirs,may_send,may_receive', AGREEMENTS, ids=AGREEMENT_IDS)
def test_sending_needs_our_send_and_their_receive(
    ours: int | None, theirs: int | None, may_send: bool, may_receive: bool
) -> None:
    """Both halves have to be present, and each half has to come from the right end.

    The table is exhaustive rather than illustrative because the failure this guards
    against is a swap: reading our own advertisement where the peer's belongs gives the
    right answer for send/receive on both sides and the wrong one for every asymmetric
    pair, which is most of this table.
    """
    require = negotiate(ours, theirs)

    assert require.send(*IPV4_UNICAST) is may_send
    assert require.receive(*IPV4_UNICAST) is may_receive


@pytest.mark.rfc('rfc7911#5-send-requires-both-directions', polarity='negative')
def test_a_peer_which_only_sends_does_not_let_us_send() -> None:
    """The case an implementation gets wrong by treating the capability as one flag.

    A peer advertising send/receive 2 is saying it will send us multiple paths. It has
    said nothing about being able to read them. If we take that as agreement and start
    prefixing our NLRI with path identifiers, the peer reads the identifier as the start
    of the NLRI and every route in the UPDATE after it is garbage.
    """
    require = negotiate(SEND_RECEIVE, SEND)

    assert not require.send(*IPV4_UNICAST), 'we would send path identifiers to a peer which never said it reads them'


@pytest.mark.rfc('rfc7911#5-extended-encoding-only-when-negotiated')
def test_a_family_which_was_not_named_is_not_enabled_by_another_which_was() -> None:
    """ADD-PATH is negotiated per family. Agreement about one says nothing about another."""
    require = RequirePath()
    require.setup(Opened(SEND_RECEIVE), Opened(SEND_RECEIVE))

    assert require.send(*IPV4_UNICAST)
    assert not require.send(AFI.ipv6, SAFI.unicast)
    assert not require.receive(AFI.ipv6, SAFI.unicast)
    assert not require.send(AFI.l2vpn, SAFI.evpn)


@pytest.mark.rfc('rfc7911#5-extended-encoding-only-when-negotiated', polarity='negative')
def test_nothing_is_enabled_when_neither_end_offered_the_capability() -> None:
    """The overwhelmingly common session, and the one a default must not break."""
    require = negotiate(None, None)

    for afi, safi in ((AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast), (AFI.ipv4, SAFI.mpls_vpn)):
        assert not require.send(afi, safi)
        assert not require.receive(afi, safi)


@pytest.mark.rfc('rfc7911#4-single-capability-instance')
def test_every_family_travels_in_one_capability() -> None:
    """RFC 7911 4: one instance of the capability carries all the AFI/SAFI pairs.

    `extract_capability_bytes` returning a list is what makes this worth asserting: a
    capability which needs to be split, as MP-BGP is, returns one element per instance,
    and ADD-PATH must not.
    """
    families = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
        (AFI.ipv4, SAFI.nlri_mpls),
        (AFI.ipv6, SAFI.nlri_mpls),
        (AFI.ipv4, SAFI.mpls_vpn),
        (AFI.ipv6, SAFI.mpls_vpn),
    ]
    capability = AddPath(families, SEND_RECEIVE)

    extracted = capability.extract_capability_bytes()

    assert len(extracted) == 1, f'ADD-PATH was split into {len(extracted)} capability instances'
    assert len(extracted[0]) == 4 * len(families), 'the single instance does not carry all six families'


@pytest.mark.rfc('rfc7911#2-identifier-uniquely-identifies-a-path')
def test_two_paths_for_one_prefix_stay_apart() -> None:
    """RFC 7911 2: (prefix, path identifier) has to identify a path on its own.

    `index()` is what the RIB stores a route under, so two paths for one prefix colliding
    there is the whole mechanism failing: the second advertisement replaces the first,
    which is exactly what ADD-PATH exists to stop.
    """
    # CIDR takes the NLRI wire form, a mask octet then only the significant bytes
    cidr = CIDR(bytes([24]) + b'\x0a\x00\x00', AFI.ipv4)

    first = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, PathInfo(bytes([0, 0, 0, 1])))
    second = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, PathInfo(bytes([0, 0, 0, 2])))
    again = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, PathInfo(bytes([0, 0, 0, 1])))

    assert first.index() != second.index(), 'two paths for one prefix share a RIB key'
    assert first.index() == again.index(), 'the same path taken twice does not land on the same key'


# ---------------------------------------------------------------------------
# Section 4, the negative side: a peer which splits the capability.

# the Capabilities optional parameter, RFC 5492 section 4
CAPABILITIES_PARAMETER = 2


def add_path_tuple(afi: AFI, safi: SAFI, send_receive: int) -> bytes:
    """One <AFI, SAFI, Send/Receive> entry of the ADD-PATH capability value."""
    return pack('!HBB', int(afi), int(safi), send_receive)


def add_path_capability(*entries: bytes) -> bytes:
    """One instance of the ADD-PATH capability TLV, carrying the entries given."""
    value = b''.join(entries)
    return bytes([Capability.CODE.ADD_PATH, len(value)]) + value


def optional_parameters(*parameters: bytes) -> bytes:
    """An OPEN optional parameter block: the one octet length, then each Capabilities
    parameter wrapping the capability TLVs it was given."""
    block = b''.join(bytes([CAPABILITIES_PARAMETER, len(tlvs)]) + tlvs for tlvs in parameters)
    return bytes([len(block)]) + block


IPV6_ENTRY = add_path_tuple(AFI.ipv6, SAFI.unicast, SEND)
IPV4_ENTRY = add_path_tuple(AFI.ipv4, SAFI.unicast, RECEIVE)

SPLIT_LAYOUTS = {
    'two instances in one parameter': optional_parameters(
        add_path_capability(IPV4_ENTRY) + add_path_capability(IPV6_ENTRY)
    ),
    'one instance in each of two parameters': optional_parameters(
        add_path_capability(IPV4_ENTRY), add_path_capability(IPV6_ENTRY)
    ),
}


@pytest.mark.rfc('rfc7911#4-single-capability-instance', polarity='negative')
@pytest.mark.parametrize('packed', list(SPLIT_LAYOUTS.values()), ids=list(SPLIT_LAYOUTS))
def test_a_peer_which_splits_add_path_across_instances_loses_no_family(packed: bytes) -> None:
    """The peer broke the MUST, and we survive it by merging rather than by overwriting.

    Section 4 is a rule for the sender, and the damage a receiver can do with a split
    capability is quiet: `Capabilities` is a dict keyed by capability code, so a second
    instance which replaced the first would leave IPv4 negotiated as off while the peer
    believes it is on, and the path identifiers it sends would be read as the start of
    the prefix.  `AddPath.unpack_capability` is handed the instance already decoded and
    extends it, so each family keeps the direction the peer gave it.
    """
    received = Opened(None)
    received.capabilities = Capabilities.unpack(packed)

    capability = received.capabilities[Capability.CODE.ADD_PATH]
    assert isinstance(capability, AddPath)
    assert dict(capability) == {IPV4_UNICAST: RECEIVE, (AFI.ipv6, SAFI.unicast): SEND}, (
        f'the second ADD-PATH instance did not merge with the first: {dict(capability)}'
    )

    require = RequirePath()
    require.setup(received, Opened(SEND_RECEIVE))
    assert require.send(*IPV4_UNICAST), 'the family in the first instance was lost'


# ---------------------------------------------------------------------------
# Section 2: re-advertisement.  A gap, because exabgp re-advertises nothing on its own.
#
# The closest real path is the one an API helper forwarding routes between neighbours
# takes: a route decoded off one session, exactly as reactor/protocol.py decodes it, and
# handed to the outgoing RIB of another.  That route keeps the Path Identifier its
# original sender chose, which was only ever unique on the session it arrived on.

LOCAL_AS = 65001
TARGET_AS = 64998
OUR_ADDRESS = '192.0.2.254'
TARGET = '192.0.2.2'
SOURCES = {'192.0.2.1': 64999, '192.0.2.3': 64997}

ORIGIN_IGP = bytes([0x40, 0x01, 0x01, 0x00])
NEXT_HOP = bytes([0x40, 0x03, 0x04, 192, 0, 2, 1])
PREFIX_10_0_0_0_24 = bytes([24, 10, 0, 0])


@pytest.fixture
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    """RIB keeps a process wide cache keyed by neighbour name; tests must not share it."""
    monkeypatch.setattr(RIB, '_cache', {})


def add_path_neighbour(address: str, peer_as: int) -> Neighbor:
    """A neighbour with ADD-PATH send/receive for IPv4 unicast, from the real parser."""
    text = f"""
neighbor {address} {{
    router-id {OUR_ADDRESS};
    local-address {OUR_ADDRESS};
    local-as {LOCAL_AS};
    peer-as {peer_as};
    capability {{ add-path send/receive; }}
    add-path {{ ipv4 unicast; }}
    family {{ ipv4 unicast; }}
}}
"""
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    parsed: Neighbor = next(iter(configuration.neighbors.values()))
    return parsed


def established(neighbor: Neighbor, peer_as: int) -> Negotiated:
    """Run the real OPEN negotiation against a peer which offered what we did."""
    sent = Capabilities().new(neighbor, False, local_as=ASN(LOCAL_AS))
    negotiated = Negotiated.make_negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), ASN(LOCAL_AS), HoldTime(180), RouterID(OUR_ADDRESS), sent))
    negotiated.received(Open.make_open(Version(4), ASN(peer_as), HoldTime(180), RouterID(TARGET), Capabilities(sent)))
    assert negotiated.required(*IPV4_UNICAST), 'ADD-PATH was not negotiated in both directions'
    return negotiated


def received(address: str, peer_as: int, path_id: int) -> UpdateCollection:
    """10.0.0.0/24 as `address` sends it, with the Path Identifier it chose, decoded."""
    session = established(add_path_neighbour(address, peer_as), peer_as)
    attributes = ORIGIN_IGP + bytes([0x40, 0x02, 0x06, 0x02, 0x01]) + pack('!L', peer_as) + NEXT_HOP
    nlri = pack('!L', path_id) + PREFIX_10_0_0_0_24
    message = Update.unpack_message(pack('!H', 0) + pack('!H', len(attributes)) + attributes + nlri, session)
    assert isinstance(message, Update)
    return message.parse(session)


def readvertised_identifiers(path_ids: dict[str, int]) -> list[bytes]:
    """The Path Identifiers the target is sent, once handed each source's route."""
    target = add_path_neighbour(TARGET, TARGET_AS)
    session = established(target, TARGET_AS)
    for address, path_id in path_ids.items():
        learned = received(address, SOURCES[address], path_id)
        assert learned.announces, f'the UPDATE from {address} carried no route'
        for routed in learned.announces:
            target.rib.outgoing.add_to_rib(Route(routed.nlri, learned.attributes, routed.nexthop))

    identifiers: list[bytes] = []
    for update in target.rib.outgoing.updates(True, None, session):
        if not isinstance(update, UpdateCollection) or not update.announces:
            continue
        for wire in update.messages(session):
            message = Update.unpack_message(wire[19:], session)
            assert isinstance(message, Update)
            identifiers.extend(bytes(routed.nlri.path_info.pack_path()) for routed in message.parse(session).announces)
    return identifiers


@pytest.mark.usefixtures('isolated_ribs')
def test_two_received_paths_with_different_identifiers_both_reach_the_target() -> None:
    """The control for the xfail below: two paths do travel, when their senders happened
    to pick different identifiers.  Without it the xfail could be failing for want of
    plumbing, and the day identifiers were generated nobody would be told."""
    identifiers = readvertised_identifiers({'192.0.2.1': 1, '192.0.2.3': 2})

    assert sorted(identifiers) == [pack('!L', 1), pack('!L', 2)]


@pytest.mark.usefixtures('isolated_ribs')
@pytest.mark.rfc('rfc7911#2-readvertise-generates-own-identifier')
@pytest.mark.xfail(
    strict=True,
    raises=AssertionError,
    reason='a re-advertised route keeps the Path Identifier its sender chose, so two paths '
    'from two peers which both picked 1 go out to the third as the same path',
)
def test_a_readvertised_path_carries_an_identifier_we_chose() -> None:
    """Identifiers are unique per session, not globally: two peers may both call their
    path 1.  Passed on as received, the second replaces the first at the peer we send
    them to, which is the loss of path ADD-PATH exists to prevent.  Generating our own
    identifier is what keeps them two paths."""
    identifiers = readvertised_identifiers({'192.0.2.1': 1, '192.0.2.3': 1})

    assert len(identifiers) == 2, f'expected two paths to be sent, got {len(identifiers)}'
    assert len(set(identifiers)) == 2, f'two different paths were sent under one identifier: {identifiers}'
