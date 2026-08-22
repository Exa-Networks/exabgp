#!/usr/bin/env python3
# encoding: utf-8

"""A gate which cannot run must not use the exit code that means it found something

Three distinct outcomes, and CI can only tell them apart if the gate says which:

    0  it ran and the tree is clean
    1  it ran and found something
    2  it did not run, so believe nothing about this result

This was wrong in three of the four gates, found one at a time and each time after
the previous fix, which is why it is pinned here rather than remembered:

    compat_gate         SystemExit('text') exits 1, and so does SystemExit(2, 'text'),
                        because .code is a tuple in the second. Every cannot-run path
                        impersonated a finding.
    check_tests_run     a failed pytest collection, and an empty collection, both
                        returned 1.
    check_sweep_floors  'no test file reads a registry, which cannot be right'
                        returned 1.

check_tiger_style had the quietest version of it and the one worth stating: it had
no cannot-run path at all. Walking nothing leaves every rule counted at zero, which
prints ok for each and EXITS 0. So the failure mode there was not a false finding,
it was a clean bill of health over an empty walk, which nobody investigates.

The gates compute their root from __file__, so copying one into an empty tree is
enough to make it unable to run, without touching the real gate or the real tree.
That is the whole test: a gate that cannot see the code it checks must say so in
its exit code.

compat_gate is deliberately not driven here. It needs a git tag and a subprocess
per family, so exercising it costs minutes; its cannot-run paths were verified when
they were written, and the three below are the ones a change to this tree can break.
"""

import shutil
import subprocess
import sys
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
QA_BIN = ROOT / 'qa' / 'bin'

CANNOT_RUN = 2

# Gates whose cannot-run path is reachable by giving them nothing to look at.
GATES = ('check_tiger_style', 'check_tests_run', 'check_sweep_floors')


@pytest.fixture
def empty_tree(tmp_path):
    """A tree holding the gates and no source, so every gate is unable to run"""
    (tmp_path / 'qa' / 'bin').mkdir(parents=True)
    for name in GATES:
        shutil.copy(QA_BIN / name, tmp_path / 'qa' / 'bin' / name)
    return tmp_path


def run(gate, cwd):
    return subprocess.run(
        [sys.executable, str(pathlib.Path('qa') / 'bin' / gate)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


class TestAGateWhichCannotRunSaysSo:
    @pytest.mark.parametrize('gate', GATES)
    def test_it_exits_two_rather_than_one(self, gate, empty_tree) -> None:
        result = run(gate, empty_tree)
        assert result.returncode == CANNOT_RUN, (
            f'{gate} exited {result.returncode} with nothing to look at; '
            f'1 means it found something and 0 means the tree is clean.\n{result.stdout}{result.stderr}'
        )

    @pytest.mark.parametrize('gate', GATES)
    def test_it_says_why_rather_than_only_failing(self, gate, empty_tree) -> None:
        # an exit code with no explanation sends whoever reads CI to the wrong place
        result = run(gate, empty_tree)
        output = (result.stdout + result.stderr).lower()
        assert 'cannot run' in output or 'proves nothing' in output, result.stdout + result.stderr

    @pytest.mark.parametrize('gate', GATES)
    def test_it_did_not_crash_instead(self, gate, empty_tree) -> None:
        """An uncaught traceback also leaves a non-zero code, and means something else

        The distinction this file exists for is between an answer and no answer. A
        gate that raises has also not answered, but it has not been designed to say
        so, and reading its code as "it exits 2" would be reading a coincidence.
        """
        result = run(gate, empty_tree)
        assert 'Traceback' not in result.stderr, result.stderr


class TestTheSetupIsRealRatherThanVacuous:
    def test_every_gate_was_copied(self, empty_tree) -> None:
        for name in GATES:
            assert (empty_tree / 'qa' / 'bin' / name).is_file(), name

    def test_the_empty_tree_really_is_empty(self, empty_tree) -> None:
        # if src or tests existed here the gates would run normally and exit 0, and
        # every assertion above would be testing the wrong thing
        assert not (empty_tree / 'src').exists()
        assert not (empty_tree / 'tests').exists()

    def test_the_same_gates_exit_zero_on_the_real_tree(self) -> None:
        """Otherwise exit 2 might be all these gates ever do

        A gate hardcoded to return 2 passes every assertion above. This is the half
        that says the cannot-run path is a path rather than the destination.

        check_sweep_floors is excluded from this one only: it drives pytest once per
        sweeping file, so a clean run costs about a minute, and CI runs it directly.
        """
        for gate in ('check_tiger_style', 'check_tests_run'):
            result = run(gate, ROOT)
            assert result.returncode == 0, f'{gate}: {result.stdout}{result.stderr}'
