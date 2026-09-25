"""A gate which cannot run must not use the exit code that means it found something.

Three distinct outcomes, and CI can only tell them apart if the gate says which:

    0  it ran and the tree is clean
    1  it ran and found something
    2  it did not run, so believe nothing about this result

`compat_gate` already answers 2 when it cannot read the tree, and
`test_gates_are_wired.test_a_tree_it_cannot_read_is_not_reported_as_a_finding` pins that.
The other three gates did not:

    check_tests_run     a failed or empty pytest collection printed "this check proves
                        nothing" and then exited 1, which reads as a finding.
    check_sweep_floors   "collected no tests at all, which cannot be right" returned 1, and
                        so did a thinner which could not thin.
    check_exa_style     the quietest version, and the one worth stating: it had no
                        cannot-run path at all. Walking nothing leaves every rule counted
                        at zero, which prints ok for each and EXITS 0. A clean bill of
                        health over an empty walk is not a false finding, it is worse:
                        nobody investigates a green gate.

The gates compute their root from `__file__`, so copying one into an empty tree is enough
to make it unable to run without touching the real gate or the real tree.

Ported from the 5.0 branch, where `check_exa_style` is still named `check_tiger_style`.
"""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
QA_BIN = ROOT / 'qa' / 'bin'

CANNOT_RUN = 2

# Gates whose cannot-run path is reachable by giving them nothing to look at.
GATES = ('check_exa_style', 'check_tests_run', 'check_sweep_floors')

# Gates with a cheap success path which can be proved on a planted tree. check_sweep_floors
# drives pytest once per sweeping file, so a clean run of it costs about a minute and CI
# runs it directly instead.
CLEAN_GATES = ('check_exa_style', 'check_tests_run')

# check_exa_style refuses to run on a walk this small, so the planted tree has to clear its
# floor for the clean-run control below to mean anything.
PLANTED_MODULE_COUNT = 250


def copy_gates(tree: pathlib.Path, gates: tuple[str, ...]) -> None:
    (tree / 'qa' / 'bin').mkdir(parents=True)
    for name in gates:
        shutil.copy(QA_BIN / name, tree / 'qa' / 'bin' / name)


@pytest.fixture
def empty_tree(tmp_path: pathlib.Path) -> pathlib.Path:
    """A tree holding the gates and no source, so every gate is unable to run."""
    copy_gates(tmp_path, GATES)
    return tmp_path


@pytest.fixture
def clean_tree(tmp_path: pathlib.Path) -> pathlib.Path:
    """The smallest tree which gives the cheap gates a meaningful clean run."""
    copy_gates(tmp_path, CLEAN_GATES)

    tests = tmp_path / 'tests'
    tests.mkdir()
    (tests / 'test_planted.py').write_text('def test_planted():\n    pass\n')

    source = tmp_path / 'src' / 'exabgp'
    source.mkdir(parents=True)
    for number in range(PLANTED_MODULE_COUNT):
        (source / f'module_{number}.py').write_text('def nothing() -> None:\n    return None\n')

    return tmp_path


def run(gate: str, cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(pathlib.Path('qa') / 'bin' / gate)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


# ================================================== a gate which cannot run says so


@pytest.mark.parametrize('gate', GATES)
def test_it_exits_two_rather_than_one(gate: str, empty_tree: pathlib.Path) -> None:
    result = run(gate, empty_tree)

    assert result.returncode == CANNOT_RUN, (
        f'{gate} exited {result.returncode} with nothing to look at; '
        f'1 means it found something and 0 means the tree is clean.\n{result.stdout}{result.stderr}'
    )


@pytest.mark.parametrize('gate', GATES)
def test_it_says_why_rather_than_only_failing(gate: str, empty_tree: pathlib.Path) -> None:
    """An exit code with no explanation sends whoever reads CI to the wrong place."""
    result = run(gate, empty_tree)

    output = (result.stdout + result.stderr).lower()
    assert 'cannot run' in output or 'proves nothing' in output, result.stdout + result.stderr


@pytest.mark.parametrize('gate', GATES)
def test_it_did_not_crash_instead(gate: str, empty_tree: pathlib.Path) -> None:
    """An uncaught traceback also leaves a non-zero code, and means something else.

    The distinction this file exists for is between an answer and no answer. A gate which
    raises has also not answered, but it has not been designed to say so, and reading its
    code as "it exits 2" would be reading a coincidence.
    """
    result = run(gate, empty_tree)

    assert 'Traceback' not in result.stderr, result.stderr


# ============================================= the setup is real rather than vacuous


@pytest.mark.parametrize('gate', GATES)
def test_every_gate_was_copied(gate: str, empty_tree: pathlib.Path) -> None:
    assert (empty_tree / 'qa' / 'bin' / gate).is_file()


def test_the_empty_tree_really_is_empty(empty_tree: pathlib.Path) -> None:
    """With src or tests present the gates would run normally and exit 0."""
    assert not (empty_tree / 'src').exists()
    assert not (empty_tree / 'tests').exists()


@pytest.mark.parametrize('gate', CLEAN_GATES)
def test_the_same_gates_exit_zero_on_a_clean_tree(gate: str, clean_tree: pathlib.Path) -> None:
    """Otherwise exit 2 might be all these gates ever do.

    A gate hardcoded to return 2 passes every assertion above. This is the half which says
    the cannot-run path is a path rather than the destination.

    The tree is planted rather than this repository: asking check_tests_run to collect the
    whole repository from inside a unit test starts a nested pytest over tests/fuzz, which
    silently makes optional fuzz dependencies mandatory for tests/unit.
    """
    result = run(gate, clean_tree)

    assert result.returncode == 0, f'{gate}: {result.stdout}{result.stderr}'
