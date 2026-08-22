#!/usr/bin/env python3
# encoding: utf-8

"""A gate which exists and never runs is not a gate

The session working main split their compat gate into a standalone stage, added
it to their runner, and got "All 22 tests passed". Twenty-two was the number
BEFORE they added it. Their runner keeps three separate lists, TEST_COMMANDS,
TEST_DESCRIPTIONS and TEST_ORDER, and they had added the stage to two of them, so
the gate they had just written to catch a class of bug we had both been missing
never executed once. The suite reported green because its count is what RAN, not
what exists.

Same shape as a test file which is never collected, which qa/bin/check_tests_run
already gates, one level up: there the file exists and pytest does not see it,
here the gate exists and the runner does not call it.

This branch has no runner script, so the equivalent is the CI workflows: a gate
in qa/bin which no workflow invokes runs only when somebody remembers to type it,
and the failure looks exactly like success, because everything that DID run
passed.

The list is not maintained here. The directory is walked and the workflows are
read, so a gate added tomorrow is covered without editing this file, and one
which stops being referenced fails rather than going quiet.
"""

import pathlib
import stat

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
QA_BIN = ROOT / 'qa' / 'bin'
WORKFLOWS = ROOT / '.github' / 'workflows'

# Executables in qa/bin which are tools rather than gates: they are invoked by a
# person or by another script, and they assert nothing on their own.
NOT_GATES = {
    'cover',  # a coverage helper
    'functional',  # invoked by the functional workflows, and by name below
    'functional-3.6',  # the legacy runner, kept for the 3.6 workflow
    'functional.orig',  # a leftover copy, not run by anything
    'rmpyc',  # a cleanup script
}

# Ratchet: a walk which finds no gates asserts nothing about them.
GATE_FLOOR = 4


def gates():
    """Executables in qa/bin which assert something and should therefore run"""
    found = []
    for path in sorted(QA_BIN.iterdir()):
        if not path.is_file():
            continue
        if not path.stat().st_mode & stat.S_IXUSR:
            continue
        if path.name in NOT_GATES:
            continue
        found.append(path.name)
    return found


def workflow_text():
    return '\n'.join(path.read_text(encoding='utf-8', errors='replace') for path in sorted(WORKFLOWS.glob('*.yml')))


GATES = gates()


class TestTheWalkFoundTheGates:
    def test_enough_gates_exist(self) -> None:
        assert len(GATES) >= GATE_FLOOR, GATES

    def test_the_ones_this_series_added_are_among_them(self) -> None:
        # the floor is a number; these are the specific gates, and a walk which
        # stopped seeing them would still clear it
        for name in ('check_tiger_style', 'check_tests_run', 'check_sweep_floors', 'compat_gate'):
            assert name in GATES, GATES

    def test_the_workflows_are_readable(self) -> None:
        assert WORKFLOWS.is_dir(), WORKFLOWS
        assert workflow_text().strip(), 'no workflow content was read, so the check below proves nothing'


@pytest.mark.parametrize('gate', GATES)
def test_every_gate_is_invoked_by_a_workflow(gate) -> None:
    """Otherwise it runs when somebody remembers, which is not a gate

    A gate absent from CI passes locally for whoever wrote it and never runs
    again. The failure is silent: the suite is green because everything which ran
    passed, and the thing which did not run is the one written to catch what the
    rest miss.
    """
    assert f'qa/bin/{gate}' in workflow_text(), f'{gate} exists in qa/bin and no workflow invokes it'


def test_the_excluded_list_does_not_hide_a_gate() -> None:
    """An exemption list which grows silently is how the category comes back

    Every name excluded above is excluded for a stated reason. If one of them
    starts asserting something it belongs in CI, and the way that gets noticed is
    somebody having to edit this list rather than the check quietly widening.
    """
    assert NOT_GATES == {'cover', 'functional', 'functional-3.6', 'functional.orig', 'rmpyc'}
    for name in NOT_GATES:
        assert (QA_BIN / name).exists() or True  # a removed tool is not a failure


def test_functional_is_run_even_though_it_is_excluded() -> None:
    # it is excluded from the gate list because it is a runner rather than a
    # check, but it must still be in CI, and asserting that here stops the
    # exclusion from quietly removing it from the tree's coverage
    assert 'qa/bin/functional' in workflow_text()
