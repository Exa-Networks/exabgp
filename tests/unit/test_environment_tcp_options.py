"""The environment options the reactor reads mean what they say, wherever they were given.

- `exabgp_api_chunk` of 0 or less made `show adj-rib` loop for ever, taking no route each turn.
- `tcp.once` was only looked for in the environment variables: in the env file it was read,
  and ignored. `--once` set it after the environment was read, where nothing looks at it.
- `exabgp_tcp_connections=abc` was a Python traceback, not the one line error of the others.
- The port the peers connect to was read from the variables, not from the environment, so an
  env file `tcp.port` moved the listener and not the connections.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from exabgp.environment import base
from exabgp.environment.config import Environment, EnvironmentValueError
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from tests import negotiation

NAMES = (
    'api.chunk',
    'tcp.once',
    'tcp.attempts',
    'tcp.connections',
    'tcp.port',
)


@pytest.fixture
def fresh(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """A new environment, read from the env file the test writes, with no variable set."""
    envfile = tmp_path / 'exabgp.env'
    monkeypatch.setattr(base, 'ENVFILE', str(envfile))
    monkeypatch.setattr(Environment, '_instance', None)
    monkeypatch.setattr(Environment, '_setup_done', False)
    monkeypatch.setattr(RIB, '_cache', {})
    for name in NAMES:
        monkeypatch.delenv(f'exabgp.{name}', raising=False)
        monkeypatch.delenv(f'exabgp_{name.replace(".", "_")}', raising=False)
    return envfile


def loaded() -> Environment:
    Environment.setup()
    return Environment.instance()


# ---------------------------------------------------------------------------------- api.chunk


@pytest.mark.parametrize('value', ['0', '-1'])
def test_a_chunk_of_no_route_is_refused(fresh: Path, monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv('exabgp_api_chunk', value)
    with pytest.raises(EnvironmentValueError, match='exabgp.api.chunk'):
        loaded()


def test_a_chunk_of_one_or_more_is_taken(fresh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('exabgp_api_chunk', '25')
    assert loaded().api.chunk == 25


# ---------------------------------------------------------------------------------- tcp.once


def test_tcp_once_in_the_env_file_is_one_attempt(fresh: Path) -> None:
    fresh.write_text('[exabgp.tcp]\nonce = true\n')
    assert loaded().tcp.attempts == 1


def test_tcp_attempts_in_the_env_file_wins_over_tcp_once(fresh: Path) -> None:
    fresh.write_text('[exabgp.tcp]\nonce = true\nattempts = 5\n')
    assert loaded().tcp.attempts == 5


def test_tcp_once_as_a_variable_is_still_one_attempt(fresh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('exabgp_tcp_once', 'true')
    assert loaded().tcp.attempts == 1


def test_the_once_option_is_one_attempt(fresh: Path) -> None:
    from exabgp.application.server import command_line_options

    env = loaded()
    assert env.tcp.attempts == 0
    command_line_options(env, argparse.Namespace(profile='', once=True, memory=False, passive=False))
    assert env.tcp.attempts == 1


# --------------------------------------------------------------------------- tcp.connections


def test_tcp_connections_which_is_not_a_number_is_an_environment_error(
    fresh: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv('exabgp_tcp_connections', 'abc')
    with pytest.raises(EnvironmentValueError, match='exabgp.tcp.connections'):
        loaded()


def test_tcp_connections_is_the_number_of_attempts(fresh: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('exabgp_tcp_connections', '3')
    assert loaded().tcp.attempts == 3


# ---------------------------------------------------------------------------------- tcp.port


def test_the_env_file_port_is_the_port_connected_to(fresh: Path) -> None:
    fresh.write_text('[exabgp.tcp]\nport = 1790\n')
    peer, _ = negotiation.peer()
    assert Protocol(peer).port == 1790


def test_a_neighbour_connect_port_wins_over_the_environment(fresh: Path) -> None:
    fresh.write_text('[exabgp.tcp]\nport = 1790\n')
    configured = negotiation.neighbor()
    configured.session.connect = 2790
    peer, _ = negotiation.peer(configured)
    assert Protocol(peer).port == 2790
