"""An `operational` section in a neighbour must load, and none of them did.

`OperationalFamily.family()` returns a plain `(AFI, SAFI)` tuple, which is exactly what
`Neighbor.families()` holds, but `_init_neighbor` called `.afi_safi()` on the result.  A
tuple has no such method, so EVERY configuration carrying an `operational` block was refused
at startup with

    problem parsing configuration file line 0
    error message: 'tuple' object has no attribute 'afi_safi'

The line immediately above it is correct and looks identical: `change.nlri.family()` answers
with a `Family` object, which does have `afi_safi()`.  That is why the two were written the
same way, and why the assertion below is on `family()` itself rather than only on the
configuration loading: the next person to read the two lines side by side needs the
difference written down.

Nothing pointed at it because the dictionary the parser reads is untyped.
"""

from __future__ import annotations

from typing import Any, Iterator
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.operational import Advisory
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB


@pytest.fixture(autouse=True)
def _logger() -> Iterator[None]:
    """The configuration parser logs, and the logger is not set up under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The RIB cache is keyed on neighbour name and lives on the class."""
    monkeypatch.setattr(RIB, '_cache', {})
    yield


def configured(operational: str) -> Configuration:
    return Configuration(
        [
            """neighbor 192.0.2.1 {
            router-id 192.0.2.2;
            local-address 192.0.2.2;
            local-as 65001;
            peer-as 65002;
            capability { operational; }
            family { ipv4 unicast; }
            operational { %s }
        }"""
            % operational
        ],
        text=True,
    )


def test_operational_family_returns_a_tuple_and_not_a_family() -> None:
    """The difference between the two neighbouring lines, written down."""
    message = Advisory.ASM(AFI.ipv4, SAFI.unicast, b'noc@example.com')

    assert message.family() == (AFI.ipv4, SAFI.unicast)
    assert not hasattr(message.family(), 'afi_safi'), 'family() grew the method, so this pins nothing'


def test_an_advisory_state_message_loads_and_is_stored_by_family() -> None:
    config = configured("asm afi ipv4 safi unicast advisory 'peering, noc@example.com';")

    assert config.reload(), str(config.error)

    neighbor: Any = next(iter(config.neighbors.values()))
    assert list(neighbor.asm) == [(AFI.ipv4, SAFI.unicast)]
    assert neighbor.asm[(AFI.ipv4, SAFI.unicast)].name == 'ASM'
    assert not neighbor.messages


def test_a_non_advisory_operational_message_loads_into_the_queue() -> None:
    config = configured('rpcq afi ipv4 safi unicast sequence 1;')

    assert config.reload(), str(config.error)

    neighbor: Any = next(iter(config.neighbors.values()))
    assert not neighbor.asm
    assert [message.name for message in neighbor.messages] == ['RPCQ']


def test_an_operational_message_for_an_unconfigured_family_is_dropped() -> None:
    """The membership test is the reason the call was there, so it has to still happen."""
    config = configured("asm afi ipv6 safi unicast advisory 'peering, noc@example.com';")

    assert config.reload(), str(config.error)

    neighbor: Any = next(iter(config.neighbors.values()))
    assert not neighbor.asm
    assert not neighbor.messages
