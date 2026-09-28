"""RFC 8955 6 validation sits where the API would otherwise see an infeasible flow.

`Protocol.read_message` tells the API about an UPDATE as soon as it is decoded, before the
peer loop hands it to `UpdateHandler`. Validating in the handler would have held the flow
out of the adj-rib-in while the API process, usually the thing which programs the
filters, had already been told about it. These tests drive `read_message` itself.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.flow import Flow, Flow4Destination
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB
from exabgp.rib.route import Route

CONFIGURATION = """
neighbor 192.0.2.1 {
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65001;
    flow-validation enable;
    family { ipv4 unicast; ipv4 flow; }
}
"""

FLOW = 'flow destination-ipv4 10.0.0.0/24'


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour() -> Neighbor:
    configuration = Configuration([CONFIGURATION], text=True)
    assert configuration.reload(), str(configuration.error)
    return next(iter(configuration.neighbors.values()))


def wire(neighbor: Neighbor, route: Route) -> bytes:
    """The UPDATE a peer on this iBGP session would send for one route."""
    _, negotiated = _negotiated(neighbor)
    collection = UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes)
    return next(collection.messages(negotiated))


def flow_route() -> Route:
    flow = Flow.make_flow(AFI.ipv4, SAFI.flow_ip)
    flow.add(Flow4Destination.make_prefix4(bytes([10, 0, 0, 0]), 24))
    return Route(flow, AttributeCollection())


def unicast_route() -> Route:
    configuration = Configuration([''], text=True)
    assert configuration.partial('static', 'route 10.0.0.0/16 next-hop 192.0.2.1', 'announce'), str(configuration.error)
    (route,) = configuration.pop_routes()
    return route


async def read(proto: Protocol, message: bytes) -> Update:
    proto.connection = Mock(
        reader_async=AsyncMock(return_value=(len(message), Message.CODE.UPDATE, message[:19], message[19:], None))
    )
    received = await proto.read_message()
    assert isinstance(received, Update)
    return received


def told(processes: Mock) -> list[str]:
    """The flow routes the API was told about, announced or withdrawn, in order."""
    routes = []
    for call in processes.message.call_args_list:
        update = call.args[3]
        routes.extend(f'+{routed.nlri}' for routed in update.data.announces if 'flow' in str(routed.nlri))
        routes.extend(f'-{nlri}' for nlri in update.data.withdraws if 'flow' in str(nlri))
    return routes


@pytest.mark.asyncio
async def test_an_infeasible_flow_is_withheld_from_the_api_and_told_once_it_becomes_feasible() -> None:
    neighbor = neighbour()
    # what a process asking for parsed UPDATEs sets, without starting one
    neighbor.api['receive-update'] = True
    neighbor.api['receive-parsed'] = True
    reactor = Mock()
    proto = Protocol(Peer(neighbor, reactor))
    proto.negotiated, _ = _negotiated(neighbor)

    flow = await read(proto, wire(neighbor, flow_route()))
    assert flow.data.announces == [], 'an infeasible flow reached the peer loop'
    assert told(reactor.processes) == [], 'an infeasible flow reached the API'

    await read(proto, wire(neighbor, unicast_route()))

    assert told(reactor.processes) == [f'+{FLOW}']
