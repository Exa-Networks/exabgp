"""RFC 7313 section 5, the error handling of Enhanced Route Refresh.

Two rules, and exabgp broke the second.  An unknown Message Subtype was answered with
Notify(7, 2) "Malformed Message Subtype", a subcode taken from an expired draft which IANA
never assigned, and it tore the session down where the RFC says the message is ignored.

The section applies only once the Enhanced Route Refresh capability was received.  Without
it the octet is RFC 2918's Reserved field, which the receiver ignores, so the message is a
plain refresh request whatever it holds.
"""

from __future__ import annotations

from struct import pack
from unittest.mock import Mock, patch

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.context import PeerContext
from exabgp.reactor.peer.handlers import route_refresh
from exabgp.reactor.peer.handlers.route_refresh import RouteRefreshHandler

ROUTE_REFRESH_ERROR = 7  # RFC 7313 section 5
INVALID_MESSAGE_LENGTH = 1
UNKNOWN_SUBTYPE = 3  # 0, 1 and 2 are the only subtypes RFC 7313 defines


def body(subtype: int) -> bytes:
    return pack('!HBB', AFI.ipv4, subtype, SAFI.unicast)


def received(subtype: int) -> RouteRefresh:
    return RouteRefresh.unpack_message(body(subtype), Mock())


def handled(subtype: int, enhanced: bool) -> Mock:
    resend = Mock()
    ctx = Mock(spec=PeerContext)
    ctx.refresh_enhanced = enhanced
    ctx.peer_id = 'peer'
    list(RouteRefreshHandler(resend).handle(ctx, received(subtype)))
    return resend


@pytest.mark.rfc('rfc7313#5-invalid-message-length')
def test_a_four_octet_route_refresh_is_accepted() -> None:
    assert received(RouteRefresh.start).reserved == RouteRefresh.start


@pytest.mark.rfc('rfc7313#5-invalid-message-length', polarity='negative')
@pytest.mark.parametrize('size', [0, 3, 5])
def test_a_route_refresh_which_is_not_four_octets_is_invalid_message_length(size: int) -> None:
    with pytest.raises(Notify) as raised:
        RouteRefresh.unpack_message(bytes(size), Mock())
    assert (raised.value.code, raised.value.subcode) == (ROUTE_REFRESH_ERROR, INVALID_MESSAGE_LENGTH)


@pytest.mark.rfc('rfc7313#5-invalid-message-length-data')
@pytest.mark.parametrize('size', [3, 5])
def test_the_notification_carries_the_complete_route_refresh_message(size: int) -> None:
    payload = bytes(range(size))
    with pytest.raises(Notify) as raised:
        RouteRefresh.unpack_message(payload, Mock())
    header = Message.MARKER + pack('!H', Message.HEADER_LEN + size) + RouteRefresh.TYPE
    assert raised.value.raw_data == header + payload


@pytest.mark.rfc('rfc7313#5-unknown-subtype-ignored')
@pytest.mark.parametrize('subtype', [RouteRefresh.request, RouteRefresh.start, RouteRefresh.end])
def test_a_defined_subtype_decodes(subtype: int) -> None:
    assert received(subtype).reserved == subtype


@pytest.mark.rfc('rfc7313#5-unknown-subtype-ignored', polarity='negative')
def test_an_unknown_subtype_is_ignored_rather_than_notified() -> None:
    resend = handled(UNKNOWN_SUBTYPE, enhanced=True)
    resend.assert_not_called()


@pytest.mark.rfc('rfc7313#5-unknown-subtype-logged')
def test_an_unknown_subtype_is_logged() -> None:
    with patch.object(route_refresh.log, 'warning') as warning:
        handled(UNKNOWN_SUBTYPE, enhanced=True)
    warning.assert_called_once()


def test_without_the_capability_the_octet_is_reserved_and_ignored() -> None:
    """RFC 2918: the Reserved field "should be set to 0 by the sender and ignored by the receiver"."""
    resend = handled(UNKNOWN_SUBTYPE, enhanced=False)
    resend.assert_called_once_with(False, (AFI.ipv4, SAFI.unicast))
