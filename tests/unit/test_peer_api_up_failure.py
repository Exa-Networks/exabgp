"""When the API process cannot be told a session is up, the peer is told why we close.

It was sent Cease with subcode 0, which IANA lists as Reserved: a value no implementation
should send.  RFC 4486 gives Out of Resources, (6, 8), for a speaker which cannot carry on
for want of a local resource, and a helper process which has gone away is one.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.reactor.api.processes import ProcessError
from exabgp.reactor.peer import Peer

CEASE = 6
OUT_OF_RESOURCES = 8


def test_an_api_process_which_cannot_be_told_is_out_of_resources() -> None:
    neighbor = Mock()
    neighbor.uid = '1'
    neighbor.api = {'neighbor-changes': True, 'fsm': False}
    reactor = Mock()
    reactor.processes.up.side_effect = ProcessError('gone')
    peer = Peer(neighbor, reactor)

    with pytest.raises(Notify) as caught:
        peer._announce_up_to_the_api()

    assert (caught.value.code, caught.value.subcode) == (CEASE, OUT_OF_RESOURCES)


def test_a_peer_without_the_api_setting_does_not_ask() -> None:
    neighbor = Mock()
    neighbor.uid = '1'
    neighbor.api = {'neighbor-changes': False, 'fsm': False}
    reactor = Mock()
    peer = Peer(neighbor, reactor)

    peer._announce_up_to_the_api()

    reactor.processes.up.assert_not_called()
