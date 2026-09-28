"""An UPDATE received on a session which keeps no Adj-RIB-In is still an Update.

`Protocol.read_message` had a shortcut for a session with no role, no Adj-RIB-In, no API
process and no route logging: it skipped decoding and returned `_UPDATE`, an empty
`UpdateCollection`.  The reactor handed that to `UpdateHandler`, which reads `.data` on
every UPDATE, and `UpdateCollection` has no `.data`: the first UPDATE the peer sent reset
the session with an AttributeError.  Skipping the decode also skipped what the handler
does with it whatever the Adj-RIB-In says: the prefix limit of RFC 4486, the End-of-RIB
record of RFC 7313, and the RFC 7606 checks of the UPDATE itself.
"""

from unittest.mock import AsyncMock, Mock

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.update import Update, UpdateCollection
from exabgp.bgp.message.update.collection import RoutedNLRI
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api import API
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB

CONFIGURATION = """
neighbor 192.0.2.1 {
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65002;
    adj-rib-in false;
    family { ipv4 unicast; }
}
"""


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


@pytest.mark.asyncio
async def test_update_without_adj_rib_in_is_decoded() -> None:
    configuration = Configuration([CONFIGURATION], text=True)
    assert configuration.reload(), str(configuration.error)
    neighbor = next(iter(configuration.neighbors.values()))
    # decoding what this session sent, or a path written for another rule: RFC 8955 6 has its own tests
    neighbor.enforce_first_as = False
    _, negotiated = _negotiated(neighbor)

    announced = API(Mock()).api_route('route 10.0.0.0/24 next-hop 192.0.2.2', 'announce')[0]
    collection = UpdateCollection([RoutedNLRI(announced.nlri, announced.nexthop)], [], announced.attributes)
    wire = next(collection.messages(negotiated))

    proto = Protocol(Peer(neighbor, Mock()))
    proto.negotiated = negotiated
    proto.connection = Mock(
        reader_async=AsyncMock(return_value=(len(wire), Message.CODE.UPDATE, wire[:19], wire[19:], None))
    )

    received = await proto.read_message()
    assert isinstance(received, Update)
    assert [str(routed.nlri.cidr) for routed in received.data.announces] == ['10.0.0.0/24']
