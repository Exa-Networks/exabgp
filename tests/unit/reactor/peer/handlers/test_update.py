"""Tests for UpdateHandler."""

import pytest

from exabgp.bgp.message import Message
from unittest.mock import Mock, patch

from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.protocol.ip import IP
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
        ctx.neighbor.prefix_limit = {}
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
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
        assert handler.can_handle(update) is True

    def test_cannot_handle_keepalive(self, handler: UpdateHandler) -> None:
        """UpdateHandler ignores non-UPDATE messages."""
        ka = Mock()
        ka.ID = Message.CODE.KEEPALIVE
        assert handler.can_handle(ka) is False

    def test_handle_stores_nlris(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler stores NLRIs in incoming RIB."""
        nlri1, nlri2 = _make_announce(b'p1', (AFI.ipv4, SAFI.unicast)), _make_announce(b'p2', (AFI.ipv4, SAFI.unicast))
        parsed = Mock()
        parsed.announces = [nlri1, nlri2]
        parsed.withdraws = []
        parsed.attributes = AttributeCollection()
        update = Mock()
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
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
        parsed.attributes = AttributeCollection()
        update = Mock()
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
        update.data = parsed

        list(handler.handle(mock_context, update))

        assert mock_context.neighbor.rib.incoming.update_cache.call_count == 0

    def test_counter_increments(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler increments counter per update."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = []
        parsed.attributes = AttributeCollection()
        update = Mock()
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
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
        parsed.attributes = AttributeCollection()
        update = Mock()
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
        update.data = parsed

        list(handler.handle(mock_context, update))

        assert mock_context.stats['receive-prefixes'] == 0
        assert mock_context.stats['receive-withdraws'] == 3

    def test_handle_is_generator(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle() returns a generator."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = []
        parsed.attributes = AttributeCollection()
        update = Mock()
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
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
        ctx.neighbor.prefix_limit = {}
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
        nlri1, nlri2 = _make_announce(b'p1', (AFI.ipv4, SAFI.unicast)), _make_announce(b'p2', (AFI.ipv4, SAFI.unicast))
        parsed = Mock()
        parsed.announces = [nlri1, nlri2]
        parsed.withdraws = []
        parsed.attributes = AttributeCollection()
        update = Mock()
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
        update.data = parsed

        await handler.handle_async(mock_context, update)

        assert mock_context.neighbor.rib.incoming.update_cache.call_count == 2

    @pytest.mark.asyncio
    async def test_handle_async_increments_counter(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle_async increments counter."""
        parsed = Mock()
        parsed.announces = []
        parsed.withdraws = []
        parsed.attributes = AttributeCollection()
        update = Mock()
        update.ID = Message.CODE.UPDATE
        update.IS_EOR = False
        update.data = parsed

        await handler.handle_async(mock_context, update)
        await handler.handle_async(mock_context, update)

        assert handler._number == 2


# Real routes: the RIB is compiled (plan/wip-mypyc.md) and refuses a Mock for an NLRI.
# A prefix is named by a test (b'p1', b'p2') and a path by its id (b'id1'), each made a
# real prefix and a real ADD-PATH Path Identifier.
PREFIXES = {b'p1': 0, b'p2': 1}
_path_ids: dict[bytes, int] = {}


def _nlri(name: bytes, family: tuple, path_id: bytes | None) -> INET:
    afi, safi = family
    if path_id is None:
        path_id = name + b':' + str(len(_path_ids)).encode()
    number = _path_ids.setdefault(path_id, len(_path_ids) + 1)
    if afi == AFI.ipv4:
        packed = bytes([10, 0, PREFIXES[name], 0])
    else:
        packed = bytes([0x20, 0x01, 0x0D, 0xB8, 0, PREFIXES[name]]) + bytes(10)
    cidr = CIDR.create_cidr(packed, 24 if afi == AFI.ipv4 else 48)
    return INET.from_cidr(cidr, afi, safi, path_info=PathInfo.make_from_integer(number))


def index(name: bytes, family: tuple = (AFI.ipv4, SAFI.unicast)) -> bytes:
    """The prefix index the RIB keys the prefix a test calls `name` by."""
    return _nlri(name, family, b'index').prefix_index()


def _make_announce(prefix_index_bytes: bytes, family: tuple, path_id: bytes | None = None) -> RoutedNLRI:
    return RoutedNLRI(_nlri(prefix_index_bytes, family, path_id), IP.from_string('192.0.2.1'))


def _make_withdraw(prefix_index_bytes: bytes, family: tuple, path_id: bytes | None = None) -> INET:
    return _nlri(prefix_index_bytes, family, path_id)


def _make_update(announces: list, withdraws: list) -> Mock:
    parsed = Mock()
    parsed.announces = announces
    parsed.withdraws = withdraws
    parsed.attributes = AttributeCollection()
    msg = Mock()
    msg.ID = Message.CODE.UPDATE
    msg.IS_EOR = False
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
        ctx.neighbor.prefix_limit = {}
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
        assert ctx_with_real_rib.neighbor.rib.incoming._path_sets == {}

    def test_audit_disabled_via_env_var(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = False
            msg = _make_update([_make_announce(b'p1', self.FAMILY, path_id=b'id1')], [])
            list(handler.handle(ctx_with_real_rib, msg))
        assert ctx_with_real_rib.neighbor.rib.incoming._path_sets == {}

    def test_within_limit_no_warning(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update(
                [
                    _make_announce(b'p1', self.FAMILY, path_id=b'id1'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id2'),
                ],
                [],
            )
            list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib.path_count(self.FAMILY, index(b'p1')) == 2
        assert rib._path_warned == set()

    def test_violation_logs_warning(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update(
                [
                    _make_announce(b'p1', self.FAMILY, path_id=b'id1'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id2'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id3'),
                ],
                [],
            )
            list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib.path_count(self.FAMILY, index(b'p1')) == 3
        assert (self.FAMILY, index(b'p1')) in rib._path_warned

    def test_reannounce_same_path_no_inflate(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            for _ in range(5):
                msg = _make_update([_make_announce(b'p1', self.FAMILY, path_id=b'id1')], [])
                list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib.path_count(self.FAMILY, index(b'p1')) == 1

    def test_independent_prefixes_independent_warnings(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update(
                [
                    _make_announce(b'p1', self.FAMILY, path_id=b'a1'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'a2'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'a3'),
                    _make_announce(b'p2', self.FAMILY, path_id=b'b1'),
                    _make_announce(b'p2', self.FAMILY, path_id=b'b2'),
                    _make_announce(b'p2', self.FAMILY, path_id=b'b3'),
                ],
                [],
            )
            list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert (self.FAMILY, index(b'p1')) in rib._path_warned
        assert (self.FAMILY, index(b'p2')) in rib._path_warned

    def test_only_audited_family_counts(self, handler, ctx_with_real_rib):
        other = (AFI.ipv6, SAFI.unicast)
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update([_make_announce(b'p1', other, path_id=b'id1')], [])
            list(handler.handle(ctx_with_real_rib, msg))
        assert other not in ctx_with_real_rib.neighbor.rib.incoming._path_sets

    def test_withdraw_decrements_counter(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update(
                [
                    _make_announce(b'p1', self.FAMILY, path_id=b'id1'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id2'),
                ],
                [],
            )
            list(handler.handle(ctx_with_real_rib, msg))
            wmsg = _make_update([], [_make_withdraw(b'p1', self.FAMILY, path_id=b'id2')])
            list(handler.handle(ctx_with_real_rib, wmsg))
        assert ctx_with_real_rib.neighbor.rib.incoming.path_count(self.FAMILY, index(b'p1')) == 1

    def test_withdraw_to_zero_clears_warning(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update(
                [
                    _make_announce(b'p1', self.FAMILY, path_id=b'id1'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id2'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id3'),
                ],
                [],
            )
            list(handler.handle(ctx_with_real_rib, msg))
            rib = ctx_with_real_rib.neighbor.rib.incoming
            assert (self.FAMILY, index(b'p1')) in rib._path_warned
            wmsg = _make_update(
                [],
                [
                    _make_withdraw(b'p1', self.FAMILY, path_id=b'id1'),
                    _make_withdraw(b'p1', self.FAMILY, path_id=b'id2'),
                    _make_withdraw(b'p1', self.FAMILY, path_id=b'id3'),
                ],
            )
            list(handler.handle(ctx_with_real_rib, wmsg))
            assert (self.FAMILY, index(b'p1')) not in rib._path_warned

    def test_withdraw_no_audit_when_no_limit(self, handler, ctx_with_real_rib):
        ctx_with_real_rib.negotiated.advertised_paths_limit = {}
        wmsg = _make_update([], [_make_withdraw(b'p1', self.FAMILY, path_id=b'id1')])
        list(handler.handle(ctx_with_real_rib, wmsg))

    @pytest.mark.asyncio
    async def test_audit_in_async_path(self, handler, ctx_with_real_rib):
        with patch('exabgp.reactor.peer.handlers.update.getenv') as mock_env:
            mock_env.return_value.bgp.paths_limit_audit = True
            msg = _make_update(
                [
                    _make_announce(b'p1', self.FAMILY, path_id=b'id1'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id2'),
                    _make_announce(b'p1', self.FAMILY, path_id=b'id3'),
                ],
                [],
            )
            await handler.handle_async(ctx_with_real_rib, msg)
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib.path_count(self.FAMILY, index(b'p1')) == 3
        assert (self.FAMILY, index(b'p1')) in rib._path_warned
