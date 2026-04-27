"""Tests for UpdateHandler."""

import pytest
from unittest.mock import Mock, patch

from exabgp.bgp.message import UpdateCollection, KeepAlive
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.handlers.update import UpdateHandler
from exabgp.reactor.peer.context import PeerContext
from exabgp.rib.incoming import IncomingRIB


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
        ctx.negotiated = Mock()
        ctx.negotiated.advertised_paths_limit = {}
        ctx.peer_id = 'test-peer'
        ctx.stats = {'receive-prefixes': 0, 'receive-withdraws': 0}
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
        assert mock_context.stats['receive-prefixes'] == 2
        assert mock_context.stats['receive-withdraws'] == 0

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

    def test_handle_counts_withdraws(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler increments withdraw counter per NLRI."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = [Mock(), Mock(), Mock()]
        parsed.attributes = Mock()
        update = Mock()
        update.TYPE = UpdateCollection.TYPE
        update.data = parsed

        list(handler.handle(mock_context, update))

        assert mock_context.stats['receive-prefixes'] == 0
        assert mock_context.stats['receive-withdraws'] == 3

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
        ctx.negotiated = Mock()
        ctx.negotiated.advertised_paths_limit = {}
        ctx.peer_id = 'test-peer'
        ctx.stats = {'receive-prefixes': 0, 'receive-withdraws': 0}
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


def _make_announce(prefix_index_bytes: bytes, family: tuple) -> Mock:
    nlri = Mock()
    nlri.prefix_index = Mock(return_value=prefix_index_bytes)
    afi_safi_mock = Mock()
    afi_safi_mock.afi_safi = Mock(return_value=family)
    nlri.family = Mock(return_value=afi_safi_mock)
    nlri.__str__ = Mock(return_value=f'<nlri {prefix_index_bytes!r}>')
    routed = Mock()
    routed.nlri = nlri
    routed.nexthop = Mock()
    return routed


def _make_withdraw(prefix_index_bytes: bytes, family: tuple) -> Mock:
    nlri = Mock()
    nlri.prefix_index = Mock(return_value=prefix_index_bytes)
    afi_safi_mock = Mock()
    afi_safi_mock.afi_safi = Mock(return_value=family)
    nlri.family = Mock(return_value=afi_safi_mock)
    nlri.__str__ = Mock(return_value=f'<nlri {prefix_index_bytes!r}>')
    return nlri


def _make_update(announces: list, withdraws: list) -> Mock:
    parsed = Mock()
    parsed.announces = announces
    parsed.withdraws = withdraws
    parsed.attributes = Mock()
    msg = Mock()
    msg.TYPE = UpdateCollection.TYPE
    msg.data = parsed
    return msg


class TestUpdateHandlerPathsLimitAudit:
    FAMILY = (AFI.ipv4, SAFI.unicast)

    @pytest.fixture
    def handler(self) -> UpdateHandler:
        return UpdateHandler()

    @pytest.fixture
    def ctx_with_real_rib(self):
        ctx = Mock(spec=PeerContext)
        ctx.neighbor = Mock()
        ctx.neighbor.session = Mock()
        ctx.neighbor.session.peer_address = '192.0.2.99'
        ctx.neighbor.rib = Mock()
        ctx.neighbor.rib.incoming = IncomingRIB(cache=False, families={self.FAMILY})
        ctx.negotiated = Mock()
        ctx.negotiated.advertised_paths_limit = {self.FAMILY: 2}
        ctx.peer_id = 'test-peer'
        ctx.stats = {'receive-prefixes': 0, 'receive-withdraws': 0}
        return ctx

    def test_no_audit_when_advertised_limit_empty(self, handler, ctx_with_real_rib):
        ctx_with_real_rib.negotiated.advertised_paths_limit = {}
        msg = _make_update([_make_announce(b'p1', self.FAMILY)], [])
        list(handler.handle(ctx_with_real_rib, msg))
        assert ctx_with_real_rib.neighbor.rib.incoming._path_counts == {}

    def test_audit_disabled_via_env_var(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = False
            msg = _make_update([_make_announce(b'p1', self.FAMILY)] * 5, [])
            list(handler.handle(ctx_with_real_rib, msg))
        assert ctx_with_real_rib.neighbor.rib.incoming._path_counts == {}

    def test_within_limit_no_warning(self, handler, ctx_with_real_rib, caplog):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            with caplog.at_level('WARNING'):
                msg = _make_update([_make_announce(b'p1', self.FAMILY)] * 2, [])
                list(handler.handle(ctx_with_real_rib, msg))
        assert ctx_with_real_rib.neighbor.rib.incoming._path_counts[self.FAMILY][b'p1'] == 2
        assert ctx_with_real_rib.neighbor.rib.incoming._path_warned == set()

    def test_violation_logs_warning(self, handler, ctx_with_real_rib, caplog):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            with caplog.at_level('WARNING'):
                msg = _make_update([_make_announce(b'p1', self.FAMILY)] * 3, [])
                list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib._path_counts[self.FAMILY][b'p1'] == 3
        assert (self.FAMILY, b'p1') in rib._path_warned

    def test_dedup_warns_once_per_prefix(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            for _ in range(5):
                msg = _make_update([_make_announce(b'p1', self.FAMILY)], [])
                list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib._path_counts[self.FAMILY][b'p1'] == 5
        assert rib._path_warned == {(self.FAMILY, b'p1')}

    def test_independent_prefixes_independent_warnings(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update(
                [_make_announce(b'p1', self.FAMILY)] * 3 + [_make_announce(b'p2', self.FAMILY)] * 3,
                [],
            )
            list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert (self.FAMILY, b'p1') in rib._path_warned
        assert (self.FAMILY, b'p2') in rib._path_warned

    def test_only_audited_family_counts(self, handler, ctx_with_real_rib):
        other = (AFI.ipv6, SAFI.unicast)
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update([_make_announce(b'p1', other)] * 5, [])
            list(handler.handle(ctx_with_real_rib, msg))
        assert other not in ctx_with_real_rib.neighbor.rib.incoming._path_counts

    def test_withdraw_decrements_counter(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update([_make_announce(b'p1', self.FAMILY)] * 2, [])
            list(handler.handle(ctx_with_real_rib, msg))
            wmsg = _make_update([], [_make_withdraw(b'p1', self.FAMILY)])
            list(handler.handle(ctx_with_real_rib, wmsg))
        assert ctx_with_real_rib.neighbor.rib.incoming._path_counts[self.FAMILY][b'p1'] == 1

    def test_withdraw_to_zero_clears_warning(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            list(handler.handle(ctx_with_real_rib, _make_update([_make_announce(b'p1', self.FAMILY)] * 3, [])))
            rib = ctx_with_real_rib.neighbor.rib.incoming
            assert (self.FAMILY, b'p1') in rib._path_warned
            list(
                handler.handle(
                    ctx_with_real_rib,
                    _make_update([], [_make_withdraw(b'p1', self.FAMILY)] * 3),
                )
            )
            assert (self.FAMILY, b'p1') not in rib._path_warned
            list(handler.handle(ctx_with_real_rib, _make_update([_make_announce(b'p1', self.FAMILY)] * 3, [])))
            assert (self.FAMILY, b'p1') in rib._path_warned

    def test_withdraw_no_audit_when_no_limit(self, handler, ctx_with_real_rib):
        ctx_with_real_rib.negotiated.advertised_paths_limit = {}
        wmsg = _make_update([], [_make_withdraw(b'p1', self.FAMILY)])
        list(handler.handle(ctx_with_real_rib, wmsg))

    @pytest.mark.asyncio
    async def test_audit_in_async_path(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update([_make_announce(b'p1', self.FAMILY)] * 3, [])
            await handler.handle_async(ctx_with_real_rib, msg)
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib._path_counts[self.FAMILY][b'p1'] == 3
        assert (self.FAMILY, b'p1') in rib._path_warned
