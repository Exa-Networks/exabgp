"""Configuration.serialise() prints a configuration which reads back to the same one, routes aside.

str(neighbor) is a display: it does not read back (rate-limit disable, the capabilities, the
families no statement names). serialise() prints what the configuration was made from, with
the grammar printer, so each process and neighbor reads back equal.
"""

from __future__ import annotations

import os
from dataclasses import replace

import pytest

from config_grammar.differential import CONFIGURATIONS
from config_grammar.differential import ROOT as REPOSITORY
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.grammar.read import read_file, read_text
from exabgp.configuration.grammar.tree.static import Unprintable
from exabgp.configuration.settings import ConfigurationSettings, ProcessSettings

NEIGHBOR = (
    'neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; {extra} }}'
)
PROCESS = 'process watcher { run /usr/bin/true; encoder json; respawn false; on-exit keep; }'


def _without_routes(settings: ConfigurationSettings) -> ConfigurationSettings:
    return replace(settings, neighbors=[replace(neighbor, routes=[]) for neighbor in settings.neighbors])


def _loaded(text: str) -> Configuration:
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    return configuration


@pytest.mark.parametrize('path', CONFIGURATIONS, ids=lambda path: os.path.relpath(path, REPOSITORY))
def test_a_configuration_file_serialises_to_what_reads_back_the_same(path: str) -> None:
    configuration = Configuration([path])
    if not configuration.reload():
        pytest.skip('a configuration which does not load')
    try:
        serialised = configuration.serialise()
    except Unprintable as exc:
        pytest.skip(str(exc))

    assert read_text(serialised) == _without_routes(read_file(path)), serialised
    assert _loaded(serialised).serialise() == serialised, 'serialising is not stable'


def test_the_routes_are_left_out() -> None:
    serialised = _loaded(NEIGHBOR.format(extra='static { route 10.0.0.0/24 next-hop 192.0.2.3; }')).serialise()

    assert '10.0.0.0' not in serialised
    assert read_text(serialised).neighbors[0].routes == []


def test_a_process_and_the_neighbor_using_it_read_back() -> None:
    text = PROCESS + NEIGHBOR.format(extra='api { processes [ watcher ]; receive { update; } }')
    serialised = _loaded(text).serialise()

    assert read_text(serialised) == read_text(text)


def test_a_multi_session_neighbor_is_serialised_once() -> None:
    """Running, it is split in one session per family; its configuration is one neighbor block."""
    text = NEIGHBOR.format(extra='capability { multi-session; } family { ipv4 unicast; ipv6 unicast; }')
    serialised = _loaded(text).serialise()

    assert serialised.count('neighbor 192.0.2.1') == 1
    assert read_text(serialised) == read_text(text)


def test_a_failed_reload_keeps_what_was_serialised() -> None:
    configuration = _loaded(NEIGHBOR.format(extra=''))
    before = configuration.serialise()
    configuration._configurations = ['neighbor 192.0.2.1 { local-as not-a-number; }']

    assert not configuration.reload()
    assert configuration.serialise() == before


def test_a_configuration_made_from_settings_serialises() -> None:
    settings = read_text(PROCESS + NEIGHBOR.format(extra=''))
    # the processes as the reactor takes them, the way the API gives them to from_settings
    given = replace(settings, processes={name: process.to_dict() for name, process in settings.processes.items()})

    assert read_text(Configuration.from_settings(given).serialise()) == settings


def test_nothing_read_serialises_to_nothing() -> None:
    assert Configuration([]).serialise() == ''


def test_a_process_dict_reads_back_as_its_settings() -> None:
    process = ProcessSettings(run=['/bin/cat'], respawn=False)
    assert ProcessSettings.from_dict(process.to_dict()) == process
