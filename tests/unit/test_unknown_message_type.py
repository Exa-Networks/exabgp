"""A message type nobody registered reached a class attribute nobody bound.

Message.unpack ended with

    return cls.klass_unknown(message, data, negotiated)

and klass_unknown was declared on Message but bound only by bgp/message/unknown.py, which
nothing under src/ imports.  So every unregistered type raised AttributeError, which the
reactor's catch-all turned into

    Notify(1, 0, 'can not decode update message of type "252"')

naming the wrong error, and calling a type 252 message an update.  RFC 4271 6.1 is
explicit: an unrecognised Type field is Bad Message Type, subcode 3.

252 was the one a peer could reach: it was the internal NOP of the reactor, listed in
Message.CODE.MESSAGES, so reactor/protocol.py's membership check let it through, and no
class registered it.  The reactor's signals are no longer message codes, so MESSAGES now
lists exactly the types which have a decoder, and 252 is refused by that check.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated

NOP = 252
BAD_MESSAGE_TYPE = 3
MESSAGE_HEADER_ERROR = 1

UNREGISTERED = [0, 7, 8, 100, 200, NOP, 255]


@pytest.mark.parametrize('code', UNREGISTERED, ids=[str(c) for c in UNREGISTERED])
def test_an_unregistered_message_type_is_a_bad_message_type(code: int) -> None:
    """Notify, with the subcode RFC 4271 6.1 names, rather than a raw AttributeError."""
    with pytest.raises(Notify) as caught:
        Message.unpack(Message.CODE.of(code), b'\x00', Negotiated.UNSET)

    assert caught.value.code == MESSAGE_HEADER_ERROR
    assert caught.value.subcode == BAD_MESSAGE_TYPE
    assert str(code) in str(caught.value), 'the notification does not say which type was refused'


def test_the_types_the_reactor_accepts_are_the_types_with_a_decoder() -> None:
    """MESSAGES is what reactor/protocol.py lets through, so it must not name a code no class decodes.

    252 was the reactor's internal NOP and was listed here, which is what made it reachable.
    """
    assert sorted(int(code) for code in Message.CODE.MESSAGES) == sorted(Message.registered_message)
    assert NOP not in [int(code) for code in Message.CODE.MESSAGES]


@pytest.mark.parametrize('code', [1, 2, 3, 4], ids=['open', 'update', 'notification', 'keepalive'])
def test_a_registered_type_is_still_dispatched_to_its_decoder(code: int) -> None:
    """The refusal must not have swallowed the types which do have a decoder.

    Their bodies here are empty, so each will refuse for its own reason; what matters is
    that it is not the Bad Message Type refusal, which would mean dispatch stopped working.
    """
    assert code in Message.registered_message

    try:
        Message.unpack(Message.CODE.of(code), b'', Negotiated.UNSET)
    except Notify as notify:
        assert not (notify.code == MESSAGE_HEADER_ERROR and notify.subcode == BAD_MESSAGE_TYPE), (
            f'type {code} has a decoder but was refused as unknown'
        )
    except Exception:
        # a registered decoder refusing an empty body its own way is not this test's business
        return
