"""A withdrawn FlowSpec rule must leave the switch, not only the policy directory.

ACL.insert() writes the rule file and then runs cl-acltool to load it, and ACL.clear()
runs cl-acltool once after deleting every file. ACL.remove() deleted the file and stopped
there, so the rule stayed programmed in hardware and kept dropping traffic until the next
announce or session reset happened to reload the policy directory.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from exabgp.application.flow import ACL


@pytest.fixture
def commits(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Isolate the policy directory and record every cl-acltool run."""
    recorded: list[str] = []

    class Acltool:
        """cl-acltool, as subprocess.Popen starts it: a compiled ACL calls its own _commit
        directly, so the process it runs is replaced rather than the method."""

        def __init__(self, command: list[str], **_: Any) -> None:
            assert command == ['cl-acltool', '-i']
            recorded.append('reload')

        def communicate(self) -> tuple[bytes, None]:
            return b'', None

    monkeypatch.setattr(ACL, 'path', f'{tmp_path}/')
    monkeypatch.setattr(ACL, '_known', {})
    monkeypatch.setattr(ACL, 'dry', False)
    monkeypatch.setattr(subprocess, 'Popen', Acltool)
    return recorded


def _install(uid: int, key: str) -> Path:
    """Put one rule on disk and in the table, as insert() would have left it."""
    ACL._known[key] = (uid, '[iptables]\n-A FORWARD --in-interface swp+ -j DROP\n')
    rule_file = Path(ACL._file(uid))
    rule_file.write_text(ACL._known[key][1])
    return rule_file


def test_withdraw_reloads_the_switch_acl(commits: list[str]) -> None:
    """Removing a flow must reload the ACLs, not just delete the rule file."""
    rule_file = _install(7, 'flow-under-test')

    flow: dict[str, Any] = {'string': 'flow-under-test'}
    ACL.remove(flow)

    assert not rule_file.exists(), 'the withdrawn rule file must be deleted'
    assert 'flow-under-test' not in ACL._known, 'the withdrawn flow must leave the table'
    assert commits == ['reload'], 'the switch must be told to reload after a withdraw'


def test_withdraw_of_an_unknown_flow_changes_nothing(commits: list[str]) -> None:
    """A flow we never installed must not trigger a reload."""
    rule_file = _install(9, 'flow-we-keep')

    ACL.remove({'string': 'flow-we-never-saw'})

    assert rule_file.exists(), 'an unrelated rule file must be left alone'
    assert commits == [], 'nothing changed, so the switch has nothing to reload'


def test_clear_reloads_once_for_every_flow(commits: list[str]) -> None:
    """clear() deletes each rule and reloads once, which is what remove() mirrors."""
    first = _install(11, 'flow-one')
    second = _install(12, 'flow-two')

    ACL.clear()

    assert not first.exists() and not second.exists(), 'every rule file must be deleted'
    assert commits == ['reload'], 'clear() reloads once for the whole batch'


@pytest.mark.parametrize('value', [None, '', '0', 'false', 'off', '1', 'yes', 'on', 'enable', 'TrUe'])
def test_environment_dry_run_controls_acl_installation(value: str | None, tmp_path: Path, monkeypatch) -> None:
    """Read the environment at import, then exercise whether the policy tool runs."""
    tool = tmp_path / 'cl-acltool'
    tool.write_text('#!/bin/sh\nprintf "applied\\n"\n')
    tool.chmod(0o700)
    monkeypatch.setenv('PATH', str(tmp_path))
    if value is None:
        monkeypatch.delenv('CUMULUS_FLOW_RIB', raising=False)
    else:
        monkeypatch.setenv('CUMULUS_FLOW_RIB', value)
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import json; from exabgp.application.flow import ACL; '
            'print(json.dumps([ACL.dry, ACL._commit().decode()]))',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    dry, output = json.loads(result.stdout)
    assert type(dry) is bool
    expected = value in ('1', 'yes', 'on', 'enable', 'TrUe')
    assert dry is expected
    assert output == ('' if expected else 'applied\n')
