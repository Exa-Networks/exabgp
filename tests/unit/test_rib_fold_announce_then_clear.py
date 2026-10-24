"""A route announced and cleared before any flush must not reach the peer.

This is the first step of the api-rib functional test, which announces
192.168.0.0/32 and clears the adj-rib-out in the same write, and whose .msg
records the result as "remove it so fast it was not announced".  On the wire that
assertion is a race: it holds only while both commands reach the reactor before it
flushes, and it asserts the *absence* of a message, which nothing can wait for.
The property belongs here, where the adj-rib-out is driven directly.

Nothing reaches the peer because of two separate mechanisms, and it takes both:

  - `del_from_rib` drops the pending announcement, replacing it under the same
    index with a withdrawal, so no announcement is sent, and
  - that withdrawal is held back by `include_withdraw`.

The second is the one worth naming.  `Peer` sets `include_withdraw = False` when a
session comes up (`reactor/peer.py`) and flips it to True only once the first
update generator is exhausted, so the first batch after establishment sends no
withdrawal at all.  That is right on its own terms: a peer which has just been
told nothing has nothing to withdraw.  It is also what api-rib leans on without
saying so, and it is why the step is racy.  Let the reactor flush the announcement
first and that batch ends, `include_withdraw` becomes True, and the clear which
follows sends a real withdrawal, so the peer sees an announce and a withdraw where
the .msg expects neither.

`clear adj-rib out` reaches the RIB as `OutgoingRIB.withdraw()`, so that is what
these tests call.
"""

from unittest.mock import Mock

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message import Update
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.logger import log
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib.change import Change
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.protocol.ip import IP


FAMILY = (AFI.ipv4, SAFI.unicast)

# the route api-rib announces and clears in one write
FOLDED_PREFIX = '192.168.0.0/32'
FOLDED_NEXT_HOP = '10.0.0.0'


@pytest.fixture
def rib(monkeypatch):
    monkeypatch.setattr(log, 'debug', Mock())
    # a neighbour keeps an adj-rib-out, which is what api-rib runs with
    return OutgoingRIB(cache=True, families={FAMILY})


def session():
    negotiated = Negotiated({'capability': {'aigp': False}})
    negotiated.local_as = ASN(1)
    negotiated.peer_as = ASN(1)
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = [FAMILY]
    return negotiated


def route(prefix=FOLDED_PREFIX, next_hop=FOLDED_NEXT_HOP):
    """The same shape api-rib announces: origin igp, local-preference 100."""
    address, mask = prefix.split('/')
    nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
    nlri.cidr = CIDR(IP.pton(address), int(mask))
    nlri.nexthop = IP.create(next_hop)
    attributes = Attributes()
    attributes.add(Origin(Origin.IGP))
    attributes.add(LocalPreference(100))
    return Change(nlri, attributes)


def flush(outgoing, grouped=False):
    """One reactor flush, the route refreshes dropped. api-rib sets group-updates false."""
    return [update for update in outgoing.updates(grouped) if not isinstance(update, RouteRefresh)]


def on_the_wire(updates, negotiated, include_withdraw=True):
    """What the peer is told, read back off the bytes rather than off the RIB.

    include_withdraw is what Peer passes: False until the first batch after the
    session came up has been sent, True from then on.
    """
    announced = []
    withdrawn = []
    for update in updates:
        for message in update.messages(negotiated, include_withdraw):
            parsed = Update.unpack_message(message[19:], Direction.IN, negotiated)
            for nlri in parsed.nlris:
                if nlri.action == Action.WITHDRAW:
                    withdrawn.append(nlri.cidr.prefix())
                else:
                    announced.append(nlri.cidr.prefix())
    return announced, withdrawn


def announce_then_clear(outgoing, include_withdraw):
    """Both commands reach the RIB before it is flushed, as api-rib intends."""
    outgoing.add_to_rib(route())
    # without this the fold has nothing to cancel and an empty flush would pass
    # the assertions below while proving nothing
    assert [change.nlri.cidr.prefix() for change in outgoing.queued_changes()] == [FOLDED_PREFIX]
    outgoing.withdraw()

    return on_the_wire(flush(outgoing), session(), include_withdraw)


def test_nothing_reaches_a_peer_which_has_just_come_up(rib):
    """The api-rib assertion, in the phase api-rib runs it in."""
    announced, withdrawn = announce_then_clear(rib, include_withdraw=False)

    assert announced == [], 'the announcement was cancelled and must not be sent'
    assert withdrawn == [], 'the peer never heard of it, so it must not be withdrawn either'


def test_the_announcement_is_folded_away_whatever_the_phase(rib):
    announced, _ = announce_then_clear(rib, include_withdraw=True)

    assert announced == [], 'the announcement was cancelled and must not be sent'


def test_once_withdrawals_are_flowing_the_clear_withdraws_a_route_never_announced(rib):
    """Why the step is racy: the same fold sends a withdrawal one batch later."""
    _, withdrawn = announce_then_clear(rib, include_withdraw=True)

    assert withdrawn == [FOLDED_PREFIX]


def test_nothing_is_left_pending_after_the_fold(rib):
    rib.add_to_rib(route())
    rib.withdraw()
    flush(rib)

    # a second flush must not produce the announcement the first one held back
    assert flush(rib) == []
    assert list(rib.queued_changes()) == []


def test_a_clear_after_a_flush_does_withdraw(rib):
    """The contrast case, so a fold is not confused with a RIB which sends nothing."""
    negotiated = session()

    rib.add_to_rib(route())
    announced, withdrawn = on_the_wire(flush(rib), negotiated, include_withdraw=False)
    assert announced == [FOLDED_PREFIX], 'the announcement should have been sent'
    assert withdrawn == []

    # the batch above is done, so Peer would have turned withdrawals back on
    rib.withdraw()
    announced, withdrawn = on_the_wire(flush(rib), negotiated, include_withdraw=True)

    assert announced == []
    assert withdrawn == [FOLDED_PREFIX], 'what the peer was told about has to be withdrawn'
