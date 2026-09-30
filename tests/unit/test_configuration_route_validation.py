"""Route validation rejects missing output and expected serialization errors."""

import pytest

from exabgp.bgp.message import UpdateCollection
from exabgp.configuration import check
from exabgp.rib import RIB
from test_configuration_asn_context import configured
from tests import negotiation

# The faults are injected by replacing methods of UpdateCollection, which the compiled
# check module calls directly: the source of the module is run instead, and it finds them.
check_generation = negotiation.interpreted(check).check_generation


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


def test_validation_compares_every_emitted_message(monkeypatch):
    config = configured('65001', '65002')
    original = UpdateCollection.messages
    calls = 0

    def duplicate_initial(self, negotiated, *args, **kwargs):
        nonlocal calls
        calls += 1
        for wire in original(self, negotiated, *args, **kwargs):
            yield wire
            if calls == 1:
                yield wire

    monkeypatch.setattr(UpdateCollection, 'messages', duplicate_initial)
    assert not check_generation(config.neighbors)
