"""Offline OPEN contexts retain independent local and remote ASN identities."""

import pytest

from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.attribute.aspath import ASPath, SEQUENCE
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.configuration.check import _negotiated, check_generation
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})


def configured(local_as, peer_as):
    config = Configuration(
        [
            f"""neighbor 192.0.2.1 {{
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as {local_as};
            peer-as {peer_as};
            family {{ ipv4 unicast; }}
            static {{ route 10.0.0.0/24 next-hop 192.0.2.2; }}
        }}"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    return config


def test_synthetic_peer_asn4_does_not_turn_ebgp_into_ibgp():
    config = configured('65001', '65538')
    (neighbor,) = config.neighbors.values()
    incoming, outgoing = _negotiated(neighbor)
    attributes = AttributeCollection()
    decoded = AttributeCollection.unpack(attributes.pack_attribute(outgoing), incoming)
    assert decoded[ASPath.ID].aspath == (SEQUENCE([ASN(65001)]),)
    assert LocalPreference.ID not in decoded


def test_synthetic_auto_local_as_resolves_without_mutating_configuration():
    config = configured('auto', '65538')
    (neighbor,) = config.neighbors.values()
    _, negotiated = _negotiated(neighbor)
    assert negotiated.local_as == ASN(65538)
    assert negotiated.peer_as == ASN(65538)
    assert neighbor.session.local_as == ASN(0)


def test_validation_accepts_a_known_local_as_with_automatic_peer():
    config = configured('65538', 'auto')
    assert check_generation(config.neighbors)
