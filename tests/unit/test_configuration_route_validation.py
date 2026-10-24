"""Offline validation must reject missing wire output and preserve known ASNs."""

import pytest

from exabgp.bgp.message import Update
from exabgp.bgp.message.open import ASN
from exabgp.configuration.check import _negotiated, check_generation
from exabgp.configuration.configuration import Configuration
from exabgp.logger import log, option
from exabgp.rib import RIB


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})
    monkeypatch.setattr(option, 'enabled', dict(option.enabled))
    for level in ('debug', 'info', 'warning', 'error', 'critical', 'fatal'):
        monkeypatch.setattr(log, level, lambda *args: None)


def configured(local_as='65001', peer_as='65002', attributes=''):
    configuration = Configuration(
        [
            f"""neighbor 192.0.2.2 {{
                router-id 192.0.2.1;
                local-address 192.0.2.1;
                local-as {local_as};
                peer-as {peer_as};
                adj-rib-out true;
                capability {{ extended-message disable; }}
                family {{ ipv4 unicast; }}
                static {{ route 10.0.0.0/24 next-hop 192.0.2.1 {attributes}; }}
            }}"""
        ],
        text=True,
    )
    assert configuration.reload(), str(configuration.error)
    return configuration


def test_offline_automatic_local_as_uses_known_peer_without_mutating_configuration():
    configuration = configured('auto', '65538')
    (neighbor,) = configuration.neighbors.values()
    negotiated = _negotiated(neighbor)
    assert negotiated.local_as == negotiated.peer_as == ASN(65538)
    assert neighbor['local-as'] is None


def test_validation_preserves_known_local_as_with_automatic_peer():
    configuration = configured('65538', 'auto')
    assert check_generation(configuration.neighbors)
    (neighbor,) = configuration.neighbors.values()
    assert neighbor['local-as'] == ASN(65538)
    assert neighbor['peer-as'] is None


def test_valid_route_still_passes_validation():
    assert check_generation(configured().neighbors)


def test_route_larger_than_message_budget_fails_validation():
    communities = 'community [ ' + ' '.join(f'65000:{value}' for value in range(1100)) + ' ]'
    assert not check_generation(configured(attributes=communities).neighbors)


def test_validation_rejects_missing_recoded_output(monkeypatch):
    original = Update.messages
    calls = 0

    def missing_recoded(self, negotiated, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            return
        yield from original(self, negotiated, *args, **kwargs)

    monkeypatch.setattr(Update, 'messages', missing_recoded)
    assert not check_generation(configured().neighbors)


def test_serialization_value_error_is_validation_failure(monkeypatch):
    def invalid(*args, **kwargs):
        raise ValueError('unresolved session-dependent attribute')

    monkeypatch.setattr(Update, 'messages', invalid)
    assert not check_generation(configured().neighbors)


def test_validation_compares_every_emitted_message(monkeypatch):
    original = Update.messages
    calls = 0

    def duplicate_initial(self, negotiated, *args, **kwargs):
        nonlocal calls
        calls += 1
        for wire in original(self, negotiated, *args, **kwargs):
            yield wire
            if calls == 1:
                yield wire

    monkeypatch.setattr(Update, 'messages', duplicate_initial)
    assert not check_generation(configured().neighbors)
