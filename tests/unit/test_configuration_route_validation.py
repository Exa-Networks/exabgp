"""Route validation rejects missing output and expected serialization errors."""

import pytest

from exabgp.bgp.message import UpdateCollection
from exabgp.configuration.check import check_generation
from exabgp.rib import RIB
from test_configuration_asn_context import configured


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})


@pytest.mark.parametrize('reencode', [False, True])
def test_validation_rejects_missing_wire_output(monkeypatch, reencode):
    config = configured('65001', '65002')
    original = UpdateCollection.messages
    calls = 0

    def missing(self, negotiated, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == (2 if reencode else 1):
            return
        yield from original(self, negotiated, *args, **kwargs)

    monkeypatch.setattr(UpdateCollection, 'messages', missing)
    assert not check_generation(config.neighbors)


def test_validation_reports_serialization_value_error_as_failure(monkeypatch):
    config = configured('65001', '65002')

    def invalid(*args, **kwargs):
        raise ValueError('unresolved session-dependent attribute')

    monkeypatch.setattr(UpdateCollection, 'messages', invalid)
    assert not check_generation(config.neighbors)
