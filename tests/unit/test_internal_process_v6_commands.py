"""Tests that internal processes send valid v6 API commands.

Internal processes (CLI pipe, CLI socket, healthcheck) communicate with
ExaBGP via stdout. Since API v6 is the default, all commands must use
v6 format (e.g. 'session ack enable' not 'enable-ack', 'peer *' not 'neighbor *').

These tests verify the actual command strings match the v6 dispatch tree,
catching format regressions like v4 commands being used with v6 API.
"""

from __future__ import annotations

import ast
import pathlib
from types import ModuleType


def source(module: ModuleType, function: str | None = None) -> str:
    """The source of `module`, or of one function or method in it (`Class.method`).

    Read from the .py file beside the module, so it is the tree under test whether it
    runs interpreted or compiled: inspect.getsource() has no source for a compiled
    function, and the build keeps each .py next to its extension.
    """
    path = pathlib.Path(module.__file__ or '')
    text = path.with_name(path.name.split('.')[0] + '.py').read_text()
    if function is None:
        return text
    scope: ast.AST = ast.parse(text)
    for name in function.split('.'):
        scope = next(
            node
            for node in ast.iter_child_nodes(scope)
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
        )
    return ast.get_source_segment(text, scope) or ''


class TestPipeV6Commands:
    """Verify pipe.py sends valid v6 API commands."""

    def test_pipe_sends_session_ack_enable(self) -> None:
        """pipe.py must send 'session ack enable', not 'enable-ack'."""
        from exabgp.application import pipe

        text = source(pipe, 'Control.loop')
        assert "b'session ack enable\\n'" in text, 'pipe.py must send v6 session ack enable command'
        assert "b'enable-ack\\n'" not in text, 'pipe.py must not send v4 enable-ack command'

    def test_session_ack_enable_in_v6_tree(self) -> None:
        """'session ack enable' must resolve in v6 dispatch tree."""
        from exabgp.reactor.api.dispatch.v6 import _get_v6_tree

        tree = _get_v6_tree()
        assert 'session' in tree
        assert isinstance(tree['session'], dict)
        assert 'ack' in tree['session']
        assert isinstance(tree['session']['ack'], dict)
        assert 'enable' in tree['session']['ack']
        assert callable(tree['session']['ack']['enable'])


class TestSocketV6Commands:
    """Verify unixsocket.py sends valid v6 API commands."""

    def test_socket_sends_session_ack_enable(self) -> None:
        """unixsocket.py must send 'session ack enable', not 'enable-ack'."""
        from exabgp.application import unixsocket

        text = source(unixsocket)
        assert "b'session ack enable\\n'" in text, 'unixsocket.py must send v6 session ack enable command'
        assert "b'enable-ack\\n'" not in text, 'unixsocket.py must not send v4 enable-ack command'


class TestHealthcheckV6Commands:
    """Verify healthcheck.py uses v6 API command format."""

    def test_healthcheck_uses_peer_not_neighbor(self) -> None:
        """healthcheck must use 'peer *' (v6), not 'neighbor *' (v4)."""
        from exabgp.application import healthcheck

        text = source(healthcheck, 'loop')
        # Must use v6 peer prefix (constructed dynamically via prefix variable)
        assert "prefix = 'peer *'" in text, "healthcheck must default to 'peer *' prefix"
        assert "f'peer {" in text, "healthcheck must format neighbor filter as 'peer {ip}'"
        # Must not use v4 neighbor prefix
        assert "'neighbor *'" not in text, "healthcheck must not use v4 'neighbor *'"
        assert "f'neighbor {" not in text, "healthcheck must not format as 'neighbor {ip}'"

    def test_healthcheck_neighbor_filter_uses_peer(self) -> None:
        """healthcheck --neighbor filter must use 'peer {ip}', not 'neighbor {ip}'."""
        from exabgp.application import healthcheck

        text = source(healthcheck, 'loop')
        assert "f'peer {" in text, "neighbor filter must format as 'peer {ip}'"
        assert "f'neighbor {" not in text, "neighbor filter must not format as 'neighbor {ip}'"

    def test_peer_exists_in_v6_tree(self) -> None:
        """'peer' must be a top-level entry in the v6 dispatch tree."""
        from exabgp.reactor.api.dispatch.v6 import _get_v6_tree

        tree = _get_v6_tree()
        assert 'peer' in tree, "v6 dispatch tree must have 'peer' entry"
        assert 'neighbor' not in tree, "v6 dispatch tree must not have 'neighbor' as top-level entry"


class TestV6TreeCompleteness:
    """Verify v6 dispatch tree has entries for all commands used by internal processes."""

    def test_peer_selector_has_announce_and_withdraw(self) -> None:
        """peer selector subtree must support announce and withdraw."""
        from exabgp.reactor.api.dispatch.common import SELECTOR_KEY
        from exabgp.reactor.api.dispatch.v6 import _get_v6_tree

        tree = _get_v6_tree()
        peer_tree = tree['peer']
        assert isinstance(peer_tree, dict)
        assert SELECTOR_KEY in peer_tree

        selector_tree = peer_tree[SELECTOR_KEY]
        assert isinstance(selector_tree, dict)
        assert 'announce' in selector_tree
        assert 'withdraw' in selector_tree
        assert callable(selector_tree['announce'])
        assert callable(selector_tree['withdraw'])
