"""An `operational` section in a neighbour must load.

`OperationalFamily.family()` returns a `(AFI, SAFI)` tuple, but the neighbour
parser called `.afi_safi()` on the result, which a tuple does not have. Every
configuration carrying an `operational` block therefore failed to load with
"'tuple' object has no attribute 'afi_safi'". The dictionary the parser reads
is typed `dict[str, Any]`, so nothing pointed at it.
"""

import pytest

from exabgp.bgp.message.operational import Advisory
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch):
    monkeypatch.setattr(RIB, '_cache', {})


def _configured(operational: str) -> Configuration:
    config = Configuration(
        [
            f"""neighbor 192.0.2.1 {{
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as 65001;
            peer-as 65002;
            capability {{ operational; }}
            family {{ ipv4 unicast; }}
            operational {{ {operational} }}
        }}"""
        ],
        text=True,
    )
    return config


def test_operational_family_returns_a_tuple_not_a_family():
    message = Advisory.ASM(AFI.ipv4, SAFI.unicast, b'noc@example.com')
    assert message.family() == (AFI.ipv4, SAFI.unicast)
    assert not hasattr(message.family(), 'afi_safi')


def test_an_advisory_state_message_loads_and_is_stored_by_family():
    config = _configured("asm afi ipv4 safi unicast advisory 'peering, noc@example.com';")
    assert config.reload(), str(config.error)

    neighbor = next(iter(config.neighbors.values()))
    assert list(neighbor.asm) == [(AFI.ipv4, SAFI.unicast)]
    assert neighbor.asm[(AFI.ipv4, SAFI.unicast)].name == 'ASM'
    assert not neighbor.messages


def test_a_non_advisory_operational_message_loads_into_the_queue():
    config = _configured('rpcq afi ipv4 safi unicast sequence 1;')
    assert config.reload(), str(config.error)

    neighbor = next(iter(config.neighbors.values()))
    assert not neighbor.asm
    assert [message.name for message in neighbor.messages] == ['RPCQ']


def test_an_operational_message_for_an_unconfigured_family_is_dropped():
    config = _configured("asm afi ipv6 safi unicast advisory 'peering, noc@example.com';")
    assert config.reload(), str(config.error)

    neighbor = next(iter(config.neighbors.values()))
    assert not neighbor.asm
    assert not neighbor.messages
