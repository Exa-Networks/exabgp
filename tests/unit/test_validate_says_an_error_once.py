"""`exabgp configuration validate` says a configuration error once.

The `error:` line on stderr was added for #1367, when the error was not shown at all with
logging off. With logging on, and printing to the terminal (the default), the log said the
same line first, so every error was printed twice. The line also named the file twice:
`<file> is not a valid config file: <file>:3:12: ...`, the error already starting with it.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).parent.parent.parent

HOLD_TIME = """
neighbor 192.0.2.1 {
  router-id 192.0.2.2; local-as 65001; peer-as 65002; local-address 192.0.2.2;
  hold-time 2;
}
"""

MESSAGE = 'hold-time 2 is invalid'


def validate(path: pathlib.Path, log: str) -> str:
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    environ['exabgp_log_enable'] = log
    result = subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'configuration', 'validate', str(path)],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    return result.stdout + result.stderr


@pytest.mark.parametrize('log', ['true', 'false'])
def test_an_error_is_said_once(tmp_path: pathlib.Path, log: str) -> None:
    conf = tmp_path / 'hold.conf'
    conf.write_text(HOLD_TIME)
    output = validate(conf, log)
    assert output.count(MESSAGE) == 1, output
    assert f'error: {conf}:4:13: {MESSAGE}' in output, output


def test_the_file_is_named_once(tmp_path: pathlib.Path) -> None:
    conf = tmp_path / 'hold.conf'
    conf.write_text(HOLD_TIME)
    # the `loading` line is printed or not depending on the log level the environment sets
    error = next(line for line in validate(conf, 'true').splitlines() if line.startswith('error: '))
    assert error.count(str(conf)) == 1, error


def test_a_missing_file_is_said_once(tmp_path: pathlib.Path) -> None:
    output = validate(tmp_path / 'absent.conf', 'true')
    assert output.count('is not an exabgp config file') == 1, output


def test_the_file_is_named_once_through_a_symlink(tmp_path: pathlib.Path) -> None:
    # the error names the real path: given another one (macOS /var is /private/var), the
    # given path was put in front of it, and the file named twice
    real = tmp_path / 'real'
    real.mkdir()
    (real / 'hold.conf').write_text(HOLD_TIME)
    (tmp_path / 'link').symlink_to(real)
    error = next(
        line for line in validate(tmp_path / 'link' / 'hold.conf', 'false').splitlines() if line.startswith('error: ')
    )
    assert 'is not a valid config file' not in error, error
    assert error.count('hold.conf') == 1, error
