"""ADD-PATH for FlowSpec, issue #1140.

RFC 7911 applies to any AFI/SAFI.  A flow route decoded its Path Identifier, but
Flow.pack_nlri wrote none and the four flow families were left out of the capability, so
ADD-PATH could not be negotiated for them and `path-information` was refused in a flow
route.  Several flow routes with one match, each its own path, could not be announced.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.action import Action
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.capabilities import Capabilities
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri.flow import Flow, Flow4Destination
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

FLOW = (AFI.ipv4, SAFI.flow_ip)
PATH_ONE = bytes([0, 0, 0, 1])
PATH_ZERO = bytes(4)


def flow(path: PathInfo = PathInfo.DISABLED, destination: str = '10.0.0.0') -> Flow:
    nlri = Flow.make_flow(*FLOW)
    nlri.add(Flow4Destination.make_prefix4(IP.pton(destination), 24))
    nlri.addpath = path
    return nlri


def negotiated(send: bool) -> Negotiated:
    # a fresh instance: Negotiated.UNSET is shared by the whole interpreter
    result = Negotiated._create_unset()
    if send:
        result.addpath._send[FLOW] = True
        result.addpath._receive[FLOW] = True
    return result


# ============================================================================
# the wire
# ============================================================================


@pytest.mark.rfc('rfc7911#3-prepend-path-identifier')
def test_the_path_identifier_is_prepended_once_negotiated() -> None:
    plain = bytes(flow().pack_nlri(negotiated(send=False)))

    assert bytes(flow(PathInfo(PATH_ONE)).pack_nlri(negotiated(send=True))) == PATH_ONE + plain


@pytest.mark.rfc('rfc7911#3-prepend-path-identifier', polarity='negative')
def test_it_is_not_sent_when_add_path_was_not_negotiated() -> None:
    assert flow(PathInfo(PATH_ONE)).pack_nlri(negotiated(send=False)) == flow().pack_nlri(negotiated(send=False))


def test_a_flow_configured_without_one_is_sent_with_zero() -> None:
    plain = bytes(flow().pack_nlri(negotiated(send=False)))

    assert bytes(flow().pack_nlri(negotiated(send=True))) == PATH_ZERO + plain


def test_two_flows_in_one_update_read_back_with_their_identifiers() -> None:
    """The second NLRI is read from the right offset only if the first gave back all four."""
    first = flow(PathInfo(PATH_ONE))
    second = flow(PathInfo(bytes([0, 0, 0, 2])), destination='10.0.1.0')
    wire = bytes(first.pack_nlri(negotiated(send=True))) + bytes(second.pack_nlri(negotiated(send=True)))

    decoded = []
    while wire:
        nlri, wire = Flow.unpack_nlri(AFI.ipv4, SAFI.flow_ip, wire, Action.ANNOUNCE, True, negotiated(send=True))
        decoded.append(nlri)

    assert [n.addpath for n in decoded] == [first.addpath, second.addpath]
    assert [n.extensive() for n in decoded] == [first.extensive(), second.extensive()]


# ============================================================================
# the RIB and what is shown
# ============================================================================


def test_one_match_with_two_identifiers_is_two_routes() -> None:
    assert flow(PathInfo(PATH_ONE)).index() != flow(PathInfo(bytes([0, 0, 0, 2]))).index()
    assert flow(PathInfo(PATH_ONE)) != flow(PathInfo(bytes([0, 0, 0, 2])))


def test_one_match_with_one_identifier_is_one_route() -> None:
    assert flow(PathInfo(PATH_ONE)).index() == flow(PathInfo(PATH_ONE)).index()


def test_the_identifier_is_shown() -> None:
    shown = flow(PathInfo(PATH_ONE))

    assert shown.extensive().endswith(' path-information 0.0.0.1')
    assert '"path-information": "0.0.0.1"' in shown.json()


def test_a_flow_without_one_is_shown_as_before() -> None:
    assert 'path-information' not in flow().extensive()
    assert 'path-information' not in flow().json()


# ============================================================================
# the configuration and the capability
# ============================================================================

CONFIGURATION = """
neighbor 127.0.0.1 {
    router-id 1.2.3.4;
    local-address 127.0.0.1;
    local-as 1;
    peer-as 1;
    capability { add-path send/receive; }
    family { ipv4 flow; ipv4 flow-vpn; }
    add-path { ipv4 flow; ipv4 flow-vpn; }
    flow {
        route block {
            path-information 1;
            match { destination 10.0.0.0/24; }
            then { discard; }
        }
        route vpn {
            rd 65000:1;
            path-information 0.0.0.2;
            match { destination 10.0.1.0/24; }
            then { discard; }
        }
        route path-information 3 destination 10.0.2.0/24 discard;
    }
    announce {
        ipv4 {
            flow destination 10.0.3.0/24 path-information 4 discard;
        }
    }
}
"""


@pytest.fixture(scope='module')
def neighbor():  # type: ignore[no-untyped-def]
    configuration = Configuration([CONFIGURATION], text=True)
    assert configuration.reload(), configuration.error
    (configured,) = configuration.neighbors.values()
    return configured


def test_each_way_of_writing_a_flow_route_takes_path_information(neighbor) -> None:  # type: ignore[no-untyped-def]
    paths = {str(route.nlri.addpath).strip() for route in neighbor.routes}

    assert paths == {f'path-information 0.0.0.{n}' for n in (1, 2, 3, 4)}


def test_the_identifier_survives_the_route_becoming_flow_vpn(neighbor) -> None:  # type: ignore[no-untyped-def]
    (vpn,) = {route.nlri.index(): route for route in neighbor.routes if route.nlri.safi == SAFI.flow_vpn}.values()

    assert vpn.nlri.addpath == PathInfo(bytes([0, 0, 0, 2]))


def test_add_path_is_offered_for_the_flow_families(neighbor) -> None:  # type: ignore[no-untyped-def]
    capabilities = Capabilities().new(neighbor, False, local_as=ASN(1))
    offered = capabilities[Capability.CODE.ADD_PATH]

    assert isinstance(offered, AddPath)
    assert (AFI.ipv4, SAFI.flow_ip) in offered
    assert (AFI.ipv4, SAFI.flow_vpn) in offered
