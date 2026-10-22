"""The session is written on a message line only when the API asked for `negotiated`.

Up to 5.0 the JSON of a message carried a "negotiated" block when the neighbor's api
listed `negotiated`, and none otherwise. A typing change passed the session on every
line, so each UPDATE a helper read carried the whole session, and an OPEN line read
before the OPEN exchange carried an empty one (no family, a hold time of 0).
"""

from __future__ import annotations

import json

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.keepalive import KeepAlive
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.reactor.api.response.json import JSON
from tests import negotiation

HEADER = b'\xff' * 16 + b'\x00\x13\x04'


def _told_session(*events: str, direction: str) -> tuple[object, object]:
    """The session the API was given for a KEEPALIVE packet, and the Protocol's own."""
    proto, told = negotiation.protocol(negotiation.api_asks(negotiation.neighbor(), *events))
    if direction == 'receive':
        negotiation.connect(proto).close()
        proto._count_received(Message.CODE.KEEPALIVE, HEADER, b'')
    else:
        proto._to_api('send', KeepAlive(), HEADER)
    (call,) = told.called('packets')
    return call[-1], proto.negotiated


@pytest.mark.parametrize('direction', ['receive', 'send'])
def test_a_message_line_carries_no_session_unless_asked(direction: str) -> None:
    given, _ = _told_session(f'{direction}-keepalive', f'{direction}-packets', direction=direction)
    assert given is Negotiated.UNSET


@pytest.mark.parametrize('direction', ['receive', 'send'])
def test_a_message_line_carries_the_session_when_asked(direction: str) -> None:
    given, session = _told_session('negotiated', f'{direction}-keepalive', f'{direction}-packets', direction=direction)
    assert given is session


def test_the_json_of_a_message_given_no_session_has_no_negotiated_block() -> None:
    neighbor = negotiation.neighbor()
    line = JSON('test').packets(neighbor, 'receive', Message.CODE.KEEPALIVE, HEADER, b'', Negotiated.UNSET)
    assert 'negotiated' not in json.loads(line)['neighbor']
