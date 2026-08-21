"""A NOTIFICATION too short to hold its code must not be answered with a NOTIFICATION.

RFC 4271 6.5: an error detected while processing a NOTIFICATION cannot be reported back to
the peer with a NOTIFICATION.  The session closes, and that is all.

Notification.__init__ refused a body under two bytes with a ValueError, which
reactor/protocol.py's catch-all turned into

    Notify(1, 0, 'can not decode update message of type "3"')

so a peer sending a truncated NOTIFICATION received one back, which the RFC forbids, and it
named the wrong error while doing it.

unpack_message now returns a Notification for any body.  protocol.py raises what it decodes
when the type is NOTIFICATION, so the reactor closes without replying, which is the
behaviour the RFC asks for and needs no new mechanism.

The distinction is silent to get wrong, because Notify subclasses Notification: an
isinstance check against Notification passes for both.  The assertion which can tell them
apart is `not isinstance(result, Notify)`, and it is the one every test here makes.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notification, Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated

NOTIFICATION = int(Message.CODE.NOTIFICATION)
BODIES = [0, 1, 2, 3, 8, 40]


@pytest.mark.parametrize('length', BODIES, ids=[f'{n} bytes' for n in BODIES])
def test_any_notification_body_decodes_rather_than_raising(length: int) -> None:
    """Including the two lengths which used to raise ValueError out of the parser."""
    decoded = Message.unpack(NOTIFICATION, bytes(length), Negotiated.UNSET)

    assert isinstance(decoded, Notification)


@pytest.mark.parametrize('length', BODIES, ids=[f'{n} bytes' for n in BODIES])
def test_a_notification_never_decodes_into_one_we_would_send(length: int) -> None:
    """The assertion that matters, and the one isinstance(x, Notification) cannot make.

    Notify is a Notification, so a decoder returning something we would put on the wire
    passes every check but this one.  reactor/peer.py catches Notify before Notification
    for the same reason, and a decoded NOTIFICATION reaching that first handler would be
    answered rather than acted on.
    """
    decoded = Message.unpack(NOTIFICATION, bytes(length), Negotiated.UNSET)

    assert not isinstance(decoded, Notify), 'a NOTIFICATION from the peer decoded into one we would send'


def test_a_well_formed_notification_still_carries_its_code() -> None:
    """The padding must not have flattened a real notification into an empty one.

    Every test above is satisfied by a decoder which returns a zeroed Notification for
    everything, so one of them has to read what the peer actually said.
    """
    decoded = Message.unpack(NOTIFICATION, bytes([6, 2]) + b'shutting down', Negotiated.UNSET)

    assert isinstance(decoded, Notification)
    assert decoded.code == 6, 'the cease code was lost'
    assert decoded.subcode == 2, 'the administrative shutdown subcode was lost'


@pytest.mark.parametrize('length', [0, 1], ids=['empty', 'one byte'])
def test_a_truncated_notification_says_the_peer_did_not_say_why(length: int) -> None:
    """A body with no code renders as unknown, which is accurate rather than invented."""
    decoded = Message.unpack(NOTIFICATION, bytes(length), Negotiated.UNSET)

    assert decoded.code == 0
    assert decoded.subcode == 0
    assert 'unknown' in str(decoded).lower()
