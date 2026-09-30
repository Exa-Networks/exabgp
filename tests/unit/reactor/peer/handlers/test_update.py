"""Tests for UpdateHandler.

The context, the messages and the RIB are the real ones: compiled (plan/wip-mypyc.md), the
handler refuses a Mock where it declares a PeerContext or a Message.
"""

import pytest

from exabgp.bgp.message import KeepAlive, Update
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI, UpdateCollection
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo
from exabgp.environment import getenv
from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor.peer.handlers.update import UpdateHandler
from exabgp.reactor.peer.context import PeerContext
from exabgp.rib.incoming import IncomingRIB
from tests import negotiation

IPV4_UNICAST = (AFI.ipv4, SAFI.unicast)


def _context() -> PeerContext:
    """A session with no paths limit and no prefix limit, holding what it receives."""
    ctx, _ = negotiation.context()
    ctx.neighbor.rib.incoming = IncomingRIB(cache=True, families={IPV4_UNICAST})
    return ctx


def _cached(ctx: PeerContext) -> int:
    return len(list(ctx.neighbor.rib.incoming.cached_routes()))


class TestUpdateHandler:
    @pytest.fixture
    def handler(self) -> UpdateHandler:
        return UpdateHandler()

    @pytest.fixture
    def mock_context(self) -> PeerContext:
        return _context()

    def test_can_handle_update(self, handler: UpdateHandler) -> None:
        """UpdateHandler recognizes UPDATE messages."""
        assert handler.can_handle(_make_update([], [])) is True

    def test_cannot_handle_keepalive(self, handler: UpdateHandler) -> None:
        """UpdateHandler ignores non-UPDATE messages."""
        assert handler.can_handle(KeepAlive()) is False

    def test_handle_stores_nlris(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler stores NLRIs in incoming RIB."""
        nlri1, nlri2 = _make_announce(b'p1', IPV4_UNICAST), _make_announce(b'p2', IPV4_UNICAST)

        list(handler.handle(mock_context, _make_update([nlri1, nlri2], [])))

        assert _cached(mock_context) == 2
        assert mock_context.stats['receive-prefixes'] == 2
        assert mock_context.stats['receive-withdraws'] == 0

    def test_handle_empty_nlris(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler handles updates with no NLRIs."""
        list(handler.handle(mock_context, _make_update([], [])))

        assert _cached(mock_context) == 0

    def test_counter_increments(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """UpdateHandler increments counter per update."""
        update = _make_update([], [])

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
        withdraws = [_make_withdraw(b'p1', IPV4_UNICAST, path_id) for path_id in (b'w1', b'w2', b'w3')]

        list(handler.handle(mock_context, _make_update([], withdraws)))

        assert mock_context.stats['receive-prefixes'] == 0
        assert mock_context.stats['receive-withdraws'] == 3

    def test_handle_is_generator(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle() returns a generator."""
        result = handler.handle(mock_context, _make_update([], []))
        # Should be a generator
        assert hasattr(result, '__iter__')
        assert hasattr(result, '__next__')


class TestUpdateHandlerAsync:
    @pytest.fixture
    def handler(self) -> UpdateHandler:
        return UpdateHandler()

    @pytest.fixture
    def mock_context(self) -> PeerContext:
        return _context()

    @pytest.mark.asyncio
    async def test_handle_async_stores_nlris(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle_async stores NLRIs in incoming RIB."""
        nlri1, nlri2 = _make_announce(b'p1', IPV4_UNICAST), _make_announce(b'p2', IPV4_UNICAST)

        await handler.handle_async(mock_context, _make_update([nlri1, nlri2], []))

        assert _cached(mock_context) == 2

    @pytest.mark.asyncio
    async def test_handle_async_increments_counter(self, handler: UpdateHandler, mock_context: PeerContext) -> None:
        """handle_async increments counter."""
        update = _make_update([], [])

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


def _make_update(announces: list, withdraws: list) -> Update:
    return Update.from_collection(UpdateCollection(announces, withdraws, AttributeCollection()))


def _audit(monkeypatch: pytest.MonkeyPatch, enabled: bool) -> None:
    """Set exabgp.bgp.paths_limit_audit for the test."""
    monkeypatch.setattr(getenv().bgp, 'paths_limit_audit', enabled)


class TestUpdateHandlerPathsLimitAudit:
    FAMILY = (AFI.ipv4, SAFI.unicast)

    @pytest.fixture
    def handler(self) -> UpdateHandler:
        return UpdateHandler()

    @pytest.fixture
    def ctx_with_real_rib(self):
        ctx, _ = negotiation.context(negotiation.neighbor(peer_address='192.0.2.99'))
        ctx.neighbor.rib.incoming = IncomingRIB(cache=False, families={self.FAMILY})
        ctx.negotiated.advertised_paths_limit = {self.FAMILY: 2}
        return ctx

    def test_no_audit_when_advertised_limit_empty(self, handler, ctx_with_real_rib):
        ctx_with_real_rib.negotiated.advertised_paths_limit = {}
        msg = _make_update([_make_announce(b'p1', self.FAMILY)], [])
        list(handler.handle(ctx_with_real_rib, msg))
        assert ctx_with_real_rib.neighbor.rib.incoming._path_sets == {}

    def test_audit_disabled_via_env_var(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, False)
        msg = _make_update([_make_announce(b'p1', self.FAMILY, path_id=b'id1')], [])
        list(handler.handle(ctx_with_real_rib, msg))
        assert ctx_with_real_rib.neighbor.rib.incoming._path_sets == {}

    def test_within_limit_no_warning(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, True)
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

    def test_violation_logs_warning(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, True)
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

    def test_reannounce_same_path_no_inflate(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, True)
        for _ in range(5):
            msg = _make_update([_make_announce(b'p1', self.FAMILY, path_id=b'id1')], [])
            list(handler.handle(ctx_with_real_rib, msg))
        rib = ctx_with_real_rib.neighbor.rib.incoming
        assert rib.path_count(self.FAMILY, index(b'p1')) == 1

    def test_independent_prefixes_independent_warnings(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, True)
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

    def test_only_audited_family_counts(self, handler, ctx_with_real_rib, monkeypatch):
        other = (AFI.ipv6, SAFI.unicast)
        _audit(monkeypatch, True)
        msg = _make_update([_make_announce(b'p1', other, path_id=b'id1')], [])
        list(handler.handle(ctx_with_real_rib, msg))
        assert other not in ctx_with_real_rib.neighbor.rib.incoming._path_sets

    def test_withdraw_decrements_counter(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, True)
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

    def test_withdraw_to_zero_clears_warning(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, True)
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
    async def test_audit_in_async_path(self, handler, ctx_with_real_rib, monkeypatch):
        _audit(monkeypatch, True)
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
