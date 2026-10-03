"""A NOTIFICATION is shown to a helper readable, as 4.2 and 5.0 showed it.

A Notification's `data` became the Data field as on the wire, its readable form `text`, and
the API kept reading `data`: an RFC 9003 Shutdown Communication reached a helper as
"\\u0007testing", its length octet in the message. 5.0 wrote `Shutdown Communication:
"testing"`, and gave an API 4 helper that text, as hexadecimal, for `data`. Found by
qa/bin/test_old_responses.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from exabgp.bgp.message import Message
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api.response import Response
from exabgp.util import hexstring
from exabgp.version import json as json_version
from exabgp.version import json_v4, text_v4

COMMUNICATION = bytes.fromhex('0306020774657374696E67')[1:]  # Cease, Administrative Shutdown, "testing"
READABLE = 'Shutdown Communication: "testing"'


def received(body: bytes) -> tuple[Any, Any, Any]:
    configuration = Configuration(
        ['neighbor 127.0.0.1 { router-id 10.0.0.2; local-address 127.0.0.1; local-as 1; peer-as 1; }'], text=True
    )
    assert configuration.reload(), configuration.error
    neighbor = next(iter(configuration.neighbors.values()))
    negotiated, _ = _negotiated(neighbor)
    return neighbor, negotiated, Message.unpack(Message.CODE.of(3), body, negotiated)


def notification(encoder: Any, body: bytes) -> dict[str, Any]:
    neighbor, negotiated, message = received(body)
    line = encoder.notification(neighbor, 'receive', message, b'', b'', negotiated)
    return json.loads(line)['neighbor']['notification']


def test_the_json_message_is_the_shutdown_communication() -> None:
    assert notification(Response.JSON(json_version), COMMUNICATION)['message'] == READABLE


def test_the_json_data_is_the_data_field() -> None:
    assert notification(Response.JSON(json_version), COMMUNICATION)['data'] == hexstring(COMMUNICATION[2:])


def test_an_api_4_helper_is_given_what_5_0_gave() -> None:
    shown = notification(Response.V4.JSON(json_v4), COMMUNICATION)
    assert shown['message'] == READABLE
    assert shown['data'] == hexstring(READABLE.encode())


def test_an_api_4_text_helper_is_given_what_5_0_gave() -> None:
    neighbor, negotiated, message = received(COMMUNICATION)
    line = Response.V4.Text(text_v4).notification(neighbor, 'receive', message, b'', b'', negotiated)
    assert f'data {hexstring(READABLE.encode())}' in line


@pytest.mark.parametrize('body', [bytes.fromhex('0102FFFF'), bytes.fromhex('0602')])
def test_other_data_is_shown_as_before(body: bytes) -> None:
    shown = notification(Response.JSON(json_version), body)
    assert shown['data'] == hexstring(body[2:])
