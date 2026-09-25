"""Role configuration, OPEN compatibility, and live outbound OTC reload contracts."""

from __future__ import annotations

import json

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open import HoldTime, Open, RouterID, Version
from exabgp.bgp.message.open.capability import Capabilities, Capability
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.open.capability.role import Role, RoleValue
from exabgp.bgp.message.update.attribute import Attribute, OTCSelf
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.encoder import config_to_json
from exabgp.rib import RIB


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


@pytest.mark.parametrize('direction', ['send', 'disable', 'receive', 'send/receive'])
def test_the_removed_otc_sub_option_is_refused_whatever_its_argument(direction: str) -> None:
    """Every spelling the option ever took now fails, and the failure names the RFC."""
    config = configuration(f'role {{ local provider; otc {direction}; }}')
    assert not config.reload()
    assert "'role otc' was removed" in str(config.error)
    assert 'RFC 9234 section 5' in str(config.error)


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
    assert {'role', 'role_strict', 'role_add_meta'}.isdisjoint(exported)


def test_role_settings_survive_configuration_dump_and_json_export() -> None:
    neighbor = parsed_neighbor('role { local provider; strict enable; add-meta disable; }')
    rendered = str(neighbor)
    start = rendered.index('role {')
    end = rendered.index('}', start) + 1
    # The dump still carries the removed `otc` line; the xfail below owns that defect.
    block = '\n'.join(line for line in rendered[start:end].splitlines() if 'otc' not in line)
    reparsed = parsed_neighbor(block)
    exported = json.loads(config_to_json(reparsed.session))
    assert {key: exported[key] for key in ('role', 'role_strict', 'role_add_meta')} == {
        'role': 'provider',
        'role_strict': True,
        'role_add_meta': False,
    }
    assert 'role_otc' not in exported


def test_the_rendered_configuration_no_longer_offers_the_removed_option() -> None:
    """What `show neighbor configuration` prints has to be a file exabgp can read back."""
    assert 'otc' not in str(parsed_neighbor('role { local provider; }'))
