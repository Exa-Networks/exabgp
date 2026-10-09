"""`exabgp configuration validate --json` prints its answer as JSON.

A program checking a configuration (an editor, a provisioning tool) wants the position, the
message, the words expected there and what may have been meant, without parsing the text of
the `error:` line. stdout holds the JSON document only, whatever the log says.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
from typing import Any

import pytest

from exabgp.configuration.grammar.error import ConfigError

ROOT = pathlib.Path(__file__).parent.parent.parent

NEIGHBOR = """
neighbor 192.0.2.1 {
  router-id 192.0.2.2; local-as 65001; peer-as 65002; local-address 192.0.2.2;
  %s
}
"""


def validate(path: pathlib.Path, returncode: int) -> dict[str, Any]:
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    # the log is on and prints to stdout: --json must keep it out of the document
    environ['exabgp_log_enable'] = 'true'
    environ['exabgp_log_destination'] = 'stdout'
    result = subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'configuration', 'validate', '--json', str(path)],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )
    assert result.returncode == returncode, result.stdout + result.stderr
    document = json.loads(result.stdout)
    assert isinstance(document, dict)
    return document


def test_an_error_gives_its_position(tmp_path: pathlib.Path) -> None:
    conf = tmp_path / 'hold.conf'
    conf.write_text(NEIGHBOR % 'hold-time 2;')
    document = validate(conf, 1)
    assert document['configuration'] == str(conf)
    assert document['valid'] is False
    error = document['error']
    assert error['file'] == os.path.realpath(conf)
    assert (error['line'], error['column']) == (4, 13)
    assert error['message'] == 'hold-time 2 is invalid, it is 0 or at least 3 seconds'


def test_an_unknown_keyword_gives_the_expected_words(tmp_path: pathlib.Path) -> None:
    conf = tmp_path / 'typo.conf'
    conf.write_text(NEIGHBOR % 'hold-tme 30;')
    error = validate(conf, 1)['error']
    assert error['line'] == 4
    assert 'hold-time' in error['suggestions']
    assert 'hold-time' in error['expected']
    # every word expected, the text form shortens the list
    assert len(error['expected']) > 24


def test_an_error_with_no_position(tmp_path: pathlib.Path) -> None:
    conf = tmp_path / 'api.conf'
    conf.write_text(NEIGHBOR % 'api { processes [ absent ]; }')
    error = validate(conf, 1)['error']
    assert (error['file'], error['line'], error['column']) == (None, None, None)
    assert 'absent' in error['message']
    assert error['expected'] == [] and error['suggestions'] == []


def test_a_missing_file(tmp_path: pathlib.Path) -> None:
    error = validate(tmp_path / 'absent.conf', 1)['error']
    assert 'file not found' in error['message']
    assert error['line'] is None


def test_a_valid_configuration(tmp_path: pathlib.Path) -> None:
    conf = tmp_path / 'good.conf'
    conf.write_text(NEIGHBOR % 'hold-time 30;')
    assert validate(conf, 0) == {'configuration': str(conf), 'valid': True}


@pytest.mark.parametrize(
    'where,position',
    [
        ('/etc/exabgp/a.conf:4:13', ('/etc/exabgp/a.conf', 4, 13)),
        ('c:/odd:name.conf:1:2', ('c:/odd:name.conf', 1, 2)),
        ('line 3:5', (None, 3, 5)),
        ('', (None, None, None)),
    ],
)
def test_the_position_is_read_from_where(where: str, position: tuple[str | None, int | None, int | None]) -> None:
    error = ConfigError(where, 'wrong', ['a', 'b'], ['a']).as_dict()
    assert (error['file'], error['line'], error['column']) == position
    assert error == {
        'file': position[0],
        'line': position[1],
        'column': position[2],
        'message': 'wrong',
        'expected': ['a', 'b'],
        'suggestions': ['a'],
    }
