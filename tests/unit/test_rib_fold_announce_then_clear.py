"""A route announced and cleared before any flush must not reach the peer.

This is the first step of the api-rib functional test, which announces
192.168.0.0/32 and clears the adj-rib-out in the same write, and whose .ci
records the result as "remove it so fast it was not announced". On the wire that
assertion is a race: it holds only while both commands reach the reactor before
it flushes, and it asserts the *absence* of a message, which no barrier can wait
for. Under load the announcement got out and the test failed. The property
belongs here, where the adj-rib-out can be driven directly.

Nothing reaches the peer because of two separate mechanisms, and it takes both:

  - `_del_from_rib_impl` drops the pending announcement, so none is sent, and
  - the withdrawal it queues in its place is held back by `include_withdraw`.

The second is the one worth naming. `Peer` sets `include_withdraw = False` when a
session comes up and flips it to True only once the first update generator is
exhausted, so the first batch after establishment sends no withdrawal at all.
That is right on its own terms: a peer which has just been told nothing has
nothing to withdraw. It is also what api-rib leans on without saying so, and it
is why the step is racy. Let the reactor flush the announcement first and that
batch ends, `include_withdraw` becomes True, and the clear which follows sends a
real withdrawal, so the peer sees an announce and a withdraw where the .ci
expects neither. That is exactly what a failing run reports:

    announce {'192.168.0.0/32': 1, ...}   withdraw {'192.168.0.0/32': 1, ...}

So these tests drive `messages()` with the flag the daemon would be using at that
point in the session, rather than its default.

`clear adj-rib out` reaches the RIB as `OutgoingRIB.withdraw()`, by way of
`Reactor.neighbor_rib_out_withdraw`, so that is what they call. The cache is on
because a neighbour defaults to `adj-rib-out` true, which api-rib inherits.
"""

from __future__ import annotations

from unittest.mock import Mock

from exabgp.logger.option import option

option.logger = Mock()

from exabgp.bgp.message.direction import Direction  # noqa: E402
from exabgp.bgp.message.open.asn import ASN  # noqa: E402
from exabgp.bgp.message.open.capability.negotiated import Negotiated  # noqa: E402
from exabgp.bgp.message.refresh import RouteRefresh  # noqa: E402
from exabgp.bgp.message.update import Update, UpdateCollection  # noqa: E402
from exabgp.bgp.message.update.attribute import LocalPreference, NextHop, Origin  # noqa: E402
from exabgp.bgp.message.update.attribute.collection import AttributeCollection  # noqa: E402
from exabgp.bgp.message.update.nlri.cidr import CIDR  # noqa: E402
from exabgp.bgp.message.update.nlri.inet import INET  # noqa: E402
from exabgp.bgp.neighbor import Neighbor  # noqa: E402
from exabgp.protocol.family import AFI, SAFI  # noqa: E402
from exabgp.protocol.ip import IP  # noqa: E402
from exabgp.rib.outgoing import OutgoingRIB  # noqa: E402
from exabgp.rib.route import Route  # noqa: E402

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)

BGP_MESSAGE_HEADER_SIZE = 19
BGP_MESSAGE_TYPE_UPDATE = 2

# the route api-rib announces and clears in one write
FOLDED_PREFIX = '192.168.0.0/32'
FOLDED_NEXT_HOP = '10.0.0.0'


def session() -> Negotiated:
    negotiated = Negotiated.make_negotiated(Neighbor(), Direction.IN)
    negotiated.local_as = ASN(1)
    negotiated.peer_as = ASN(1)
    negotiated.asn4 = True
    negotiated.families = [IPV4_UNICAST]
    return negotiated


def route(prefix: str = FOLDED_PREFIX, next_hop: str = FOLDED_NEXT_HOP) -> Route:
    """The same shape api-rib announces: origin igp, local-preference 100."""
    address, _, mask = prefix.partition('/')
    nlri = INET.from_cidr(CIDR.create_cidr(IP.from_string(address).pack_ip(), int(mask)), AFI.ipv4, SAFI.unicast)
    attributes = AttributeCollection()
    attributes.add(Origin.from_int(0))
    attributes.add(NextHop.from_string(next_hop))
    attributes.add(LocalPreference.from_int(100))
    return Route(nlri, attributes, nexthop=IP.from_string(next_hop))


def rib() -> OutgoingRIB:
    # a neighbour defaults to adj-rib-out true, which is what api-rib runs with
    return OutgoingRIB(cache=True, families={IPV4_UNICAST})


def flush(outgoing: OutgoingRIB) -> list[UpdateCollection]:
    """One reactor flush, the route refreshes dropped. api-rib sets group-updates false."""
    return [update for update in outgoing.updates(grouped=False) if not isinstance(update, RouteRefresh)]


def on_the_wire(
    updates: list[UpdateCollection], negotiated: Negotiated, include_withdraw: bool = True
) -> tuple[list[str], list[str]]:
    """What the peer is told, read back off the bytes rather than off the RIB.

    include_withdraw is what Peer passes: False until the first batch after the
    session came up has been sent, True from then on.
    """
    announced: list[str] = []
    withdrawn: list[str] = []
    for update in updates:
        for message in update.messages(negotiated, include_withdraw):
            assert message[BGP_MESSAGE_HEADER_SIZE - 1] == BGP_MESSAGE_TYPE_UPDATE, 'not an UPDATE'
            parsed = Update.unpack_message(message[BGP_MESSAGE_HEADER_SIZE:], negotiated).parse(negotiated)
            # an announced NLRI comes back wrapped with its next hop, a withdrawn one does not
            announced.extend(str(getattr(nlri, 'nlri', nlri)) for nlri in parsed.announces)
            withdrawn.extend(str(nlri) for nlri in parsed.withdraws)
    return announced, withdrawn


def announce_then_clear(include_withdraw: bool) -> tuple[list[str], list[str]]:
    """Both commands reach the RIB before it is flushed, as api-rib intends."""
    negotiated = session()
    outgoing = rib()

    outgoing.add_to_rib(route())
    # without this the fold has nothing to cancel and an empty flush would pass
    # the assertions below while proving nothing
    assert [str(queued.nlri) for queued in outgoing.queued_routes()] == [FOLDED_PREFIX]
    outgoing.withdraw()

    return on_the_wire(flush(outgoing), negotiated, include_withdraw)


def test_nothing_reaches_a_peer_which_has_just_come_up():
    """The api-rib assertion, in the phase api-rib runs it in."""
    announced, withdrawn = announce_then_clear(include_withdraw=False)

    assert announced == [], 'the announcement was cancelled and must not be sent'
    assert withdrawn == [], 'the peer never heard of it, so it must not be withdrawn either'


def test_the_announcement_is_folded_away_whatever_the_phase():
    announced, _ = announce_then_clear(include_withdraw=True)

    assert announced == [], 'the announcement was cancelled and must not be sent'


def test_once_withdrawals_are_flowing_the_clear_withdraws_a_route_never_announced():
    """Why the step is racy: the same fold sends a withdrawal one batch later.

    If the reactor flushes the announcement before the clear is processed, that
    first batch ends, include_withdraw becomes True, and the peer is told to drop
    a prefix it was never given.
    """
    _, withdrawn = announce_then_clear(include_withdraw=True)

    assert withdrawn == [FOLDED_PREFIX]


def test_nothing_is_left_pending_after_the_fold():
    outgoing = rib()

    outgoing.add_to_rib(route())
    outgoing.withdraw()
    flush(outgoing)

    # a second flush must not produce the announcement the first one held back
    assert flush(outgoing) == []
    assert list(outgoing.queued_routes()) == []


def test_a_clear_after_a_flush_does_withdraw():
    """The contrast case, so a fold is not confused with a RIB which sends nothing."""
    negotiated = session()
    outgoing = rib()

    outgoing.add_to_rib(route())
    announced, withdrawn = on_the_wire(flush(outgoing), negotiated, include_withdraw=False)
    assert announced == [FOLDED_PREFIX], 'the announcement should have been sent'
    assert withdrawn == []

    # the batch above is done, so Peer would have turned withdrawals back on
    outgoing.withdraw()
    announced, withdrawn = on_the_wire(flush(outgoing), negotiated, include_withdraw=True)

    assert announced == []
    assert withdrawn == [FOLDED_PREFIX], 'what the peer was told about has to be withdrawn'
