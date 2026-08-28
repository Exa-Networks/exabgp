"""decode_to_api_command must distinguish no update from an internal failure."""

from unittest.mock import Mock

import pytest

from exabgp.configuration import command


def test_decode_failure_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_payload: str) -> bytes:
        raise RuntimeError('boom')

    monkeypatch.setattr(command, '_hexa', fail)

    with pytest.raises(RuntimeError, match='boom'):
        command.decode_to_api_command('00', Mock())


def test_no_decoded_update_returns_empty_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(command, '_hexa', lambda _payload: b'')
    monkeypatch.setattr(command, '_make_update', lambda _neighbor, _raw: None)

    assert command.decode_to_api_command('00', Mock()) == []
