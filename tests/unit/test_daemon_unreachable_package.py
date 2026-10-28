"""A daemon started as root refuses a user who could not read the package it imports.

exabgp imports some modules only when it first needs them, and starts its helpers as the
user it drops to. Installed in a directory that user can not enter, as a venv in a 0700
directory made by `mktemp -d` is, every session was reset as soon as it was established,
with nothing logged: the compiled wheels workflow failed on Linux for that reason, where
cibuildwheel tests as root from such a venv.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from exabgp.reactor.daemon import PACKAGE, can_enter, preload, unreachable_by

OWNER = 1000
GROUP = 100
OTHER = 2000


def status(mode: int) -> os.stat_result:
    """A directory owned by OWNER and GROUP, with these permission bits."""
    return os.stat_result((0o040000 | mode, 0, 0, 2, OWNER, GROUP, 0, 0, 0, 0))


@pytest.mark.parametrize(
    ('mode', 'uid', 'gids', 'expected'),
    [
        (0o700, OWNER, set(), True),
        (0o700, OTHER, {GROUP}, False),
        (0o700, OTHER, set(), False),
        (0o710, OTHER, {GROUP}, True),
        (0o710, OTHER, set(), False),
        (0o701, OTHER, set(), True),
        # the owner is held to the owner bits, whatever the others may do
        (0o077, OWNER, {GROUP}, False),
    ],
)
def test_the_bits_of_the_user_are_the_ones_read(mode: int, uid: int, gids: set[int], expected: bool) -> None:
    assert can_enter(status(mode), uid, gids) is expected


def test_the_first_directory_the_user_can_not_enter_is_named(tmp_path: Path) -> None:
    closed = tmp_path / 'venv'
    package = closed / 'site-packages' / 'exabgp'
    package.mkdir(parents=True)
    me = os.getuid()
    assert unreachable_by(str(package), me, set()) == ''

    closed.chmod(0o600)
    try:
        assert unreachable_by(str(package), me, set()) == str(closed)
    finally:
        closed.chmod(0o755)


def test_the_package_is_the_directory_of_exabgp() -> None:
    assert Path(PACKAGE).name == 'exabgp'
    assert (Path(PACKAGE) / 'reactor').is_dir()


def test_every_module_of_the_package_is_loaded_before_the_drop() -> None:
    """A one-file binary unpacks itself where the user it drops to can not read.

    So the modules the daemon imports only once a session is up are imported first.
    """
    import sys

    assert preload() == []
    assert 'exabgp.reactor.peer.handlers' in sys.modules
    assert 'exabgp.configuration.check' in sys.modules


def test_a_zipapp_must_be_readable_not_executable(tmp_path: Path) -> None:
    """Run from a zipapp, the package is the archive: a file the user reads, never enters.

    `python3 exabgp.pyz` runs an archive with no execute bit, which the check took for a
    directory the user could not enter, and the daemon refused to drop its privileges.
    """
    archive = tmp_path / 'exabgp.pyz'
    archive.write_bytes(b'')
    me = os.getuid()

    archive.chmod(0o644)
    assert unreachable_by(str(archive), me, set()) == ''

    archive.chmod(0o300)
    try:
        assert unreachable_by(str(archive), me, set()) == str(archive)
    finally:
        archive.chmod(0o644)


def test_in_a_zipapp_the_package_is_the_archive(tmp_path: Path) -> None:
    """Imported from a zipapp, the package has no directory: its modules live in the archive.

    PACKAGE named a path inside the archive, which os.stat can not reach, and dropping the
    privileges raised instead of checking them.
    """
    import subprocess
    import sys
    import zipfile

    import exabgp

    source = Path(exabgp.__file__).parent
    archive = tmp_path / 'exabgp.pyz'
    with zipfile.ZipFile(archive, 'w') as writer:
        for module in source.rglob('*.py'):
            writer.write(module, Path('exabgp') / module.relative_to(source))

    code = 'import sys; sys.path.insert(0, sys.argv[1]); from exabgp.reactor.daemon import PACKAGE; print(PACKAGE)'
    result = subprocess.run(
        [sys.executable, '-I', '-c', code, str(archive)], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(archive)
