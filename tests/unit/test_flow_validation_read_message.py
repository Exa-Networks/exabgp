"""RFC 8955 6 validation sits where the API would otherwise see an infeasible flow.

`Protocol.read_message` tells the API about an UPDATE as soon as it is decoded, before the
peer loop hands it to `UpdateHandler`. Validating in the handler would have held the flow
out of the adj-rib-in while the API process, usually the thing which programs the
filters, had already been told about it. These tests drive `read_message` itself.
"""

import pytest

from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.attribute import AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.bgp.message.update.nlri.flow import Flow, Flow4Destination
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.protocol import Protocol
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib import RIB
from exabgp.rib.route import Route
from tests import negotiation

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
    theirs = negotiation.connect(proto)
    theirs.sendall(message)
    try:
        received = await proto.read_message()
    finally:
        negotiation.disconnect(proto, theirs)
    assert isinstance(received, Update)
    return received


def told(api: negotiation.Told) -> list[str]:
    """The flow routes the API was told about, announced or withdrawn, in order."""
    routes = []
    # the encoder's update() is given the neighbor, the direction, then the UpdateCollection
    for _, _, collection, *_ in api.called('update'):
        routes.extend(f'+{routed.nlri}' for routed in collection.announces if 'flow' in str(routed.nlri))
        routes.extend(f'-{nlri}' for nlri in collection.withdraws if 'flow' in str(nlri))
    return routes


@pytest.mark.asyncio
async def test_an_infeasible_flow_is_withheld_from_the_api_and_told_once_it_becomes_feasible() -> None:
    neighbor = neighbour()
    # what a process asking for parsed UPDATEs sets, without starting one
    neighbor.api['receive-update'] = [negotiation.PROCESS]
    neighbor.api['receive-parsed'] = [negotiation.PROCESS]
    proto, api = negotiation.protocol(neighbor)
    proto.negotiated, _ = _negotiated(neighbor)

    flow = await read(proto, wire(neighbor, flow_route()))
    assert flow.data.announces == [], 'an infeasible flow reached the peer loop'
    assert told(api) == [], 'an infeasible flow reached the API'

    await read(proto, wire(neighbor, unicast_route()))

    assert told(api) == [f'+{FLOW}']
