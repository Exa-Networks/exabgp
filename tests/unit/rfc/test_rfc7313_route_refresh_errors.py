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
from exabgp.bgp.message.open import ASN, Capabilities, HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.refresh import EnhancedRouteRefresh
from exabgp.bgp.message.open.capability.refresh import RouteRefresh as CapabilityRouteRefresh
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.context import PeerContext
from exabgp.reactor.peer.handlers import route_refresh
from exabgp.reactor.peer.handlers.route_refresh import RouteRefreshHandler
from rfc.message_wire import header, read_wire

MESSAGE_HEADER_ERROR = 1  # RFC 4271 section 6.1
BAD_MESSAGE_LENGTH = 2
ROUTE_REFRESH_ERROR = 7  # RFC 7313 section 5
INVALID_MESSAGE_LENGTH = 1
UNKNOWN_SUBTYPE = 3  # 0, 1 and 2 are the only subtypes RFC 7313 defines


def body(subtype: int) -> bytes:
    return pack('!HBB', int(AFI.ipv4), subtype, int(SAFI.unicast))


def received(subtype: int) -> RouteRefresh:
    return RouteRefresh.unpack_message(body(subtype), Mock())


def handled(subtype: int, enhanced: bool) -> Mock:
    resend = Mock()
    ctx = Mock(spec=PeerContext)
    ctx.refresh_enhanced = enhanced
    ctx.peer_id = 'peer'
    list(RouteRefreshHandler(resend).handle(ctx, received(subtype)))
    return resend


def test_a_four_octet_route_refresh_is_accepted() -> None:
    assert received(RouteRefresh.BEGIN).reserved == RouteRefresh.BEGIN


@pytest.mark.parametrize('size', [0, 3, 5])
def test_the_decoder_answers_a_body_which_is_not_four_octets(size: int) -> None:
    with pytest.raises(Notify) as raised:
        RouteRefresh.unpack_message(bytes(size), Mock())
    assert (raised.value.code, raised.value.subcode) == (ROUTE_REFRESH_ERROR, INVALID_MESSAGE_LENGTH)


@pytest.mark.parametrize('size', [3, 5])
def test_the_decoder_puts_the_complete_route_refresh_message_in_the_data(size: int) -> None:
    payload = bytes(range(size))
    with pytest.raises(Notify) as raised:
        RouteRefresh.unpack_message(payload, Mock())
    header = Message.MARKER + pack('!H', Message.HEADER_LEN + size) + RouteRefresh.TYPE
    assert raised.value.data == header + payload


@pytest.mark.rfc('rfc7313#5-unknown-subtype-ignored')
@pytest.mark.parametrize('subtype', [RouteRefresh.REQUEST, RouteRefresh.BEGIN, RouteRefresh.END])
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


# ============================================================ what a peer is answered
#
# The tests above call the decoder.  A peer never reaches it without the header check in
# reactor/network/connection.py in front, which is where the answer used to be decided:
# these read the message through a real connection, as the daemon does.  The header check
# answered 1/2 to every ROUTE-REFRESH which was not 23 octets, so the 7/1 the decoder raised
# was never sent to anybody, and the tests above said it was.


def peer_open(enhanced: bool) -> Open:
    capabilities = Capabilities()
    capabilities[Capability.CODE.ROUTE_REFRESH] = CapabilityRouteRefresh()
    if enhanced:
        capabilities[Capability.CODE.ENHANCED_ROUTE_REFRESH] = EnhancedRouteRefresh()
    return Open.make_open(Version(4), ASN(65001), HoldTime(180), RouterID('192.0.2.1'), capabilities)


def wire(size: int) -> bytes:
    return header(Message.HEADER_LEN + size, Message.CODE.ROUTE_REFRESH) + bytes(range(size))


def answered(size: int, enhanced: bool) -> Notify:
    with pytest.raises(Notify) as raised:
        read_wire(wire(size), peer_open(enhanced))
    return raised.value


@pytest.mark.rfc('rfc7313#5-invalid-message-length')
@pytest.mark.parametrize('subtype', [RouteRefresh.REQUEST, RouteRefresh.BEGIN, RouteRefresh.END])
def test_a_four_octet_route_refresh_read_from_a_peer_is_accepted(subtype: int) -> None:
    message = read_wire(header(Message.HEADER_LEN + 4, Message.CODE.ROUTE_REFRESH) + body(subtype), peer_open(True))
    assert message is not None
    assert message.ID == Message.CODE.ROUTE_REFRESH


@pytest.mark.rfc('rfc7313#5-invalid-message-length', polarity='negative')
@pytest.mark.parametrize('size', [0, 3, 5, 8])
def test_a_peer_is_answered_invalid_message_length(size: int) -> None:
    notify = answered(size, enhanced=True)
    assert (notify.code, notify.subcode) == (ROUTE_REFRESH_ERROR, INVALID_MESSAGE_LENGTH)


@pytest.mark.rfc('rfc7313#5-invalid-message-length-data')
@pytest.mark.parametrize('size', [3, 5])
def test_a_peer_is_sent_back_the_complete_route_refresh_message(size: int) -> None:
    assert answered(size, enhanced=True).data == wire(size)


@pytest.mark.parametrize('size', [3, 5])
def test_without_the_capability_a_wrong_length_is_a_bad_message_length(size: int) -> None:
    """Section 5 "is applicable only when" the capability was received; RFC 2918 has no error of its own."""
    notify = answered(size, enhanced=False)
    assert (notify.code, notify.subcode) == (MESSAGE_HEADER_ERROR, BAD_MESSAGE_LENGTH)
    assert notify.data == pack('!H', Message.HEADER_LEN + size)
