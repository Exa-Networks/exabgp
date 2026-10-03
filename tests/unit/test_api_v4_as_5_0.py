"""An API 4 helper is written what 5.0 wrote it.

The API 4 encoders were built on the API 6 ones, and took their changes: the capabilities of
an OPEN filed under their name, a label shown with its raw value, a flow route's `string`
without its next-hop, and text routes with `next-hop no-nexthop` or the next-hop after the
route distinguisher. A helper written for 5.0 reads the 5.0 layout. Found by
qa/bin/test_old_responses, the expected lines are what 5.0 wrote.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.update.collection import RoutedNLRI, UpdateCollection
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor.api.response import Response
from exabgp.version import json as json_version
from exabgp.version import json_v4, text_v4

NEIGHBOR = (
    'neighbor 127.0.0.1 {{ router-id 10.0.0.2; local-address 127.0.0.1; local-as 1; peer-as 1; '
    'family {{ all; }} {body} }}'
)


def received(body: str) -> tuple[Any, Any, Any]:
    """The neighbor, its session, and the UPDATE of its one configured route as a peer sends it."""
    configuration = Configuration([NEIGHBOR.format(body=body)], text=True)
    assert configuration.reload(), configuration.error
    neighbor = next(iter(configuration.neighbors.values()))
    negotiated_in, negotiated_out = _negotiated(neighbor)
    route = neighbor.resolve_self(neighbor.routes[0])
    (packed,) = UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes).messages(negotiated_out)
    update = Message.unpack(Message.CODE.of(packed[18]), packed[19:], negotiated_in)
    return neighbor, negotiated_in, update


def text(body: str) -> str:
    neighbor, negotiated, update = received(body)
    line = Response.V4.Text(text_v4).update(neighbor, 'receive', update.data, b'', b'', negotiated)
    return line.splitlines()[1].split(' update ', 1)[1]


def announced(encoder: Any, body: str) -> Any:
    neighbor, negotiated, update = received(body)
    line = encoder.update(neighbor, 'receive', update.data, b'', b'', negotiated)
    (family,) = json.loads(line)['neighbor']['message']['update']['announce'].values()
    ((routes,),) = [list(family.values())]
    return routes[0]


@pytest.mark.parametrize(
    ('body', 'expected'),
    [
        (
            'static { route 10.0.0.0/24 next-hop 1.2.3.4 label 100 rd 65000:1; }',
            'announced 10.0.0.0/24 label 100 next-hop 1.2.3.4 rd 65000:1 origin igp local-preference 100',
        ),
        (
            'static { route 10.0.0.0/24 next-hop 1.2.3.4 label 100; }',
            'announced 10.0.0.0/24 label 100 next-hop 1.2.3.4 origin igp local-preference 100',
        ),
        (
            'flow { route r { match { source 10.0.0.1/32; } then { discard; } } }',
            'announced flow source-ipv4 10.0.0.1/32 origin igp local-preference 100 extended-community rate-limit:0',
        ),
        (
            'static { route 10.0.0.0/24 next-hop 1.2.3.4; }',
            'announced 10.0.0.0/24 next-hop 1.2.3.4 origin igp local-preference 100',
        ),
        (
            # 4.2 and 5.0 wrote a cluster list in brackets, of one cluster too
            'static { route 10.0.0.0/24 next-hop 1.2.3.4 cluster-list 192.168.1.10; }',
            'announced 10.0.0.0/24 next-hop 1.2.3.4 origin igp local-preference 100 cluster-list [ 192.168.1.10 ]',
        ),
    ],
)
def test_a_text_route_is_written_as_5_0_wrote_it(body: str, expected: str) -> None:
    assert text(body) == expected


def test_a_mup_route_is_written_without_a_next_hop() -> None:
    body = 'announce { ipv4 { mup mup-isd 10.0.1.0/24 rd 100:100 next-hop 10.0.0.2 extended-community [ target:10:10 ]; } }'
    assert text(body) == 'announced afi ipv4 safi mup origin igp local-preference 100 extended-community target:10:10'


def test_a_json_label_is_its_value() -> None:
    route = announced(Response.V4.JSON(json_v4), 'static { route 10.0.0.0/24 next-hop 1.2.3.4 label 100 rd 65000:1; }')
    assert route['label'] == [[100]]


def test_api_6_keeps_the_raw_label() -> None:
    route = announced(
        Response.JSON(json_version), 'static { route 10.0.0.0/24 next-hop 1.2.3.4 label 100 rd 65000:1; }'
    )
    assert route['label'] == [[100, 1601]]


def test_a_json_flow_string_ends_with_its_next_hop() -> None:
    route = announced(
        Response.V4.JSON(json_v4),
        'flow { route r { match { destination 192.168.0.1/32; } then { redirect-to-nexthop; } next-hop 1.2.3.4; } }',
    )
    assert route['string'] == 'flow destination-ipv4 192.168.0.1/32 next-hop 1.2.3.4'


def opened(encoder: Any) -> dict[str, Any]:
    neighbor, negotiated, _ = received('static { route 10.0.0.0/24 next-hop 1.2.3.4; }')
    raw = negotiated.sent_open.pack_message(negotiated)
    message = Message.unpack(Message.CODE.of(1), raw[19:], negotiated)
    line = encoder.open(neighbor, 'receive', message, b'', b'', negotiated)
    return json.loads(line)['neighbor']['open']['capabilities']


def test_api_4_files_the_capabilities_of_an_open_under_their_code() -> None:
    capabilities = opened(Response.V4.JSON(json_v4))
    assert capabilities['1']['name'] == 'multiprotocol'
    assert 'code' not in capabilities['1']


def test_api_6_files_the_capabilities_of_an_open_under_their_name() -> None:
    assert opened(Response.JSON(json_version))['multiprotocol']['code'] == 1
