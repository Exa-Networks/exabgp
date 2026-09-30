"""When the API process cannot be told a session is up, the peer is told why we close.

It was sent Cease with subcode 0, which IANA lists as Reserved: a value no implementation
should send.  RFC 4486 gives Out of Resources, (6, 8), for a speaker which cannot carry on
for want of a local resource, and a helper process which has gone away is one.
"""

from __future__ import annotations

from typing import Any

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.reactor.api.processes import ProcessError
from tests.negotiation import PROCESS, Told, api_asks, neighbor, peer

CEASE = 6
OUT_OF_RESOURCES = 8


class Gone(Told):
    """The encoder of a helper process which has gone away: telling it anything fails."""

    def up(self, *args: Any) -> str:
        self.calls.append(('up', args))
        raise ProcessError('gone')


def test_an_api_process_which_cannot_be_told_is_out_of_resources() -> None:
    session, _ = peer(api_asks(neighbor(), 'neighbor-changes'))
    gone = Gone()
    session.reactor.processes._encoder[PROCESS] = gone

    with pytest.raises(Notify) as caught:
        session._announce_up_to_the_api()

    assert (caught.value.code, caught.value.subcode) == (CEASE, OUT_OF_RESOURCES)
    assert gone.names() == ['up'], 'the helper was not the one which failed'


def test_a_peer_without_the_api_setting_does_not_ask() -> None:
    """The same helper which cannot be told, but no process asked to hear of the session."""
    session, _ = peer(api_asks(neighbor()))
    gone = Gone()
    session.reactor.processes._encoder[PROCESS] = gone

    session._announce_up_to_the_api()

    assert gone.names() == []
