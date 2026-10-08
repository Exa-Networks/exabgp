"""Tests for RouteRefreshHandler.

The context and the messages are real: compiled (plan/wip-mypyc.md), the handler refuses a
Mock where it declares a PeerContext or a Message. The resend callback stays a Mock, it is
a plain callable.
"""

import pytest

from unittest.mock import Mock

from exabgp.bgp.message import KeepAlive

from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.handlers.route_refresh import RouteRefreshHandler
from exabgp.reactor.peer.context import PeerContext
from tests import negotiation


class TestRouteRefreshHandler:
    @pytest.fixture
    def resend_mock(self) -> Mock:
        return Mock()

    @pytest.fixture
    def handler(self, resend_mock: Mock) -> RouteRefreshHandler:
        return RouteRefreshHandler(resend_mock)

    @pytest.fixture
    def mock_context(self) -> PeerContext:
        ctx, _ = negotiation.context(refresh_enhanced=False)
        # RFC 2918 4: a request for a family the session did not negotiate is ignored
        ctx.negotiated.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)]
        return ctx

    def test_can_handle_route_refresh(self, handler: RouteRefreshHandler) -> None:
        """RouteRefreshHandler recognizes ROUTE-REFRESH messages."""
        rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast)
        assert handler.can_handle(rr) is True

    def test_cannot_handle_keepalive(self, handler: RouteRefreshHandler) -> None:
        """RouteRefreshHandler ignores non-ROUTE-REFRESH messages."""
        assert handler.can_handle(KeepAlive()) is False

    def test_handle_calls_resend(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """RouteRefreshHandler calls resend callback."""
        rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, 0)  # Not enhanced

        list(handler.handle(mock_context, rr))

        resend_mock.assert_called_once_with(False, (AFI.ipv4, SAFI.unicast))

    def test_handle_enhanced_refresh_disabled(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """Enhanced refresh disabled even if requested when not negotiated."""
        mock_context.refresh_enhanced = False

        rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.REQUEST)  # Request enhanced

        list(handler.handle(mock_context, rr))

        # Should NOT be enhanced since refresh_enhanced is False
        resend_mock.assert_called_once_with(False, (AFI.ipv4, SAFI.unicast))

    def test_handle_enhanced_refresh_enabled(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """Enhanced refresh enabled when both requested and negotiated."""
        mock_context.refresh_enhanced = True

        rr = RouteRefresh.make_route_refresh(AFI.ipv6, SAFI.unicast, RouteRefresh.REQUEST)  # Request enhanced

        list(handler.handle(mock_context, rr))

        # Should be enhanced
        resend_mock.assert_called_once_with(True, (AFI.ipv6, SAFI.unicast))

    def test_handle_is_generator(self, handler: RouteRefreshHandler, mock_context: PeerContext) -> None:
        """handle() returns a generator."""
        rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, 0)

        result = handler.handle(mock_context, rr)
        assert hasattr(result, '__iter__')
        assert hasattr(result, '__next__')


class TestRouteRefreshHandlerAsync:
    @pytest.fixture
    def resend_mock(self) -> Mock:
        return Mock()

    @pytest.fixture
    def handler(self, resend_mock: Mock) -> RouteRefreshHandler:
        return RouteRefreshHandler(resend_mock)

    @pytest.fixture
    def mock_context(self) -> PeerContext:
        ctx, _ = negotiation.context(refresh_enhanced=False)
        # RFC 2918 4: a request for a family the session did not negotiate is ignored
        ctx.negotiated.families = [(AFI.ipv4, SAFI.unicast), (AFI.ipv6, SAFI.unicast)]
        return ctx

    @pytest.mark.asyncio
    async def test_handle_async_calls_resend(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """handle_async calls resend callback."""
        rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, 0)

        await handler.handle_async(mock_context, rr)

        resend_mock.assert_called_once_with(False, (AFI.ipv4, SAFI.unicast))

    @pytest.mark.asyncio
    async def test_handle_async_enhanced(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """handle_async supports enhanced refresh."""
        mock_context.refresh_enhanced = True

        rr = RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast, RouteRefresh.REQUEST)

        await handler.handle_async(mock_context, rr)

        resend_mock.assert_called_once_with(True, (AFI.ipv4, SAFI.unicast))
