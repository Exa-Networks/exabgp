"""Role configuration, OPEN compatibility, and live outbound OTC reload contracts."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from exabgp.bgp.fsm import FSM
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.role import Role, RoleValue
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute, OTC, OTCSelf
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.encoder import config_to_json
from exabgp.protocol.family import AFI
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.rib.route import Route


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def configuration(role: str = '', extra: str = '', local_as: str = '65001', peer_as: str = '65002') -> Configuration:
    return Configuration(
        [
            f"""neighbor 192.0.2.1 {{
                router-id 192.0.2.2;
                local-address 192.0.2.2;
                local-as {local_as};
                peer-as {peer_as};
                family {{ ipv4 unicast; }}
                {role}
                {extra}
            }}"""
        ],
        text=True,
    )


def parsed_neighbor(role: str = '', extra: str = '') -> Neighbor:
    config = configuration(role, extra)
    assert config.reload(), str(config.error)
    (neighbor,) = config.neighbors.values()
    return neighbor


def negotiate(neighbor: Neighbor, remote: RoleValue) -> Negotiated:
    sent = Capabilities().new(neighbor, False)
    received = Capabilities()
    received[Capability.CODE.MULTIPROTOCOL] = sent[Capability.CODE.MULTIPROTOCOL]
    if remote != RoleValue.NO_ROLE:
        received[Capability.CODE.ROLE] = Role(remote)
    negotiated = Negotiated(neighbor, Direction.OUT)
    negotiated.sent(Open.make_open(Version(4), neighbor.session.local_as, HoldTime(90), RouterID('192.0.2.2'), sent))
    negotiated.received(
        Open.make_open(Version(4), neighbor.session.peer_as, HoldTime(90), RouterID('192.0.2.1'), received)
    )
    return negotiated


def test_inherited_provider_role_validates_static_assertion_without_resolving_it() -> None:
    config = Configuration(
        [
            """template {
            neighbor upstream {
                local-as 65001;
                peer-as 65002;
                role { local provider; }
            }
        }
        neighbor 192.0.2.1 {
            inherit upstream;
            local-address 192.0.2.2;
            router-id 192.0.2.2;
            family { ipv4 unicast; }
            static { route 10.0.0.0/24 next-hop 192.0.2.2 otc provider; }
        }"""
        ],
        text=True,
    )
    assert config.reload(), str(config.error)
    (neighbor,) = config.neighbors.values()
    attribute = neighbor.routes[0].attributes[Attribute.CODE.OTC]
    assert isinstance(attribute, OTCSelf)
    assert attribute.role == RoleValue.PROVIDER
    negotiated = negotiate(neighbor, RoleValue.CUSTOMER)
    assert negotiated.validate(neighbor) is None
    assert attribute.pack_attribute(negotiated) == bytes.fromhex('c023040000fde9')
    assert neighbor.routes[0].attributes[Attribute.CODE.OTC] is attribute


@pytest.mark.parametrize('role', ['', 'role { local customer; }'])
def test_static_role_assertion_rejects_absent_or_different_role(role: str) -> None:
    config = configuration(role, 'static { route 10.0.0.0/24 next-hop 192.0.2.2 otc provider; }')
    assert not config.reload()
    assert 'role' in str(config.error)


def test_plain_self_needs_no_role_and_survives_auto_as_configuration() -> None:
    config = configuration(extra='static { route 10.0.0.0/24 next-hop 192.0.2.2 otc self; }', local_as='auto')
    assert config.reload(), str(config.error)
    (neighbor,) = config.neighbors.values()
    otc = neighbor.routes[0].attributes[Attribute.CODE.OTC]
    assert isinstance(otc, OTCSelf)
    assert otc.role == RoleValue.NO_ROLE


@pytest.mark.parametrize('body', ['', 'strict enable;'])
def test_present_role_block_requires_local(body: str) -> None:
    config = configuration(f'role {{ {body} }}')
    assert not config.reload()
    assert 'local' in str(config.error)


@pytest.mark.parametrize('direction', ['receive', 'send/receive'])
def test_ingress_marking_reports_unimplemented_direction(direction: str) -> None:
    config = configuration(f'role {{ local provider; otc {direction}; }}')
    assert not config.reload()
    assert 'ingress marking is not implemented' in str(config.error)


@pytest.mark.parametrize('local_as,peer_as', [('auto', '65002'), ('65001', 'auto'), ('65001', '65001')])
def test_role_requires_explicit_unequal_asns(local_as: str, peer_as: str) -> None:
    config = configuration('role { local provider; }', local_as=local_as, peer_as=peer_as)
    assert not config.reload()
    assert 'role requires' in str(config.error)


@pytest.mark.parametrize('local', RoleValue.assigned())
def test_generated_open_accepts_complementary_role(local: RoleValue) -> None:
    neighbor = parsed_neighbor(f'role {{ local {local}; strict enable; }}')
    negotiated = negotiate(neighbor, RoleValue.complement(local))
    assert negotiated.validate(neighbor) is None
    assert negotiated.role == local
    assert negotiated.peer_role == RoleValue.complement(local)


def test_role_mismatch_is_returned_by_open_validation() -> None:
    neighbor = parsed_neighbor('role { local provider; }')
    negotiated = negotiate(neighbor, RoleValue.PROVIDER)
    error = negotiated.validate(neighbor)
    assert error is not None
    assert error[:2] == (2, 11)


def test_legacy_peer_complement_is_effective_but_not_a_received_capability() -> None:
    neighbor = parsed_neighbor('role { local customer; }')
    negotiated = negotiate(neighbor, RoleValue.NO_ROLE)
    assert negotiated.validate(neighbor) is None
    assert negotiated.peer_role == RoleValue.PROVIDER
    assert negotiated.received_open is not None
    assert Capability.CODE.ROLE not in negotiated.received_open.capabilities


def test_strict_rejects_missing_remote_role() -> None:
    neighbor = parsed_neighbor('role { local provider; strict enable; }')
    error = negotiate(neighbor, RoleValue.NO_ROLE).validate(neighbor)
    assert error is not None
    assert error[:2] == (2, 11)


def test_unconfigured_role_does_not_activate_remote_role_policy() -> None:
    neighbor = parsed_neighbor()
    negotiated = negotiate(neighbor, RoleValue.PROVIDER)
    assert negotiated.validate(neighbor) is None
    assert negotiated.role == RoleValue.NO_ROLE
    assert negotiated.peer_role == RoleValue.NO_ROLE
    assert negotiated.sent_open is not None
    assert Capability.CODE.ROLE not in negotiated.sent_open.capabilities
    assert 'role {' not in str(neighbor)
    exported = json.loads(config_to_json(neighbor.session))
    assert {'role', 'role_strict', 'role_otc', 'role_add_meta'}.isdisjoint(exported)


def test_role_settings_survive_configuration_dump_and_json_export() -> None:
    neighbor = parsed_neighbor('role { local provider; strict enable; otc disable; add-meta disable; }')
    rendered = str(neighbor)
    start = rendered.index('role {')
    end = rendered.index('}', start) + 1
    reparsed = parsed_neighbor(rendered[start:end])
    exported = json.loads(config_to_json(reparsed.session))
    assert {key: exported[key] for key in ('role', 'role_strict', 'role_otc', 'role_add_meta')} == {
        'role': 'provider',
        'role_strict': True,
        'role_otc': False,
        'role_add_meta': False,
    }


def drain_wire(neighbor: Neighbor, negotiated: Negotiated) -> dict[str, int | None]:
    announced: dict[str, int | None] = {}
    for update in neighbor.rib.outgoing.updates(True, negotiated=negotiated):
        assert isinstance(update, UpdateCollection)
        for wire in update.messages(negotiated):
            decoded = Update.unpack_message(wire[19:], negotiated).parse(negotiated)
            otc = decoded.attributes.get(Attribute.CODE.OTC)
            for route in decoded.announces:
                announced[str(route.nlri.cidr)] = int(otc.asn) if isinstance(otc, OTC) else None
    return announced


@pytest.mark.asyncio
@pytest.mark.parametrize('cache', [True, False])
async def test_live_otc_reload_replays_only_retained_api_routes(cache: bool) -> None:
    extra = f'adj-rib-out {str(cache).lower()}; static {{ route 10.0.0.0/24 next-hop 192.0.2.2; }}'
    before = parsed_neighbor('role { local provider; otc disable; }', extra)
    negotiated = negotiate(before, RoleValue.CUSTOMER)
    peer = Peer(before, Mock())
    peer.proto = Protocol(peer)
    peer.proto.negotiated = negotiated
    peer.fsm.change(FSM.ESTABLISHED)
    peer._otc_disabled_warned = False
    configured = before.routes[0]
    api_route = Route(INET(bytes.fromhex('180a0100'), AFI.ipv4), configured.attributes, nexthop=configured.nexthop)
    before.rib.outgoing.add_to_rib(api_route)
    assert drain_wire(before, negotiated) == {'10.0.0.0/24': None, '10.1.0.0/24': None}
    after = parsed_neighbor('role { local provider; otc send; }', extra)
    after.previous = before
    assert before == after
    peer.reconfigure(after)
    assert negotiated.role_otc is False
    peer.proto.connection = Mock()
    peer.recv_timer = Mock()
    with (
        patch('exabgp.reactor.peer.peer.log.warning') as warning,
        patch.object(peer.proto, 'read_message', new=AsyncMock(side_effect=EOFError)),
        pytest.raises(EOFError),
    ):
        await peer._main()
    expected = {'10.0.0.0/24': 65001}
    if cache:
        expected['10.1.0.0/24'] = 65001
    else:
        warnings = [call.args[0]() for call in warning.call_args_list]
        assert any('excludes=routes-announced-through-the-api' in message for message in warnings)
    assert drain_wire(after, negotiated) == expected
    assert negotiated.neighbor is before
    assert configured.attributes.get(Attribute.CODE.OTC) is None


def test_reload_during_open_confirmation_applies_marking_to_first_announcement() -> None:
    extra = 'static { route 10.0.0.0/24 next-hop 192.0.2.2; }'
    before = parsed_neighbor('role { local provider; otc disable; }', extra)
    negotiated = negotiate(before, RoleValue.CUSTOMER)
    peer = Peer(before, Mock())
    peer.proto = Protocol(peer)
    peer.proto.negotiated = negotiated
    peer.fsm.change(FSM.OPENCONFIRM)
    after = parsed_neighbor('role { local provider; otc send; }', extra)
    after.previous = before
    peer.reconfigure(after)
    assert drain_wire(after, negotiated) == {'10.0.0.0/24': 65001}
    assert negotiated.neighbor is before
