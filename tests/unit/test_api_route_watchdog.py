"""A route an API helper announces with a watchdog is held by it, as a configured one is.

Only a configured route went through add_to_rib_watchdog: an API route naming a watchdog,
or asking with `withdraw` to start withdrawn, was announced at once, the two words accepted
and ignored. The route is now the watchdog's, and stays the helper's: it goes when the
helper exits, and a watchdog announced later does not bring it back.
"""

from __future__ import annotations

from collections.abc import Iterator
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.attribute.internal import Watchdog, Withdrawn
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route

PREFIX = '192.0.2.0/24'
DOG = 'dog'
NEIGHBOR = """
neighbor 127.0.0.2 {
    router-id 127.0.0.1;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65000;
    family { ipv4 unicast; }
}
"""


@pytest.fixture(autouse=True)
def _logger() -> Iterator[None]:
    """The RIB logs every insert and the logger is not initialised under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


def route(withdraw: bool) -> Route:
    address, mask = PREFIX.split('/')
    nlri = INET.from_cidr(CIDR.create_cidr(IP.pton(address), int(mask)), AFI.ipv4, SAFI.unicast)
    attributes = AttributeCollection()
    attributes[Origin.ID] = Origin.from_int(Origin.IGP)
    attributes[Attribute.CODE.INTERNAL_WATCHDOG] = Watchdog(DOG)
    if withdraw:
        attributes[Attribute.CODE.INTERNAL_WITHDRAW] = Withdrawn()
    return Route(nlri, attributes, nexthop=IP.from_string('192.0.2.1'))


def announced(rib: OutgoingRIB) -> list[str]:
    return [str(entry.nlri) for entry in rib._new_nlri.values()]


@pytest.fixture
def rib() -> OutgoingRIB:
    """The outgoing RIB of a configured neighbor, given a route the way the API gives one."""
    configuration = Configuration([NEIGHBOR], text=True)
    assert configuration.reload(), configuration.error
    ((name, neighbor),) = configuration.neighbors.items()
    configuration.announce_route([name], route(withdraw=True), 'helper')
    return neighbor.rib.outgoing


def test_an_api_route_starting_withdrawn_waits_for_its_watchdog(rib: OutgoingRIB) -> None:
    assert announced(rib) == []

    rib.announce_watchdog(DOG)

    assert announced(rib) == [PREFIX]
    assert [str(owned.nlri) for owned in rib.owned('helper')] == [PREFIX]


def test_the_routes_a_helper_gave_a_watchdog_go_with_the_helper(rib: OutgoingRIB) -> None:
    rib.announce_watchdog(DOG)

    assert rib.withdraw_owner('helper', []) == 1
    rib.withdraw_watchdog(DOG)
    rib.announce_watchdog(DOG)

    assert DOG not in rib._watchdog or not any(rib._watchdog[DOG].values())
    assert rib.owned('helper') == []


def test_a_route_held_withdrawn_for_a_helper_which_exits_is_not_announced_later(rib: OutgoingRIB) -> None:
    assert rib.withdraw_owner('helper', []) == 1

    rib.announce_watchdog(DOG)

    assert announced(rib) == []


def test_an_api_route_naming_a_watchdog_is_announced_and_withdrawn_with_it() -> None:
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
    rib.add_to_rib_watchdog(route(withdraw=False), owner='helper')
    assert announced(rib) == [PREFIX]

    rib.withdraw_watchdog(DOG)

    assert announced(rib) == []
    assert rib.owned('helper') == []
