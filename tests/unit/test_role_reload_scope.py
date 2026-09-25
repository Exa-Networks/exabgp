#!/usr/bin/env python3
# encoding: utf-8
"""test_role_reload_scope.py

Which of the three role settings restart a BGP session on reload.

Reactor.reload() calls reestablish() on any neighbour whose Neighbor.__eq__()
says it changed, so that comparison is the whole of the restart policy. `local`
and `strict` change the OPEN and must restart. `add-meta` changes nothing that
was negotiated, and restarting a session to change a JSON key would be absurd,
so it must compare equal.

These tests exist because the specification originally said to compare all of
them, which would have made `add-meta disable` bounce BGP. There used to be a
fourth, `otc`; RFC 9234 section 5 forbids the operator that switch and it was
removed in 6.0.0.

Created for ExaBGP testing framework
License: 3-clause BSD
"""

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.neighbor import Neighbor
from exabgp.protocol.ip import IP


def _neighbor() -> Neighbor:
    neighbor = Neighbor()
    neighbor.session.peer_address = IP.from_string('192.0.2.1')
    neighbor.session.local_address = IP.from_string('192.0.2.2')
    neighbor.session.local_as = ASN(65001)
    neighbor.session.peer_as = ASN(65002)
    return neighbor


def test_two_identical_neighbours_compare_equal() -> None:
    """The baseline the rest of this file leans on."""
    assert _neighbor() == _neighbor()


def test_changing_the_local_role_restarts_the_session() -> None:
    """The role travels in the OPEN, so a new one needs a new OPEN."""
    before, after = _neighbor(), _neighbor()
    before.session.role = RoleValue.PROVIDER
    after.session.role = RoleValue.CUSTOMER
    assert before != after


def test_adding_a_role_restarts_the_session() -> None:
    before, after = _neighbor(), _neighbor()
    after.session.role = RoleValue.PROVIDER
    assert before != after


def test_removing_a_role_restarts_the_session() -> None:
    """Role 0 is provider. A comparison written with truthiness would miss this."""
    before, after = _neighbor(), _neighbor()
    before.session.role = RoleValue.PROVIDER
    after.session.role = RoleValue.NO_ROLE
    assert before != after


def test_changing_strict_restarts_the_session() -> None:
    """Strict decides whether a missing remote capability rejects the session,
    which is decided while processing the OPEN."""
    before, after = _neighbor(), _neighbor()
    before.session.role = RoleValue.PROVIDER
    after.session.role = RoleValue.PROVIDER
    after.session.role_strict = True
    assert before != after


def test_changing_add_meta_does_not_restart_the_session() -> None:
    """It gates a group in the API output and nothing else."""
    before, after = _neighbor(), _neighbor()
    before.session.role = RoleValue.PROVIDER
    after.session.role = RoleValue.PROVIDER
    after.session.role_add_meta = False
    assert before == after


def test_a_live_setting_changing_alongside_a_restart_one_still_restarts() -> None:
    """`strict` deciding a restart is not weakened by `add-meta` moving with it."""
    before, after = _neighbor(), _neighbor()
    before.session.role = RoleValue.PROVIDER
    after.session.role = RoleValue.PROVIDER
    after.session.role_strict = True
    after.session.role_add_meta = False
    assert before != after
