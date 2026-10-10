"""The offline checker (exabgp decode, configuration validate) reads a BGP header safely.

check_message() and display_message() read raw[18] as soon as the marker was there, so a
message of 17 or 18 bytes was an IndexError out of a validation tool. A KEEPALIVE, which is
the header alone, was reported as an unknown message type. check_notification() decoded
from raw[18], so the type octet was read as the error code.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.notification import Notification
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration import check
from exabgp.configuration.setup import create_minimal_configuration

MARKER = 'FF' * 16


@pytest.fixture
def neighbor() -> Neighbor:
    return next(iter(create_minimal_configuration().neighbors.values()))


@pytest.mark.parametrize('message', [MARKER + '00', MARKER + '0013'])
def test_a_header_too_short_is_refused_not_raised(neighbor: Neighbor, message: str) -> None:
    assert check.check_message(neighbor, message) is False
    assert check.display_message(neighbor, message) is False


@pytest.mark.rfc('rfc4271#6.1-bad-message-length')
def test_a_keepalive_is_a_known_message(neighbor: Neighbor, capsys: pytest.CaptureFixture[str]) -> None:
    keepalive = MARKER + '001304'
    assert check.check_message(neighbor, keepalive) is True
    assert check.display_message(neighbor, keepalive) is True
    output = capsys.readouterr().out
    assert 'unknown type' not in output
    assert '"type": "keepalive"' in output


@pytest.mark.rfc('rfc4271#6.1-bad-message-length', polarity='negative')
def test_a_keepalive_with_a_body_is_refused(neighbor: Neighbor) -> None:
    keepalive = MARKER + '00140400'
    assert check.check_message(neighbor, keepalive) is False
    assert check.display_message(neighbor, keepalive) is False


class _Recorder:
    """Stands in for the module's log, keeping what info() was given."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def info(self, message: object, source: str = '') -> None:
        self.messages.append(str(message() if callable(message) else message))


def test_check_notification_reads_the_code_after_the_header(monkeypatch: pytest.MonkeyPatch) -> None:
    # what was decoded is seen in what is logged: a patched Notification.unpack_message is
    # not, as the compiled check.py calls the native method without looking it up
    recorder = _Recorder()
    monkeypatch.setattr(check, 'log', recorder)
    assert check.check_notification(bytes.fromhex(MARKER + '0015030602')) is True
    # read from raw[18], the type octet 3 would have been the code: UPDATE Message Error
    assert recorder.messages == [f'notification.decoded notification={Notification(b"\x06\x02")}']
    assert 'Cease / Administrative Shutdown' in recorder.messages[0]
