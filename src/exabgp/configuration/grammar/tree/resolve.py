"""resolve.py

Turn the values of a neighbor block into NeighborSettings, as the legacy parser turned its
scope into a Neighbor (ParseNeighbor.post).

The values come in by keyword, the way the legacy scope held them, because template
inheritance merges them in that form (`transfer`, reproduced with its accidents). Every
rule here is the legacy one: the differential tests hold the two to the same result.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.neighbor.capability import GracefulRestartConfig, NeighborCapability
from exabgp.bgp.neighbor.settings import NeighborSettings, SessionSettings
from exabgp.configuration.grammar.tree.family import SAFIS, default_families
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.protocol.ip import IP
from exabgp.util.enumeration import TriState

MANDATORY = ('peer-address', 'local-as', 'peer-as')
TCP_AO_MANDATORY = ('keyid', 'algorithm', 'password')
REQUIRE = 'require'
REQUIRABLE: dict[str, int] = {
    'asn4': Capability.CODE.FOUR_BYTES_ASN,
    'route-refresh': Capability.CODE.ROUTE_REFRESH,
    'extended-message': Capability.CODE.EXTENDED_MESSAGE,
    'operational': Capability.CODE.OPERATIONAL,
    'software-version': Capability.CODE.SOFTWARE_VERSION,
    'nexthop': Capability.CODE.NEXTHOP,
    'link-local-nexthop': Capability.CODE.LINK_LOCAL_NEXTHOP,
}
TRISTATE_CAPABILITIES = {
    'asn4': 'asn4',
    'extended-message': 'extended_message',
    'multi-session': 'multi_session',
    'operational': 'operational',
    'nexthop': 'nexthop',
    'aigp': 'aigp',
}
API_COMMANDS = ('neighbor-changes', 'negotiated', 'fsm', 'signal')
API_MESSAGES = (
    'parsed',
    'packets',
    'consolidate',
    'open',
    'update',
    'notification',
    'keepalive',
    'refresh',
    'operational',
)
# the depth of nested sections a template holds, far past the real ones
MAX_TRANSFER_DEPTH = 16


def transfer(source: dict[str, Any], destination: dict[str, Any], depth: int = 0) -> None:
    """Merge a template into a neighbor, the legacy way (Scope.transfer).

    legacy: a list is extended, a dict merged, and a number, address or string of the
    template REPLACES the neighbor's own: `inherit` wins over what the neighbor says.
    Anything else present on both sides (an `auto` AS, a tuple) is refused. A template list
    taken whole is shared, and extended in place by a later template.
    """
    if depth > MAX_TRANSFER_DEPTH:
        raise ValueError('templates nest too deep to be merged')
    for key, value in source.items():
        if key not in destination:
            destination[key] = value
        elif isinstance(value, list):
            destination[key].extend(value)
        elif isinstance(value, dict):
            transfer(value, destination[key], depth + 1)
        elif isinstance(value, (int, IP, str)):
            destination[key] = value
        else:
            raise ValueError(
                f'can not copy "{key}" (as it is of type {type(value)}) and it exists in both the source and destination'
            )


def inherit(values: dict[str, Any], templates: dict[str, dict[str, Any]]) -> None:
    # legacy: a template which does not exist, or is only defined further down, is ignored
    for name in values.pop('inherit', []):
        transfer(templates.get(name, {}), values)


def families(local: dict[str, Any]) -> list[FamilyTuple]:
    configured = local.get('family', {})
    # `all` asks for every family exabgp knows, RTC included; no family block gets the default set
    if 'all' in configured:
        return NLRI.known_families()
    found: list[FamilyTuple] = []
    for afi in SAFIS:
        # a family named in two family blocks is negotiated once
        found.extend(family for family in configured.get(afi, []) if family not in found)
    return found or default_families()


def check_mandatory(local: dict[str, Any]) -> None:
    missing = [name for name in MANDATORY if name not in local]
    if missing:
        raise ValueError('incomplete neighbor, missing {}'.format(', '.join(missing)))
    tcp_ao = local.get('tcp-ao', {})
    if tcp_ao:
        missing = [name for name in TCP_AO_MANDATORY if name not in tcp_ao]
        if missing:
            raise ValueError('incomplete tcp-ao, missing {}'.format(', '.join(missing)))


def check_role(local: dict[str, Any]) -> None:
    if 'role' not in local:
        return
    if 'local' not in local['role']:
        raise ValueError('incomplete role, missing local')
    if local.get('local-as') is None or local.get('peer-as') is None:
        raise ValueError('role requires explicit local-as and peer-as; auto is not allowed')
    if not local['local-as'] or not local['peer-as']:
        raise ValueError('role requires nonzero explicit local-as and peer-as')
    if local['local-as'] == local['peer-as']:
        raise ValueError('role requires unequal local-as and peer-as (eBGP only)')


def check_confederation(local: dict[str, Any]) -> None:
    if 'confederation' not in local:
        return
    confederation = local['confederation']
    if 'identifier' not in confederation:
        raise ValueError('incomplete confederation, missing identifier')
    if not local.get('local-as') or not local.get('peer-as'):
        raise ValueError('confederation requires explicit local-as and peer-as; auto is not allowed')
    if local['local-as'] == confederation['identifier']:
        raise ValueError('local-as is the Member-AS Number, it can not be the confederation identifier')
    if confederation['identifier'] in tuple(confederation.get('members', ())):
        raise ValueError('the confederation identifier can not also be a member')


def session(local: dict[str, Any]) -> SessionSettings:
    tcp_ao = local.get('tcp-ao', {})
    role = local.get('role', {})
    confederation = local.get('confederation', {})
    settings = SessionSettings(
        peer_address=local['peer-address'],
        local_as=local['local-as'] if local['local-as'] is not None else ASN(0),
        peer_as=local['peer-as'] if local['peer-as'] is not None else ASN(0),
        local_address=local.get('local-address'),
        router_id=local.get('router-id'),
        md5_password=local.get('md5-password', ''),
        md5_base64=local.get('md5-base64', False),
        tcp_ao_keyid=tcp_ao.get('keyid'),
        tcp_ao_algorithm=tcp_ao.get('algorithm', ''),
        tcp_ao_password=tcp_ao.get('password', ''),
        tcp_ao_base64=tcp_ao.get('base64', False),
        connect=local.get('connect', 0),
        listen=local.get('listen', 0),
        passive=local.get('passive', False),
        source_interface=local.get('source-interface', ''),
        outgoing_ttl=local.get('outgoing-ttl'),
        incoming_ttl=local.get('incoming-ttl'),
        local_link_local=local.get('local-link-local'),
        # legacy: with an auto-discovered local address, md5-ip is dropped even when given
        md5_ip=local.get('md5-ip') if local.get('local-address') is not None else None,
    )
    if role:
        settings.role = role['local']
        settings.role_strict = role.get('strict', False)
        settings.role_add_meta = role.get('add-meta', True)
    if confederation:
        settings.confederation = confederation['identifier']
        settings.confederation_members = tuple(confederation.get('members', ()))
    return settings


def capability(local: dict[str, Any]) -> NeighborCapability:
    configured = local.get('capability', {})
    cap = NeighborCapability()
    cap.required = frozenset(code for name, code in REQUIRABLE.items() if configured.get(name) == REQUIRE)
    values = {name: True if value == REQUIRE else value for name, value in configured.items()}
    for name, attribute in TRISTATE_CAPABILITIES.items():
        if name in values:
            setattr(cap, attribute, TriState.from_bool(values[name]))
    if 'add-path' in values:
        cap.add_path = values['add-path']
    if 'route-refresh' in values:
        cap.route_refresh = 2 if values['route-refresh'] else 0  # REFRESH.NORMAL or 0
    if 'software-version' in values:
        cap.software_version = 'exabgp' if values['software-version'] else None
    if values.get('link-local-nexthop') is not None:
        cap.link_local_nexthop = TriState.from_bool(values['link-local-nexthop'])
    if 'link-local-prefer' in values:
        cap.link_local_prefer = values['link-local-prefer']
    graceful = values.get('graceful-restart', None)
    if graceful is False:
        cap.graceful_restart = GracefulRestartConfig.disabled()
    elif isinstance(graceful, int) and 'graceful-restart' in values:
        # 0 is enabled with the hold-time as restart time, filled in when the neighbor is made
        cap.graceful_restart = GracefulRestartConfig.with_time(graceful)
    return cap


def addpaths(local: dict[str, Any], cap: NeighborCapability, negotiated: list[FamilyTuple]) -> list[FamilyTuple]:
    if not cap.add_path:
        return []
    add_path = local.get('add-path', {})
    if not add_path:
        return list(negotiated)
    found: list[FamilyTuple] = []
    for afi in SAFIS:
        for family, limit in add_path.get(afi, []):
            if family not in negotiated:
                log.debug(
                    lazymsg('skipping add-path family {family} as it is not negotiated', family=family), 'configuration'
                )
                continue
            found.append(family)
            if limit > 0:
                cap.paths_limit_per_family[family] = limit
    return found


def nexthops(
    local: dict[str, Any], cap: NeighborCapability, negotiated: list[FamilyTuple]
) -> list[tuple[AFI, SAFI, AFI]]:
    # the capability is on when a nexthop block is present, unless it was set explicitly
    nexthop = local.get('nexthop', {})
    if cap.nexthop.is_unset() and nexthop:
        cap.nexthop = TriState.TRUE
    if not cap.nexthop.is_enabled():
        return []
    found: list[tuple[AFI, SAFI, AFI]] = []
    for afi in nexthop:
        for entry in nexthop[afi]:
            afi_, safi, nexthop_afi = entry
            if (afi_, safi) not in negotiated or (nexthop_afi, safi) not in negotiated:
                log.debug(lazymsg('nexthop.skipped {entry} reason=not_negotiated', entry=entry), 'configuration')
                continue
            found.append(entry)
    return found


def api(apis: dict[str, Any]) -> dict[str, Any]:
    """The api blocks of a neighbor as one table, from their names to the processes (ParseAPI.flatten)."""
    built: dict[str, list[str]] = {command: [] for command in (*API_COMMANDS, 'processes', 'processes-match')}
    for direction in ('send', 'receive'):
        for message in API_MESSAGES:
            built[f'{direction}-{message}'] = []
    for block in apis.values():
        processes = block.get('processes', [])
        built['processes'].extend(processes)
        built['processes-match'].extend(block.get('processes-match', []))
        for command in API_COMMANDS:
            built[command].extend(processes if block.get(command, False) else [])
        for direction in ('send', 'receive'):
            data = block.get(direction, {})
            for message in API_MESSAGES:
                built[f'{direction}-{message}'].extend(processes if data.get(message, False) else [])
    return built


def policy(local: dict[str, Any], settings: NeighborSettings) -> None:
    """The BGP policy leaves, where the neighbor keeps them."""
    hold_time = local.get('hold-time')
    if hold_time is not None:
        settings.hold_time = HoldTime(hold_time)
    for keyword in ('description', 'rate-limit', 'host-name', 'domain-name', 'group-updates', 'as-set'):
        if local.get(keyword) is not None:
            setattr(settings, keyword.replace('-', '_'), local[keyword])
    for keyword in ('auto-flush', 'adj-rib-in', 'adj-rib-out', 'manual-eor', 'shutdown'):
        if local.get(keyword) is not None:
            setattr(settings, keyword.replace('-', '_'), local[keyword])


def neighbor_settings(local: dict[str, Any]) -> NeighborSettings:
    check_mandatory(local)
    negotiated = families(local)
    check_role(local)
    check_confederation(local)
    cap = capability(local)
    settings = NeighborSettings(session=session(local), capability=cap, families=negotiated)
    policy(local, settings)
    settings.addpaths = addpaths(local, cap, negotiated)
    limits = local.get('family', {}).get('prefix-limit', [])
    settings.prefix_limit = {family: limit for family, limit in limits if family in negotiated}
    settings.nexthops = nexthops(local, cap, negotiated)
    if cap.route_refresh and not settings.adj_rib_out:
        log.warning(
            lazymsg(
                'neighbor.route_refresh.adj_rib_out peer={peer} action=auto_enabled reason=route_refresh_requires_cache',
                peer=settings.session.peer_address,
            ),
            'configuration',
        )
        settings.adj_rib_out = True
    settings.api = api(local.get('api', {}))
    return settings
