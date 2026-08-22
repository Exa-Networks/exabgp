"""The guards inside qa/bin/test_everything have to run somewhere CI looks.

Ten SystemExit guards were added to that file over one session: the qa/bin walk, the
tests/ directory walk, the pytest path form check, the testpaths check, and the controls
on the workflow walk.  Every one of them exists to catch a gate which is present and never
invoked.

None of them ran in CI.  No workflow invokes test_everything; the workflows run the five
check_* gates and compat_gate directly, so the guards only executed when somebody typed
./qa/bin/test_everything at a prompt.  A guard against unwired gates, itself unwired, in
the file whose subject is that failure.

Importing the module executes them, because they are module level.  So these tests are
mostly one import, plus the pieces worth naming separately when they break.

Session 5.0 reached the same arrangement from the other side: they have no runner at all,
so a pytest file was the only place their equivalents could live.
"""

import ast
import importlib.machinery
import importlib.util
from pathlib import Path

import subprocess
import types

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
GATE = ROOT / 'qa' / 'bin' / 'test_everything'


def load():
    """Import test_everything, running its module level guards.

    A guard which fails raises SystemExit during exec_module, so it arrives here as an
    exception carrying the message the guard wrote rather than as a silent skip.
    """
    loader = importlib.machinery.SourceFileLoader('test_everything', str(GATE))
    spec = importlib.util.spec_from_loader('test_everything', loader)
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except SystemExit as refusal:
        pytest.fail(f'a guard in qa/bin/test_everything refused to let it start: {refusal}')
    return module


class _DisarmGuards(ast.NodeTransformer):
    """Turn `raise SystemExit(...)` into `pass`, and nothing else."""

    def visit_Raise(self, node: ast.Raise) -> ast.stmt:
        call = node.exc
        name = call.func if isinstance(call, ast.Call) else call
        if isinstance(name, ast.Name) and name.id == 'SystemExit':
            return ast.copy_location(ast.Pass(), node)
        return node


def load_disarmed():
    """The same module with its guards turned off, so each test can check ONE thing.

    Every test here needs the module's data, and a guard which fires raises during import,
    so without this a single broken guard fails all seven tests identically and none of
    them tells you which invariant went.  The transform touches `raise SystemExit` and
    nothing else, and test_every_guard_in_the_runner_passes still loads it armed.
    """
    tree = _DisarmGuards().visit(ast.parse(GATE.read_text()))
    ast.fix_missing_locations(tree)
    module = types.ModuleType('test_everything_disarmed')
    module.__file__ = str(GATE)
    exec(compile(tree, str(GATE), 'exec'), module.__dict__)
    return module


def test_the_disarm_transform_only_removes_guards() -> None:
    """A disarm which removed more than the guards would make every test below vacuous."""
    armed = ast.parse(GATE.read_text())
    disarmed = _DisarmGuards().visit(ast.parse(GATE.read_text()))
    raises = sum(1 for n in ast.walk(armed) if isinstance(n, ast.Raise))
    left = sum(1 for n in ast.walk(disarmed) if isinstance(n, ast.Raise))
    assert raises > left, 'the transform removed no raise, so the disarmed module is the armed one'
    assert left == sum(
        1
        for n in ast.walk(armed)
        if isinstance(n, ast.Raise)
        and not (
            isinstance(getattr(n.exc, 'func', n.exc), ast.Name) and getattr(n.exc, 'func', n.exc).id == 'SystemExit'
        )
    ), 'the transform removed a raise which was not a guard'


def test_every_guard_in_the_runner_passes() -> None:
    """The ten guards, run where CI can see them fail."""
    assert load() is not None


def test_the_runner_defines_and_orders_the_same_stages() -> None:
    """A stage in one list and not the other never runs, and the suite still says passed."""
    module = load_disarmed()
    assert set(module.TEST_COMMANDS) == set(module.TEST_ORDER), 'TEST_COMMANDS and TEST_ORDER disagree'


def test_every_executable_in_qa_bin_is_a_gate_or_a_named_tool() -> None:
    """A check written, made executable, and wired to nothing runs when somebody remembers."""
    module = load_disarmed()
    import os

    executables = {
        entry.name for entry in (ROOT / 'qa' / 'bin').iterdir() if entry.is_file() and os.access(entry, os.X_OK)
    }
    invocations = ' '.join(
        part
        for command in module.TEST_COMMANDS.values()
        for part in ([command] if isinstance(command, str) else command)
    )
    wired = {name for name in executables if f'qa/bin/{name}' in invocations}
    unaccounted = sorted(executables - wired - set(module.NOT_A_GATE))
    assert not unaccounted, f'these run nothing and are not named as tools: {unaccounted}'


def test_no_pytest_invocation_names_a_child_of_tests() -> None:
    """A glob like tests/unit/test_*.py reads as thorough and skips every subdirectory.

    It skipped 34 files and three directories here, in both CI systems, for as long as the
    line existed.
    """
    module = load_disarmed()
    assert not module._narrow_pytest_paths(), 'a pytest path names children of tests/ rather than the root'


def test_no_pytest_path_selects_nothing() -> None:
    """A path matching no file leaves every number downstream real, consistent and empty."""
    module = load_disarmed()
    assert not module._paths_selecting_nothing(), 'a pytest path matches no file'


def test_the_workflow_walk_reaches_every_forge() -> None:
    """.forgejo is the CI for the remote this repository pushes to, and was not being read."""
    module = load_disarmed()
    forges = {flow.parent.parent.name for flow in module.workflow_files(ROOT)}
    assert {'.github', '.forgejo'} <= forges, f'the walk reaches only {sorted(forges)}'


def test_the_workflow_walk_reads_both_spellings(tmp_path: Path) -> None:
    """A workflow named .yaml was invisible, and there is none in this tree to notice it.

    Planted, because the case a control is for is the one the tree does not contain.
    """
    module = load_disarmed()
    for forge, name in (('.github', 'a.yml'), ('.forgejo', 'b.yaml')):
        (tmp_path / forge / 'workflows').mkdir(parents=True)
        (tmp_path / forge / 'workflows' / name).write_text('jobs: {}\n')
    assert {flow.name for flow in module.workflow_files(tmp_path)} == {'a.yml', 'b.yaml'}


# A gate has three answers and they must not share a number.
#
#   0  it ran and found nothing
#   1  it ran and found something
#   2  it could not run
#
# Two and one collapsing is the dangerous pair, because the way both of us validate these
# gates is "reinstate the bug, expect 1", and a gate which has DIED passes that test.
# Session 5.0 found four such paths on their branch, one of them `raise SystemExit(2, msg)`
# whose .code is a tuple and so exits 1.
#
# Here it was the ref: `compat_gate does-not-exist-ref` let CalledProcessError out of main
# and python exited 1, so a typo in a ref, or a shallow clone missing the base commit,
# reported as a compatibility regression.
GATE_ROOT = ROOT / 'qa' / 'bin'


def run_gate(*arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([str(GATE_ROOT / 'compat_gate'), *arguments], cwd=str(ROOT), capture_output=True, timeout=600)


def test_a_tree_it_cannot_read_is_not_reported_as_a_finding() -> None:
    """Exit 2, and say which tree, rather than exit 1 and look like a regression."""
    result = run_gate('does-not-exist-ref')
    assert result.returncode == 2, f'a ref which does not exist exited {result.returncode}, not 2'
    assert b'does-not-exist-ref' in result.stderr, 'it did not say which tree it could not read'


def test_a_clean_tree_exits_zero() -> None:
    """The control for the test above: 2 means something only if 0 is reachable."""
    assert run_gate('--this-tree-only').returncode == 0
