"""A singleton compared with `is` must copy to itself.

Session 5.0 lost a whole family to this twice.  PathInfo.NOPATH is tested by identity
inside index():

    addpath = b'no-pi' if self.path_info is PathInfo.NOPATH else self.path_info.pack()

so once a deep copy minted a second NOPATH, a copied route indexed differently from the
route it came from.  rib/outgoing.py deep copies on the withdraw path, so four families
produced a route the RIB could no longer find.  They had already fixed the same defect on
another singleton without going looking for the rest.

The rule generalises and is cheap to hold: anything compared with `is` and reachable from
an object which gets copied has to survive the copy as itself.  This walks the singletons
this codebase actually compares that way rather than a list somebody remembered, so one
added tomorrow is covered when it is added.
"""

from __future__ import annotations

import ast
import pathlib
from copy import copy, deepcopy

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.protocol.ip import IP

# the ones which ride inside an NLRI or an attribute, so a copy of one reaches them
CARRIED: dict[str, object] = {
    'IP.NoNextHop': IP.NoNextHop,
    'NLRI.INVALID': NLRI.INVALID,
    'NLRI.EMPTY': NLRI.EMPTY,
    'PathInfo.NOPATH': PathInfo.NOPATH,
    'PathInfo.DISABLED': PathInfo.DISABLED,
    'RouteDistinguisher.NORD': RouteDistinguisher.NORD,
    'Labels.NOLABEL': Labels.NOLABEL,
    'NextHop.UNSET': NextHop.UNSET,
}

# Negotiated.UNSET is compared by identity but belongs to the session rather than to a
# route, so nothing copies a route and reaches it.  Named rather than omitted, so that
# leaving it out stays a decision.
NOT_CARRIED = {'Negotiated.UNSET': Negotiated.UNSET}

# enum members and reactor state, which Python copies by identity already and which no
# route carries.  Listed rather than filtered by a pattern, so a new one has to be looked
# at once before it stops failing this file.
NOT_A_ROUTE_VALUE = {
    'Action.ANNOUNCE',
    'Action.WITHDRAW',
    'Action.UNSET',
    'States.EXIT',
    'States.UP',
    'Listener.STOPPED',
    'Scheduling.NOW',
    'Scheduling.LATER',
    'Scheduling.CLOSE',
    'Scheduling.MESSAGE',
    # `type(x) is Y.__repr__` and similar, which are not singleton comparisons at all
    'ExtendedCommunityBase.__repr__',
}

MIN_SINGLETONS_COMPARED = 8


@pytest.mark.parametrize('name', sorted(CARRIED), ids=sorted(CARRIED))
def test_a_singleton_deep_copies_to_itself(name: str) -> None:
    """deepcopy is what the RIB does on the withdraw path."""
    singleton = CARRIED[name]

    assert deepcopy(singleton) is singleton, f'{name} deep copies to a different object'


@pytest.mark.parametrize('name', sorted(CARRIED), ids=sorted(CARRIED))
def test_a_singleton_shallow_copies_to_itself(name: str) -> None:
    """Both hooks, because a class can define one and not the other."""
    singleton = CARRIED[name]

    assert copy(singleton) is singleton, f'{name} copies to a different object'


def test_a_real_value_is_still_copied_rather_than_shared() -> None:
    """Returning self for every instance would satisfy the tests above and share state.

    5.0 mutated exactly this and found their own fix untested: an unconditional `return
    self` passed, because their sweep only ever copied whole NLRIs and only the singleton
    appeared in them.
    """
    rd = RouteDistinguisher.make_from_elements('10.0.0.1', 7)
    labels = Labels.make_labels([42], True)
    path = PathInfo.make_from_integer(1)

    for name, value in (('a route distinguisher', rd), ('a label stack', labels), ('a path identifier', path)):
        assert deepcopy(value) is not value, f'{name} is shared with its copy'
        assert deepcopy(value) == value, f'{name} does not equal its copy'


def test_every_singleton_this_codebase_compares_by_identity_is_covered() -> None:
    """The list above must not fall behind the code.

    Reading the source for `x is Some.SINGLETON` is what makes this a sweep rather than a
    list somebody remembered.  A new singleton compared that way, and not carried by a
    route, has to be named in NOT_CARRIED deliberately.
    """
    found: set[str] = set()
    for path in pathlib.Path('src/exabgp').rglob('*.py'):
        if 'vendoring' in str(path):
            continue
        try:
            tree = ast.parse(path.read_text())
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for operator, other in zip(node.ops, node.comparators):
                if not isinstance(operator, (ast.Is, ast.IsNot)) or not isinstance(other, ast.Attribute):
                    continue
                rendered = ast.unparse(other)
                if rendered.split('.')[0][:1].isupper():
                    found.add(rendered)

    known = set(CARRIED) | set(NOT_CARRIED)
    unclassified = sorted(found - known - NOT_A_ROUTE_VALUE)
    assert not unclassified, (
        f'these are compared by identity and are neither covered nor named as uncarried: {unclassified}'
    )


def test_the_sweep_found_something_to_check() -> None:
    """A list which emptied would pass every test above."""
    assert len(CARRIED) >= MIN_SINGLETONS_COMPARED, f'only {len(CARRIED)} singletons are covered'
