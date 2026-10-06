"""The CLI shows why the daemon turned its connection down, in either form it is written.

The CLI helper is an API 6 process, so the daemon gives the reason as {"error": "<why>"};
an API 4 helper is given `error: <why>`.
"""

from __future__ import annotations

import pytest

from exabgp.cli.persistent_connection import _rejection_reason


@pytest.mark.parametrize(
    ('line', 'reason'),
    [
        ('error: too many clients', 'too many clients'),
        ('{"error": "too many clients"}', 'too many clients'),
        # not the JSON the daemon writes: shown as it came rather than lost
        ('{"error": broken', '{"error": broken'),
        ('{"other": "x"}', '{"other": "x"}'),
    ],
)
def test_the_reason_is_read_from_either_form(line: str, reason: str) -> None:
    assert _rejection_reason(line) == reason
