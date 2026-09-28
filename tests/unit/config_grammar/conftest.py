"""The environment both parsers read is the process-wide one, which other tests change.

`bgp.passive` decides whether a neighbor with a range is accepted: a test elsewhere which
leaves it set turns the refused range forms into accepted ones, and the corpus says they
are refused. Each test here starts from the default.
"""

from __future__ import annotations

import pytest

from exabgp.environment import getenv


@pytest.fixture(autouse=True)
def default_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(getenv().bgp, 'passive', False)
