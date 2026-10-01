"""A comment after a value in the environment file is not part of the value.

The file was read with ConfigParser's defaults, which keep an inline comment, so
`parser = true  # comment` gave the value `true  # comment`. The boolean parser took
anything it did not know as False: the option was turned off, and nothing said so.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from exabgp.environment import base
from exabgp.environment.config import Environment


def _loaded(monkeypatch: pytest.MonkeyPatch, path: Path, text: str) -> Environment:
    path.write_text(text)
    monkeypatch.setattr(base, 'ENVFILE', str(path))
    monkeypatch.setattr(Environment, '_instance', None)
    monkeypatch.setattr(Environment, '_setup_done', False)
    for name in ('exabgp.log.parser', 'exabgp_log_parser', 'exabgp.api.respawn', 'exabgp_api_respawn'):
        monkeypatch.delenv(name, raising=False)
    Environment.setup()
    return Environment.instance()


def test_a_comment_after_a_boolean_is_ignored(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    loaded = _loaded(monkeypatch, tmp_path / 'exabgp.env', '[exabgp.log]\nparser = true  # comment\n')
    assert loaded.log.parser is True


def test_a_comment_after_false_is_still_false(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    loaded = _loaded(monkeypatch, tmp_path / 'exabgp.env', '[exabgp.api]\nrespawn = false  # comment\n')
    assert loaded.api.respawn is False
