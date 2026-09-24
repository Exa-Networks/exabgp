"""Three swallowed errors which changed behaviour rather than merely hiding noise.

`check_exa_style` counts `except X: pass`, and most of what it counts is genuinely safe:
best effort cleanup, an optional terminal feature, a teardown race. These three are not.
Each sits on a path where swallowing the error produces a different outcome from letting
it through, and in each case the outcome is the wrong one.

1.  `Asynchronous._notify_error` exists so that a failed async callback still sends
    `done`/`error` to the client, in its own words "so the client doesn't hang waiting".
    It wrapped the notification in `except Exception: pass`, so when the notifier itself
    failed the client hung forever and nothing was written down. The one handler whose
    entire job is to stop a hang was the one which could fail silently.

2.  `Listener._listen` set `SO_REUSEADDR` and, for IPv6, `IPV6_V6ONLY` inside a single
    `try`. A failure on the first skipped the second, so a listener could end up accepting
    IPv4-mapped connections which match no configured neighbour. Two independent options
    sharing one handler is how one failure silently becomes two.

3.  `Cache.in_cache` compared next hops inside a `try`, swallowed `AttributeError`, and
    then fell through to `return True`. True means "already advertised", and
    `outgoing.py` reads it as permission to skip the announce, so an unexpected error
    there dropped a route with no log. The safe direction for an error in a
    deduplication check is to say "not seen", which re-announces, rather than to say
    "seen", which loses the route.
"""

from __future__ import annotations

import socket
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor import asynchronous as asynchronous_module
from exabgp.reactor import listener as listener_module
from exabgp.reactor.asynchronous import ASYNC
from exabgp.rib.cache import Cache


class RecordingSocket:
    """Accepts setsockopt, refusing whichever options the test nominates."""

    def __init__(self, refuse: set[tuple[int, int]] | None = None) -> None:
        self.options: list[tuple[int, int, int]] = []
        self._refuse = refuse or set()

    def setsockopt(self, level: int, option: int, value: int) -> None:
        if (level, option) in self._refuse:
            raise OSError(22, 'Invalid argument')
        self.options.append((level, option, value))


# ------------------------------------------------------------------ 1. the notifier


def test_a_failing_error_handler_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client is going to hang. That must not also be invisible."""
    errors: list[str] = []
    recorder = Mock()
    recorder.error = lambda message, source='', level='ERROR': errors.append(
        str(message() if callable(message) else message)
    )
    monkeypatch.setattr(asynchronous_module, 'log', recorder)

    scheduler = ASYNC()

    def handler(uid: str) -> None:
        raise RuntimeError('the notifier itself is broken')

    scheduler.set_error_handler(handler)
    scheduler._notify_error('service-1')

    assert errors, 'the error notification failed, the client will hang, and nothing was logged'
    said = ' '.join(errors)
    assert 'service-1' in said, f'the log does not name the service which will hang: {errors}'


def test_a_failing_error_handler_does_not_propagate() -> None:
    """Still swallowed, just not silently: this runs inside the asyncio loop."""
    scheduler = ASYNC()

    def handler(uid: str) -> None:
        raise RuntimeError('the notifier itself is broken')

    scheduler.set_error_handler(handler)

    scheduler._notify_error('service-1')  # must not raise


def test_a_working_error_handler_is_called_and_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    """The ordinary path must not have gained a log line."""
    errors: list[str] = []
    recorder = Mock()
    recorder.error = lambda message, source='', level='ERROR': errors.append(str(message))
    monkeypatch.setattr(asynchronous_module, 'log', recorder)
    seen: list[str] = []

    scheduler = ASYNC()
    scheduler.set_error_handler(seen.append)
    scheduler._notify_error('service-1')

    assert seen == ['service-1']
    assert not errors, f'the working path logged an error: {errors}'


# ------------------------------------------------------- 2. the two socket options


def test_ipv6_only_is_set_even_when_reuseaddr_fails() -> None:
    """Two independent options, so one failing must not skip the other."""
    sock = RecordingSocket(refuse={(socket.SOL_SOCKET, socket.SO_REUSEADDR)})

    listener_module.set_listener_options(sock, ipv6=True)

    assert (socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1) in sock.options, (
        'SO_REUSEADDR failed and IPV6_V6ONLY was skipped, so this listener accepts IPv4-mapped connections'
    )


def test_both_options_are_set_when_the_platform_allows_it() -> None:
    sock = RecordingSocket()

    listener_module.set_listener_options(sock, ipv6=True)

    assert (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) in sock.options
    assert (socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 1) in sock.options


def test_ipv4_does_not_ask_for_the_v6_option() -> None:
    sock = RecordingSocket()

    listener_module.set_listener_options(sock, ipv6=False)

    assert (socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) in sock.options
    assert not [option for option in sock.options if option[0] == socket.IPPROTO_IPV6]


def test_neither_option_failing_stops_the_listener() -> None:
    """Both are conveniences. A bind which genuinely cannot happen fails later, loudly."""
    sock = RecordingSocket(refuse={(socket.SOL_SOCKET, socket.SO_REUSEADDR), (socket.IPPROTO_IPV6, socket.IPV6_V6ONLY)})

    listener_module.set_listener_options(sock, ipv6=True)  # must not raise


# ------------------------------------------------------------- 3. the cache verdict


def _route(index: bytes, attributes_index: bytes, nexthop: Any) -> Any:
    route = Mock()
    route.index = Mock(return_value=index)
    route.attributes.index = Mock(return_value=attributes_index)
    route.nexthop = nexthop
    family = Mock()
    family.afi_safi = Mock(return_value=(AFI.ipv4, SAFI.unicast))
    route.nlri.family = Mock(return_value=family)
    return route


class NextHopWithoutIndex:
    """A next hop whose index() is missing, which is what the handler was written for."""

    @property
    def index(self) -> Any:
        raise AttributeError('this next hop has no index')


def test_an_unexpected_error_means_not_cached_rather_than_cached() -> None:
    """False re-announces, True drops the route. Only one of those is safe to guess."""
    cache = Cache(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    nexthop = Mock()
    nexthop.index = Mock(return_value=b'nh')
    cached = _route(b'r1', b'attr', NextHopWithoutIndex())
    incoming = _route(b'r1', b'attr', nexthop)
    cache._seen = {(AFI.ipv4, SAFI.unicast): {b'r1': cached}}

    assert cache.in_cache(incoming) is False, (
        'a next hop which could not be compared reported the route as already advertised, which drops it'
    )


def test_an_identical_route_is_still_reported_as_cached() -> None:
    """The deduplication must still work, or the assertion above is satisfied by nothing."""
    cache = Cache(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    def nexthop() -> Any:
        value = Mock()
        value.index = Mock(return_value=b'nh')
        return value

    cached = _route(b'r1', b'attr', nexthop())
    incoming = _route(b'r1', b'attr', nexthop())
    cache._seen = {(AFI.ipv4, SAFI.unicast): {b'r1': cached}}

    assert cache.in_cache(incoming) is True, 'an identical route was not recognised as already advertised'


def test_a_different_next_hop_is_not_cached() -> None:
    cache = Cache(cache=True, families={(AFI.ipv4, SAFI.unicast)})

    first = Mock()
    first.index = Mock(return_value=b'nh-1')
    second = Mock()
    second.index = Mock(return_value=b'nh-2')

    cached = _route(b'r1', b'attr', first)
    incoming = _route(b'r1', b'attr', second)
    cache._seen = {(AFI.ipv4, SAFI.unicast): {b'r1': cached}}

    assert cache.in_cache(incoming) is False
