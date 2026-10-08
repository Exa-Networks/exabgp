"""Graceful Restart and Enhanced Route Refresh each mark routes stale, and each ends its own.

RFC 4724 4.2 marks a peer's routes stale when its session is lost, and removes what it did
not send again at its End-of-RIB, its Restart Time, or the next restart. RFC 7313 4 marks
them at a BoRR and removes what was not sent again at the EoRR. The adj-rib-in kept one
stale record for both, so each end marker purged the other's routes:

- an EoRR with no BoRR before it, received from a restarted peer before its End-of-RIB,
  found the routes the restart had marked and removed them, although RFC 7313 says such an
  EoRR may be ignored and RFC 4724 keeps them until the End-of-RIB;
- a session lost in the middle of a refresh had the refresh's stale routes deleted as if
  they were left over from a previous restart, where RFC 4724 says retain them.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.rib.incoming import IncomingRIB
from tests.unit.rfc.test_rfc7313_operation import DROPPED, FAMILY, KEPT, Session, held, route


def restarted(incoming: IncomingRIB) -> None:
    """The session is lost and a new one comes up, its OPEN keeping FAMILY's forwarding state."""
    assert incoming.retain_for_restart([FAMILY]) == []
    incoming.start_session({FAMILY})


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale')
@pytest.mark.rfc('rfc7313#4-may-ignore-eorr-without-borr')
def test_an_eorr_without_a_borr_leaves_what_a_restart_retained() -> None:
    session = Session(graceful=True)
    session.announced(KEPT, DROPPED)
    restarted(session.incoming)

    session.receive(RouteRefresh.END)

    assert held(session.incoming) == sorted([KEPT, DROPPED]), 'an EoRR removed routes a restart retained'
    assert session.incoming.restarting_families() == {FAMILY}, 'the restart was ended by an EoRR'


@pytest.mark.rfc('rfc4724#4.2-remove-stale-on-end-of-rib')
def test_the_end_of_rib_still_removes_what_the_restart_retained_after_a_stray_eorr() -> None:
    session = Session(graceful=True)
    session.announced(KEPT, DROPPED)
    restarted(session.incoming)
    session.receive(RouteRefresh.END)
    session.announced(KEPT)

    removed = session.incoming.end_restart(FAMILY)

    assert [str(entry.nlri) for entry in removed] == [DROPPED]
    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc4724#4.2-retain-and-mark-stale')
def test_a_session_lost_during_a_refresh_retains_the_routes_the_refresh_marked() -> None:
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.BEGIN)
    session.announced(KEPT)

    deleted = session.incoming.retain_for_restart([FAMILY])

    assert deleted == [], f'routes stale only from a refresh were deleted: {[str(e.nlri) for e in deleted]}'
    assert held(session.incoming) == sorted([KEPT, DROPPED])


@pytest.mark.rfc('rfc4724#4.2-delete-stale-on-consecutive-restart', polarity='negative')
def test_what_a_refresh_marked_is_stale_from_the_restart_once_the_session_is_lost() -> None:
    """Retained, and then subject to the restart's own end: the End-of-RIB of the next session."""
    session = Session()
    session.announced(KEPT, DROPPED)
    session.receive(RouteRefresh.BEGIN)
    restarted(session.incoming)
    session.announced(KEPT)

    removed = session.incoming.end_restart(FAMILY)

    assert [str(entry.nlri) for entry in removed] == [DROPPED]
    assert held(session.incoming) == [KEPT]


@pytest.mark.rfc('rfc4724#4.2-delete-stale-on-consecutive-restart')
def test_a_second_restart_deletes_only_what_is_still_stale_from_the_first() -> None:
    incoming = IncomingRIB(True, {FAMILY})
    incoming.update_cache(route(KEPT))
    incoming.update_cache(route(DROPPED))
    restarted(incoming)
    incoming.update_cache(route(KEPT))

    deleted = incoming.retain_for_restart([FAMILY])

    assert [str(entry.nlri) for entry in deleted] == [DROPPED]
    assert held(incoming) == [KEPT]
