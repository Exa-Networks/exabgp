"""A connection from a peer nobody configured is refused with Connection Rejected.

RFC 4486 section 4 gives this case as its example of (6, 5): a connection disallowed
"e.g., the peer is not configured locally".  The listener sent (6, 3) Peer De-configured,
which is for a peering the speaker had and decided to remove.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from exabgp.reactor.listener import Listener

CEASE = 6
CONNECTION_REJECTED = 5


def refused_with() -> tuple[int, int]:
    reactor = MagicMock()
    reactor.peers.return_value = []
    listener = Listener(reactor)
    listener.serving = True
    connection = Mock()

    with patch.object(Listener, '_connected', return_value=iter([connection])):
        for _ in listener.new_connections():
            pass

    code, subcode, _ = connection.notification.call_args.args
    return code, subcode


@pytest.mark.rfc('rfc4486#4-connection-rejected')
def test_an_unconfigured_peer_is_sent_connection_rejected() -> None:
    assert refused_with() == (CEASE, CONNECTION_REJECTED)
