"""Tests for RouteRefreshHandler."""

import pytest
from unittest.mock import Mock

from exabgp.bgp.message import KeepAlive
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.handlers.route_refresh import RouteRefreshHandler
from exabgp.reactor.peer.context import PeerContext


class TestRouteRefreshHandler:
    @pytest.fixture
    def resend_mock(self) -> Mock:
        return Mock()

    @pytest.fixture
    def handler(self, resend_mock: Mock) -> RouteRefreshHandler:
        return RouteRefreshHandler(resend_mock)

    @pytest.fixture
    def mock_context(self) -> PeerContext:
        ctx = Mock(spec=PeerContext)
        ctx.refresh_enhanced = False
        return ctx

    def test_can_handle_route_refresh(self, handler: RouteRefreshHandler) -> None:
        """RouteRefreshHandler recognizes ROUTE-REFRESH messages."""
        rr = Mock()
        rr.TYPE = RouteRefresh.TYPE
        assert handler.can_handle(rr) is True

    def test_cannot_handle_keepalive(self, handler: RouteRefreshHandler) -> None:
        """RouteRefreshHandler ignores non-ROUTE-REFRESH messages."""
        ka = Mock()
        ka.TYPE = KeepAlive.TYPE
        assert handler.can_handle(ka) is False

    def test_handle_calls_resend(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """RouteRefreshHandler calls resend callback."""
        rr = Mock()
        rr.TYPE = RouteRefresh.TYPE
        rr.reserved = 0  # Not enhanced
        rr.afi = AFI.ipv4
        rr.safi = SAFI.unicast

        list(handler.handle(mock_context, rr))

        resend_mock.assert_called_once_with(False, (AFI.ipv4, SAFI.unicast))

    def test_handle_enhanced_refresh_disabled(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """Enhanced refresh disabled even if requested when not negotiated."""
        mock_context.refresh_enhanced = False

        rr = Mock()
        rr.TYPE = RouteRefresh.TYPE
        rr.reserved = RouteRefresh.request  # Request enhanced
        rr.afi = AFI.ipv4
        rr.safi = SAFI.unicast

        list(handler.handle(mock_context, rr))

        # Should NOT be enhanced since refresh_enhanced is False
        resend_mock.assert_called_once_with(False, (AFI.ipv4, SAFI.unicast))

    def test_handle_enhanced_refresh_enabled(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """Enhanced refresh enabled when both requested and negotiated."""
        mock_context.refresh_enhanced = True

        rr = Mock()
        rr.TYPE = RouteRefresh.TYPE
        rr.reserved = RouteRefresh.request  # Request enhanced
        rr.afi = AFI.ipv6
        rr.safi = SAFI.unicast

        list(handler.handle(mock_context, rr))

        # Should be enhanced
        resend_mock.assert_called_once_with(True, (AFI.ipv6, SAFI.unicast))

    def test_handle_is_generator(self, handler: RouteRefreshHandler, mock_context: PeerContext) -> None:
        """handle() returns a generator."""
        rr = Mock()
        rr.TYPE = RouteRefresh.TYPE
        rr.reserved = 0
        rr.afi = AFI.ipv4
        rr.safi = SAFI.unicast

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
        ctx = Mock(spec=PeerContext)
        ctx.refresh_enhanced = False
        return ctx

    @pytest.mark.asyncio
    async def test_handle_async_calls_resend(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """handle_async calls resend callback."""
        rr = Mock()
        rr.TYPE = RouteRefresh.TYPE
        rr.reserved = 0
        rr.afi = AFI.ipv4
        rr.safi = SAFI.unicast

        await handler.handle_async(mock_context, rr)

        resend_mock.assert_called_once_with(False, (AFI.ipv4, SAFI.unicast))

    @pytest.mark.asyncio
    async def test_handle_async_enhanced(
        self, handler: RouteRefreshHandler, mock_context: PeerContext, resend_mock: Mock
    ) -> None:
        """handle_async supports enhanced refresh."""
        mock_context.refresh_enhanced = True

        rr = Mock()
        rr.TYPE = RouteRefresh.TYPE
        rr.reserved = RouteRefresh.request
        rr.afi = AFI.ipv4
        rr.safi = SAFI.unicast

        await handler.handle_async(mock_context, rr)

        resend_mock.assert_called_once_with(True, (AFI.ipv4, SAFI.unicast))
