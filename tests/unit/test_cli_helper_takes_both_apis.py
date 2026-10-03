"""`exabgp run` and `exabgp cli` accept the commands of 5.x as well as those of 6.0.

ExaBGP's own CLI helper relays what the operator types. It was held to API v6, so `exabgp run
show neighbor`, `exabgp run shutdown` and the shortcut `s n summary` were all refused as
unknown. `exabgp run reset` was worse: 5.0's daemon never answered `reset`, so `run` sent it and
exited 0 without waiting, and the refusal went unseen.

The helper still answers in v6 JSON. Only the dispatch of its commands changed.
"""

from __future__ import annotations

from argparse import Namespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from exabgp.application import run
from exabgp.configuration.cli_process import API_PREFIX
from exabgp.environment import Environment
from exabgp.reactor.api.command import reactor as reactor_cmd
from exabgp.reactor.api.dispatch.common import UnknownCommand
from exabgp.reactor.api.dispatch.version import API_AUTO, API_V6, dispatch_for
from exabgp.reactor.api.processes import Processes

CLI = f'{API_PREFIX}-1'


def _started(name: str) -> Processes:
    env = Environment()
    env.api.version = API_V6
    with patch('exabgp.reactor.api.processes.getenv', return_value=env):
        processes = Processes()
        processes._configuration = {name: {'run': ['/bin/cat'], 'encoder': 'json'}}
        with patch('exabgp.reactor.api.processes.log'):
            processes._select_encoder(name, processes._configuration[name])
    return processes


def _reactor() -> Any:
    reactor = MagicMock()
    reactor.peers.return_value = ['peer-1']
    return reactor


@pytest.mark.parametrize('command', ['reset', 'shutdown', 'show neighbor summary', 'session reset', 'peer show'])
def test_the_cli_helper_takes_both_forms(command: str) -> None:
    processes = _started(CLI)
    handler, _, _ = dispatch_for(processes.dispatch_version(CLI), command, _reactor(), CLI)
    assert callable(handler)


def test_reset_reaches_the_reset_handler() -> None:
    processes = _started(CLI)
    handler, _, _ = dispatch_for(processes.dispatch_version(CLI), 'reset', _reactor(), CLI)
    assert handler is reactor_cmd.reset


def test_the_cli_helper_still_answers_in_v6() -> None:
    processes = _started(CLI)
    assert processes.detect_api_version(CLI, 'show neighbor') == API_V6
    assert processes.dispatch_version(CLI) == API_AUTO


def test_an_operator_helper_held_to_v6_is_still_refused_v4() -> None:
    processes = _started('helper')
    assert processes.dispatch_version('helper') == API_V6
    with pytest.raises(UnknownCommand):
        dispatch_for(processes.dispatch_version('helper'), 'reset', _reactor(), 'helper')


def test_run_waits_for_the_answer_to_reset(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[tuple[str, str]] = []
    monkeypatch.setattr(run, 'cmdline_socket', lambda name, command: sent.append((name, command)))
    monkeypatch.delenv('exabgp_cli_transport', raising=False)
    run.cmdline(Namespace(command=['reset'], pipename=None, use_pipe=False, use_socket=True, batch_file=None))
    assert [command for _, command in sent] == ['reset']
