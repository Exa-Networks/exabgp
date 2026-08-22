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


def workflow_files(root=None):
    """Every CI workflow file, whichever forge directory holds it

    Hardcoding .github/workflows/*.yml is two assumptions wearing one path. The
    session working main had a .forgejo directory holding the CI that runs on
    their primary remote, fixed the .github copy, watched their gate go green and
    reported the glob closed: the gate confirmed the half it could see and was
    silent about the half it could not.

    There is no second forge directory here, so this walk finds exactly what the
    hardcoded path did. The extension is the live half: this globbed *.yml only,
    so a workflow named unit-testing.yaml would have been invisible today.

    Because the walk resolves one directory, it gets a positive control below
    rather than being trusted for finding what it already knew about.
    """
    found = []
    for directory in sorted((root or ROOT).iterdir()):
        if not directory.is_dir() or not directory.name.startswith('.'):
            continue
        workflows = directory / 'workflows'
        if not workflows.is_dir():
            continue
        found.extend(sorted(path for path in workflows.iterdir() if path.suffix in ('.yml', '.yaml')))
    return found


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
    return '\n'.join(path.read_text(encoding='utf-8', errors='replace') for path in workflow_files())


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


# Ratchet: a walk which finds no test directories asserts nothing about them.
TEST_DIRECTORY_FLOOR = 4


def test_directories():
    """Directories under tests/ which hold files pytest collects"""
    found = []
    for path in sorted((ROOT / 'tests').iterdir()):
        if not path.is_dir() or path.name.startswith('_'):
            continue
        if any(path.glob('test_*.py')):
            found.append(path.name)
    return found


TEST_DIRECTORIES = test_directories()


def shell_sources():
    """Every place a SHELL runs pytest: the workflows, and the scripts in qa/bin

    Reading only .github/workflows leaves a hole the size of the repository. On
    this branch qa/bin/cover held

        pytest --cov --cov-reset --cov-report=html ./tests/*_test.py

    which names a child of tests/, and which matched NOTHING, because this tree
    names files test_*.py and that glob wants *_test.py. It had been reporting
    coverage over zero tests. It cleared the check below by not being read, and it
    cleared the walk above by being in NOT_GATES as a helper. Excluded twice, for
    two good reasons, adding up to invisible.

    Reported by the session working main, whose form check had the same boundary
    and whose local stages sat outside it.

    Python files are deliberately not read. check_sweep_floors and check_tests_run
    invoke pytest per file on purpose, and that is what they are for, so scanning
    them would flag the tools rather than the pipeline.
    """
    sources = [
        (str(path.relative_to(ROOT)), path.read_text(encoding='utf-8', errors='replace')) for path in workflow_files()
    ]
    for path in sorted(QA_BIN.iterdir()):
        if not path.is_file():
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        if text.startswith('#!') and 'python' in text.splitlines()[0]:
            continue
        sources.append((f'qa/bin/{path.name}', text))
    return sources


def pytest_invocations():
    """(source, path) for every path argument a shell passes to pytest"""
    found = []
    for name, text in shell_sources():
        for line in text.splitlines():
            if 'pytest' not in line or line.lstrip().startswith('#'):
                continue
            for word in line.split():
                if word.startswith('./tests') or word.startswith('tests/'):
                    found.append((name, word))
    return found


class TestEveryTestDirectoryIsActuallyRun:
    """Collected is not run, which check_tests_run cannot tell you

    check_tests_run asks whether pytest COLLECTS a file. A file in a directory no
    workflow ever names collects perfectly well and never executes, so the gate is
    green for exactly the files whose failures nobody will see.

    The session working main hit the live version: tests/async_debug had been
    calling INET(action=...) and reading rib._refresh_changes since the
    packed-bytes-first refactor, both long gone. Two independent greens covered for
    it. No stage named the directory, so it never ran, and check_tests_run was
    green because those files collect fine right up until they execute.

    Here the same hole existed and happened to be empty: tests/integration (16) and
    tests/performance (59) were named by no workflow. Both passed when finally run,
    which is luck rather than a gate, and is the reason this is asserted now rather
    than after they rot.

    The fix was structural rather than a longer list. The workflows named
    ./tests/unit/test_*.py ./tests/fuzz/test_*.py, and a hand-typed enumeration of
    a tree's children is what goes stale when the tree grows. They now name ./tests,
    so a directory added tomorrow runs without anybody remembering to edit CI, and
    this test says so rather than trusting it.

    Deliberately in the same file as the qa/bin check above. Those were two gaps
    with one shape which did not see each other: a gate which exists and is not
    invoked, and a test which is collected and is not run. Kept apart they get
    re-derived one at a time.
    """

    def test_the_walk_found_the_directories(self) -> None:
        assert len(TEST_DIRECTORIES) >= TEST_DIRECTORY_FLOOR, TEST_DIRECTORIES

    def test_the_ones_that_were_unwired_are_among_them(self) -> None:
        # the floor is a number; a walk which stopped seeing these would clear it
        for name in ('unit', 'fuzz', 'integration', 'performance'):
            assert name in TEST_DIRECTORIES, TEST_DIRECTORIES

    def test_a_workflow_passes_pytest_a_path_at_all(self) -> None:
        assert pytest_invocations(), 'no workflow invokes pytest with a path, so the check below proves nothing'

    @pytest.mark.parametrize('directory', TEST_DIRECTORIES)
    def test_some_workflow_runs_it(self, directory) -> None:
        covered = [
            path
            for _source, path in pytest_invocations()
            if path.rstrip('/') in ('./tests', 'tests') or f'tests/{directory}' in path
        ]
        assert covered, f'tests/{directory} holds tests and no workflow pytest invocation reaches it'


class TestNoWorkflowNamesAChildOfTests:
    """The shape, not today's contents, because the shape is what goes stale

    The check above asks whether each directory is reached. It accepts a path
    which names that directory, and that is not enough, because

        pytest ./tests/unit/test_*.py

    reaches tests/unit and DOES NOT RECURSE. Eight files here were outside the
    old invocation and one of them, tests/unit/reactor/api/response/
    test_json_update.py, holds 22 tests on the JSON API response encoder, which
    is the subject of the advisory this whole series came from. It passed. CI had
    simply never run it.

    So my own gate had the defect it was written to catch: a directory-reached
    check reads as thorough while a glob under it silently skips a subtree. The
    session working main found this on their side first, 34 files and 4341 of
    5193 tests, and their suggestion is what this asserts: do not check that the
    list is right today, refuse the list.

    Naming ./tests and nothing else is the only form with no stale enumeration in
    it, at any depth. A file added tomorrow in a directory invented tomorrow runs
    without anybody editing CI, which is the property, rather than the current
    paths being correct.
    """

    def test_pytest_is_given_a_path_at_all(self) -> None:
        assert pytest_invocations(), 'nothing to check, so the assertions below prove nothing'

    def test_every_invocation_names_the_tree_itself(self) -> None:
        children = [
            f'{source}: {path}' for source, path in pytest_invocations() if path.rstrip('/') not in ('./tests', 'tests')
        ]
        assert not children, (
            f'these run pytest over part of tests/ rather than all of it: {children}. '
            'A glob does not recurse and a list does not grow; name ./tests instead'
        )

    def test_every_path_given_to_pytest_selects_something(self) -> None:
        """The half being a child of tests/ only catches by accident

        qa/bin/cover asked for ./tests/*_test.py. That is a child, so the check
        above catches it, but it is ALSO a glob which matches zero files, because
        this tree names them test_*.py. Those are two defects and only one of them
        is about recursion: the second would survive somebody rewriting the form
        check, and it is the one that made the coverage report a silent zero
        rather than a partial.

        A path which selects nothing is the worst failure available here, because
        every downstream number is real, consistent, and about nothing.
        """
        empty = []
        for source, path in pytest_invocations():
            selected = list(ROOT.glob(path.lstrip('./'))) if '*' in path else [ROOT / path.lstrip('./')]
            if not [entry for entry in selected if entry.exists()]:
                empty.append(f'{source}: {path}')
        assert not empty, f'these pytest paths match no file at all: {empty}'

    def test_the_recursive_and_non_recursive_file_counts_differ(self) -> None:
        """Otherwise this file is asserting a distinction the tree cannot show

        If every test file sat directly in tests/unit and tests/fuzz, a glob and a
        walk would agree, the check above would be untestable here, and it would
        go quietly wrong the day somebody added the first subdirectory.
        """
        tests_dir = ROOT / 'tests'
        walked = list(tests_dir.rglob('test_*.py'))
        globbed = list(tests_dir.glob('unit/test_*.py')) + list(tests_dir.glob('fuzz/test_*.py'))
        assert len(walked) > len(globbed), (
            f'walk found {len(walked)} and the old glob {len(globbed)}: with no subtree to miss, '
            'the check above cannot fail here and proves nothing'
        )

    def test_the_json_response_subtree_is_among_the_ones_a_glob_misses(self) -> None:
        # named rather than counted: the count above is satisfied by any subtree,
        # and this is the one whose absence from CI actually mattered
        missed = ROOT / 'tests' / 'unit' / 'reactor' / 'api' / 'response' / 'test_json_update.py'
        assert missed.exists(), missed
        assert missed not in list((ROOT / 'tests').glob('unit/test_*.py'))


class TestTheWorkflowWalkItself:
    """A walk which resolves one directory is trusted, not tested

    Everything above reads whatever workflow_files() returns. On this branch that
    is one directory and one extension, so the walk agreeing with the hardcoded
    path it replaced says nothing about the cases it was widened for.
    """

    def test_it_finds_the_real_workflows(self) -> None:
        names = [path.name for path in workflow_files()]
        assert names, 'no workflow file found at all, so every check above reads an empty string'
        assert 'unit-testing.yml' in names, names

    def test_it_reads_a_second_forge_directory(self, tmp_path) -> None:
        # the defect on main: .forgejo held the CI that runs on their primary
        # remote, their check globbed .github, and fixing the visible half went
        # green while the half that actually runs stayed broken
        for forge, name in (('.forgejo', 'ci.yaml'), ('.github', 'ci.yml')):
            (tmp_path / forge / 'workflows').mkdir(parents=True)
            (tmp_path / forge / 'workflows' / name).write_text('pytest ./tests\n', encoding='utf-8')
        found = [f'{path.parent.parent.name}/{path.name}' for path in workflow_files(tmp_path)]
        assert found == ['.forgejo/ci.yaml', '.github/ci.yml'], found

    def test_it_reads_the_yaml_spelling(self, tmp_path) -> None:
        # the half that IS live here: the previous glob was *.yml, so a workflow
        # named unit-testing.yaml was invisible on this branch today
        (tmp_path / '.github' / 'workflows').mkdir(parents=True)
        (tmp_path / '.github' / 'workflows' / 'unit-testing.yaml').write_text('pytest ./tests\n', encoding='utf-8')
        assert [path.name for path in workflow_files(tmp_path)] == ['unit-testing.yaml']

    def test_it_ignores_a_directory_which_is_not_a_forge(self, tmp_path) -> None:
        # the widening must not start reading anything that happens to be named
        # workflows: only a dot directory holding one counts
        (tmp_path / 'docs' / 'workflows').mkdir(parents=True)
        (tmp_path / 'docs' / 'workflows' / 'guide.yml').write_text('pytest ./tests/unit\n', encoding='utf-8')
        assert workflow_files(tmp_path) == []
