"""An environment value its option refuses is reported in one line, with the reason.

`exabgp.daemon.user=''` gave a Python traceback ending in `invalid value for daemon.user : `,
the reason the option gave ("user '' is not found on this system") thrown away.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from exabgp.application.main import main
from exabgp.environment import base
from exabgp.environment.config import Environment, EnvironmentValueError


@pytest.fixture
def fresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    monkeypatch.setattr(base, 'ENVFILE', str(tmp_path / 'absent.env'))
    monkeypatch.setattr(Environment, '_instance', None)
    monkeypatch.setattr(Environment, '_setup_done', False)
    monkeypatch.delenv('exabgp_daemon_user', raising=False)
    return monkeypatch


def test_the_error_names_the_variable_and_the_reason(fresh: pytest.MonkeyPatch) -> None:
    fresh.setenv('exabgp.daemon.user', '')
    with pytest.raises(EnvironmentValueError) as caught:
        Environment.setup()
    assert str(caught.value) == "invalid value '' for exabgp.daemon.user: user '' is not found on this system"


def test_main_reports_it_without_a_traceback(fresh: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fresh.setenv('exabgp.daemon.user', '')
    with patch('sys.argv', ['exabgp', 'configuration', 'validate', 'etc/exabgp/conf-ipself6.conf']):
        assert main() == 1
    error = capsys.readouterr().err
    assert error == "error: invalid value '' for exabgp.daemon.user: user '' is not found on this system\n"
