"""What qa/bin/check_tiger_style's input_assert rule does, and the two holes it has.

The rule refuses an `assert` which validates peer bytes, because -O deletes it and the
check goes with it.  It was rewritten twice in one session and neither rewrite was pinned
by anything: both were verified by planting an assert, running the gate by hand, and
reading the output.  That regresses in silence.

Every case here is one the gate got WRONG at some point, plus the two it still gets wrong
on purpose.  The known holes are asserted as holes: if one is ever closed, the test fails
and says to update the gate's docstring, so the gate cannot quietly start claiming more
than it does.
"""

import ast
import importlib.util
from pathlib import Path

import pytest

GATE = Path(__file__).resolve().parent.parent.parent / 'qa' / 'bin' / 'check_tiger_style'


def _gate():
    """Import the gate, which has no .py extension because it is run as a command."""
    spec = importlib.util.spec_from_loader(
        'check_tiger_style', importlib.machinery.SourceFileLoader('check_tiger_style', str(GATE))
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def flagged(source: str) -> list[str]:
    """The names input_assert reports for a single function's source."""
    gate = _gate()
    function = ast.parse(source).body[0]
    return [violation.detail for violation in gate.input_asserts(function, 'probe.py')]


REPORTED = [
    (
        'the parameter itself',
        'def unpack_nlri(cls, bgp):\n    assert len(bgp) >= 4\n',
    ),
    (
        'a value assigned from it',
        'def unpack_nlri(cls, bgp):\n    size = bgp[0]\n    assert size < 10\n',
    ),
    (
        'a value from a tuple unpack',
        'def unpack_nlri(cls, bgp):\n    first, rest = bgp[0], bgp[1:]\n    assert first < 10\n',
    ),
    (
        'a value two assignments away',
        'def unpack_nlri(cls, bgp):\n    size = bgp[0]\n    doubled = size * 2\n    assert doubled < 10\n',
    ),
]

ALLOWED = [
    (
        'our own class state',
        'def unpack_nlri(cls, bgp):\n    assert cls.__name__ is not None\n',
    ),
    (
        'an object whose FIELD was assigned from the wire',
        # the real case: three of these in src flagged when the rule walked whole targets,
        # and `assert isinstance(instance, HostName)` is a type invariant, not validation
        'def unpack_capability(cls, instance, data):\n    instance.hostname = data[0]\n    assert isinstance(instance, dict)\n',
    ),
    (
        'a field of a tainted object',
        # update IS derived from the wire and _parsed is a field our parser sets, so the
        # assertion is our invariant rather than a look at the peer's bytes
        'def unpack_message(cls, data):\n    update = cls.parse(data)\n    assert update._parsed is not None\n',
    ),
]


@pytest.mark.parametrize('description, source', REPORTED, ids=[name for name, _ in REPORTED])
def test_an_assert_about_peer_bytes_is_reported(description: str, source: str) -> None:
    """Peer data validated with a statement -O deletes, however far from the parameter."""
    assert flagged(source), f'an assert about {description} was not reported'


@pytest.mark.parametrize('description, source', ALLOWED, ids=[name for name, _ in ALLOWED])
def test_an_assert_about_our_own_state_is_not_reported(description: str, source: str) -> None:
    """Asserting our own invariants is wanted, and the rule must not punish it."""
    assert not flagged(source), f'an assert about {description} was reported, and should not be'


def test_the_accumulation_hole_is_still_a_hole() -> None:
    """A KNOWN hole, asserted so it cannot close without the docstring being updated.

    `labels` is never assigned FROM a tainted name, so nothing taints it and an assert
    about it is not reported, though it validates peer bytes as much as any case above.
    Derivation by assignment is covered, derivation by mutation is not.

    If this test fails, the gate got better: close the hole in its docstring too.
    """
    source = 'def unpack_nlri(cls, bgp):\n    labels = []\n    labels.append(bgp[0])\n    assert len(labels) < 5\n'
    assert not flagged(source), 'the accumulation hole has closed; update the gate docstring and delete this test'


def test_the_attribute_hole_is_still_a_hole() -> None:
    """The other KNOWN hole, and the price of letting `update._parsed` through.

    Peer data reached through a field is not reported.  That is the same rule which makes
    the third ALLOWED case pass, read the other way round, so the two cannot be separated
    without deciding which of them matters more.  Session 5.0 chose the strict reading on
    their branch, where no legitimate occurrence forces the permissive one.

    If this test fails, the gate got stricter: check `assert update._parsed is not None`
    in src/exabgp/bgp/message/update/__init__.py still passes, and update the docstring.
    """
    source = 'def unpack_nlri(cls, bgp):\n    nlri = cls.make(bgp)\n    assert len(nlri.packed) > 4\n'
    assert not flagged(source), (
        'the attribute hole has closed; check update._parsed still passes and update the docstring'
    )
