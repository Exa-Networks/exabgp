"""Tests for UpdateHandler."""

import pytest
from unittest.mock import Mock

from exabgp.bgp.message import UpdateCollection, KeepAlive
from exabgp.reactor.peer.handlers.update import UpdateHandler
from exabgp.reactor.peer.context import PeerContext


class TestUpdateHandler:
    @pytest.fixture
    def handler(self) -> UpdateHandler:
        return UpdateHandler()

    @pytest.fixture
    def mock_context(self) -> PeerContext:
        ctx = Mock(spec=PeerContext)
        ctx.neighbor = Mock()
        ctx.neighbor.rib = Mock()
        ctx.neighbor.rib.incoming = Mock()
        ctx.peer_id = 'test-peer'
        return ctx

    def test_can_handle_update(self, handler: UpdateHandler) -> None:
        """UpdateHandler recognizes UPDATE messages."""
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        assert handler.can_handle(update) is True

    def test_cannot_handle_keepalive(self, handler: UpdateHandler) -> None:
        """UpdateHandler ignores non-UPDATE messages."""
        ka = Mock()
        ka.TYPE = KeepAlive.TYPE
        assert handler.can_handle(ka) is False

    def test_handle_stores_nlris(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler stores NLRIs in incoming RIB."""
        nlri1, nlri2 = Mock(), Mock()
        parsed = Mock()
        parsed.announces = [nlri1, nlri2]
        parsed.withdraws = []
        parsed.attributes = Mock()
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        update.data = parsed

        list(handler.handle(mock_context, update))

        assert mock_context.neighbor.rib.incoming.update_cache.call_count == 2

    def test_handle_empty_nlris(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler handles updates with no NLRIs."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = []
        parsed.attributes = Mock()
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        update.data = parsed

        list(handler.handle(mock_context, update))

        assert mock_context.neighbor.rib.incoming.update_cache.call_count == 0

    def test_counter_increments(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler increments counter per update."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = []
        parsed.attributes = Mock()
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        update.data = parsed

        list(handler.handle(mock_context, update))
        list(handler.handle(mock_context, update))

        assert handler._number == 2

    def test_reset_clears_counter(self, handler: UpdateHandler) -> None:
        """reset() clears the update counter."""
        handler._number = 10
        handler.reset()
        assert handler._number == 0

    def test_handle_is_generator(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle() returns a generator."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = []
        parsed.attributes = Mock()
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        update.data = parsed

        result = handler.handle(mock_context, update)
        # Should be a generator
        assert hasattr(result, '__iter__')
        assert hasattr(result, '__next__')


class TestUpdateHandlerAsync:
    @pytest.fixture
    def handler(self) -> UpdateHandler:
        return UpdateHandler()

    @pytest.fixture
    def mock_context(self) -> PeerContext:
        ctx = Mock(spec=PeerContext)
        ctx.neighbor = Mock()
        ctx.neighbor.rib = Mock()
        ctx.neighbor.rib.incoming = Mock()
        ctx.peer_id = 'test-peer'
        return ctx

    @pytest.mark.asyncio
    async def test_handle_async_stores_nlris(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle_async stores NLRIs in incoming RIB."""
        nlri1, nlri2 = Mock(), Mock()
        parsed = Mock()
        parsed.announces = [nlri1, nlri2]
        parsed.withdraws = []
        parsed.attributes = Mock()
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        update.data = parsed

        await handler.handle_async(mock_context, update)

        assert mock_context.neighbor.rib.incoming.update_cache.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_async_increments_counter(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle_async increments counter."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = []
        parsed.attributes = Mock()
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        update.data = parsed

        await handler.handle_async(mock_context, update)
        await handler.handle_async(mock_context, update)

        assert handler._number == 2
