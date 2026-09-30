"""The CLI socket directory ExaBGP creates can be entered, whatever the umask.

It was created with os.makedirs(mode=0o700), which the umask filters: under exabgp's default
umask of 0o137 the directory came out 0o600, without the search bit, and binding the socket
inside it failed with EACCES.
"""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest

from exabgp.application.unixsocket import Control

EXABGP_DEFAULT_UMASK = 0o137


@pytest.fixture
def exabgp_umask() -> Iterator[None]:
    previous = os.umask(EXABGP_DEFAULT_UMASK)
    try:
        yield
    finally:
        os.umask(previous)


def test_the_socket_directory_is_created_searchable(exabgp_umask: None) -> None:
    # a short path: a unix socket path is limited to about a hundred octets
    directory = Path(os.path.realpath('/tmp')) / f'exabgp-sock-{os.getpid()}'
    control = Control(str(directory) + '/')
    try:
        assert control.init(), 'the socket could not be created'
        mode = stat.S_IMODE(os.stat(directory).st_mode)
        assert mode == 0o700, f'the socket directory is {oct(mode)}'
    finally:
        control.cleanup()
        if directory.exists():
            directory.chmod(0o700)
            for entry in directory.iterdir():
                entry.unlink()
            directory.rmdir()
