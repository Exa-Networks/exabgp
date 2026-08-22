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
from struct import pack

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.qualifier.labels import Labels
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
from exabgp.bgp.message import Action
from exabgp.protocol.family import AFI, SAFI, Family
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

# resolved from this file rather than the working directory.  Path('src/exabgp') is
# relative to the CWD, and another test in the suite changes it, so the walk found nothing
# in a full run while passing when this file ran alone: the guard below is what caught it.
SOURCE_ROOT = pathlib.Path(__file__).resolve().parents[2] / 'src' / 'exabgp'

MIN_SINGLETONS_COMPARED = 8
# a ratchet on the WALK, not on the list: raise it, never lower it to make a red run green
MIN_COMPARISONS_FOUND = 18


def compared_by_identity() -> set[str]:
    """Every `x is Some.SINGLETON` this source contains, read from the source.

    A list of names goes stale the day someone adds one.  A walk does not, with one
    caveat session 5.0 paid for: a walk which resolves nothing reports success over an
    empty set, and that is a more convincing kind of nothing than the list it replaced.
    So what this returns is asserted to be non-empty, and to contain everything CARRIED
    claims, by the two tests below.
    """
    found: set[str] = set()
    for path in SOURCE_ROOT.rglob('*.py'):
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
    return found


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
    found = compared_by_identity()

    known = set(CARRIED) | set(NOT_CARRIED)
    unclassified = sorted(found - known - NOT_A_ROUTE_VALUE)
    assert not unclassified, (
        f'these are compared by identity and are neither covered nor named as uncarried: {unclassified}'
    )


def test_the_sweep_found_something_to_check() -> None:
    """A list which emptied would pass every test above."""
    assert len(CARRIED) >= MIN_SINGLETONS_COMPARED, f'only {len(CARRIED)} singletons are covered'


@pytest.mark.registry_floor
def test_the_source_walk_actually_resolves_something() -> None:
    """The walk itself, held to the same standard as everything else this series checked.

    test_every_singleton_this_codebase_compares_by_identity_is_covered subtracts what the
    walk found from what is known, so a walk which found NOTHING subtracts an empty set
    and passes.  Session 5.0 shipped exactly that shape and only their floor assertion
    caught it: fifteen green parameters over an empty list, which looks like coverage of
    a category rather than coverage of five names.
    """
    found = compared_by_identity()

    assert len(found) >= MIN_COMPARISONS_FOUND, (
        f'the source walk found only {len(found)} identity comparisons, so it is not walking anything'
    )


def test_the_walk_finds_every_singleton_this_file_claims_to_cover() -> None:
    """The list must not drift ahead of the code either.

    A name in CARRIED which nothing compares by identity any more is a test protecting an
    invariant nobody depends on, which is cheap but misleading: it says the codebase has a
    constraint it has stopped having.
    """
    found = compared_by_identity()

    stale = sorted(name for name in CARRIED if name not in found)
    assert not stale, f'CARRIED names these, and nothing compares them with `is` any more: {stale}'


def test_a_copy_keeps_its_class() -> None:
    """The property, rather than the mechanism, because the mechanism differs per class.

    A slotted class must name its slots and copying __dict__ gets it nothing; a class with
    a __dict__ must copy that and naming one attribute loses the rest.  So an assertion
    about HOW a hook copies is wrong for half the tree.  What holds either way is that a
    copy is the same class carrying the same state.

    Session 5.0 arrived at this from the opposite side: their tree has one slotted class
    and mine has ten, so the correct fix is opposite on the two branches and only the
    property survives being stated once.
    """
    for name, singleton in CARRIED.items():
        assert type(deepcopy(singleton)) is type(singleton), f'{name} deep copies to another class'
        assert type(copy(singleton)) is type(singleton), f'{name} copies to another class'

    for name, value in (
        ('a route distinguisher', RouteDistinguisher.make_from_elements('10.0.0.1', 7)),
        ('a label stack', Labels.make_labels([42], True)),
        ('a path identifier', PathInfo.make_from_integer(1)),
    ):
        for made in (copy(value), deepcopy(value)):
            assert type(made) is type(value), f'{name} copies to another class'
            assert made == value, f'{name} does not equal its copy'


DISTINGUISHER = bytes([0, 1]) + bytes([10, 0, 0, 1]) + bytes([0, 7])


def bgpls_vpn_prefix() -> bytes:
    """A BGP-LS VPN prefix, which keeps its distinguisher under route_d rather than rd."""
    body = bytes([3]) + bytes(8) + pack('!HH', 265, 4) + bytes([24, 192, 0, 2])
    return pack('!HH', 3, len(body) + 8) + DISTINGUISHER + body


# name, afi, safi, wire, whether this seed must produce a REAL distinguisher
RD_SEEDS = [
    ('ipv4 mpls-vpn', AFI.ipv4, SAFI.mpls_vpn, bytes([112, 0, 0, 0x11]) + DISTINGUISHER + bytes([10, 0, 0]), True),
    (
        'ipv6 mpls-vpn',
        AFI.ipv6,
        SAFI.mpls_vpn,
        bytes([112, 0, 0, 0x11]) + DISTINGUISHER + bytes([0x20, 0x01, 0x0D]),
        True,
    ),
    ('bgp-ls vpn', AFI.bgpls, SAFI.bgp_ls_vpn, bgpls_vpn_prefix(), True),
    ('ipv4 flow-vpn', AFI.ipv4, SAFI.flow_vpn, bytes([11]) + DISTINGUISHER + bytes([0x03, 0x81, 0x06]), True),
    ('l2vpn vpls', AFI.l2vpn, SAFI.vpls, bytes([0, 17]) + DISTINGUISHER + bytes(9), True),
    ('ipv4 flow', AFI.ipv4, SAFI.flow_ip, bytes([3, 0x03, 0x81, 0x06]), False),
]

MIN_REAL_DISTINGUISHERS = 5


def distinguisher_of(nlri: object) -> object | None:
    """BGP-LS calls it route_d and everything else calls it rd."""
    for name in ('rd', 'route_d'):
        value = getattr(nlri, name, None)
        if value is not None:
            return value
    return None


def test_every_family_which_carries_a_distinguisher_is_seeded() -> None:
    """The seed table is hand written, so what stops it drifting is this.

    Session 5.0 wrote their version of this test FROM a sweep which iterated ten families,
    and the test they committed exercised one: the family they had been looking at while
    writing it.  Copying a measurement into an assertion loses whatever the measurement got
    from iterating, and mine had the same shape, missing bgp-ls-vpn.

    Deriving the list from Family.size rather than from memory is what found it.  Structural
    inspection of the classes does NOT: BGP-LS sets route_d in __init__ as an instance
    attribute, so nothing about the class says it carries one.
    """
    declared = {(afi, safi) for (afi, safi), (_, rd_size) in Family.size.items() if rd_size}
    seeded = {(afi, safi) for _name, afi, safi, _wire, _real in RD_SEEDS}

    missing = sorted(f'{afi}/{safi}' for afi, safi in declared - seeded)
    assert not missing, f'these families declare a route distinguisher and have no seed: {missing}'


def test_nothing_builds_a_route_distinguisher_which_impersonates_NORD() -> None:
    """The `is NORD` tests are only sound while no path builds an equal-but-separate one.

    RouteDistinguisher(b'') equals NORD and is not NORD, so a route carrying one would take
    the wrong branch at every `is RouteDistinguisher.NORD` site: five here, two in the
    configuration and three in the decoders and renderers.

    Measured rather than read off the code, and the first version of this docstring is why
    that distinction matters.  It said the wire path "only builds one when the family says
    there are eight bytes to read", which is a claim about a mechanism I had read, offered
    where the next reader takes it as measured.

    What IS measured: every family and every generic fill, 7484 successful decodes, zero
    RouteDistinguisher constructions.  That cannot carry the assertion on its own, because a
    sweep which builds none proves nothing about what it builds, so the seeds reach the
    construction path and the test requires them to.

    5.0 solved the same hazard the other way, by having their copy hook canonicalise an
    equal RD TO the singleton.  Neither branch has a lookalike, so both choices are sound
    and NEITHER is load bearing; the difference should not be removed for tidiness without
    measuring what it buys on that branch.
    """
    real = 0
    singleton = 0
    for name, afi, safi, wire, must_be_real in RD_SEEDS:
        nlri, _ = NLRI.unpack_nlri(afi, safi, wire, Action.ANNOUNCE, None, None)
        rd = distinguisher_of(nlri)
        assert rd is not None, f'{name} carries no distinguisher, so it pins nothing'

        for candidate in (rd, deepcopy(rd), copy(rd)):
            assert (candidate == RouteDistinguisher.NORD) == (candidate is RouteDistinguisher.NORD), (
                f'{name} carries a route distinguisher which equals NORD without being it'
            )

        if rd is RouteDistinguisher.NORD:
            singleton += 1
            assert not must_be_real, f'{name} should carry a real distinguisher and was handed the singleton'
        else:
            real += 1

    # both halves, or the test passes by never reaching the construction path at all
    assert real >= MIN_REAL_DISTINGUISHERS, f'only {real} seeds built a real route distinguisher'
    assert singleton >= 1, 'no seed took the no-distinguisher path, which is the one handed the singleton'
