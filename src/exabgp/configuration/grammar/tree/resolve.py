"""resolve.py

The rules turning the values of a neighbor block into NeighborSettings, as the legacy parser
turned its scope into a Neighbor (ParseNeighbor.post); codecs.py applies them part by part.

The values come in by keyword, the way the legacy scope held them, because template
inheritance merges them in that form (`transfer`, reproduced with its accidents). Every
rule here is the legacy one: the differential tests hold the two to the same result.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability, CapabilityCode
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.neighbor.capability import GracefulRestartConfig, NeighborCapability
from exabgp.bgp.neighbor.settings import SessionSettings
from exabgp.configuration.grammar.tree.family import SAFIS, default_families
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI, FamilyTuple
from exabgp.util.enumeration import TriState

MANDATORY = ('peer-address', 'local-as', 'peer-as')
TCP_AO_MANDATORY = ('keyid', 'algorithm', 'password')
REQUIRE = 'require'
REQUIRABLE: dict[str, CapabilityCode] = {
    'asn4': Capability.CODE.FOUR_BYTES_ASN,
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
    """Merge a template into a neighbor: what the neighbor already has wins.

    A template gives defaults the neighbor changes. A list is extended (routes, processes add
    up) and a section merged by the same rule; a value the neighbor has is kept. The template
    won before 6.0: `hold-time 30;` in a neighbor whose template said `hold-time 60;` was 60.
    A list or a dict is copied, never taken whole: a later template extended the template's
    own list in place, and every other neighbor inheriting it was given what it added.
    """
    if depth > MAX_TRANSFER_DEPTH:
        raise ValueError('templates nest too deep to be merged')
    for key, value in source.items():
        if key not in destination:
            destination[key] = _copied(value, depth)
        elif isinstance(value, list) and isinstance(destination[key], list):
            destination[key].extend(value)
        elif isinstance(value, dict) and isinstance(destination[key], dict):
            transfer(value, destination[key], depth + 1)


def _copied(value: Any, depth: int) -> Any:
    """A list or a dict of a template, as the neighbor's own; anything else as it is."""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        copied: dict[str, Any] = {}
        transfer(value, copied, depth + 1)
        return copied
    return value


# the templates one template may inherit through, one from the other, far past a real one
MAX_INHERIT_DEPTH = 8


def inherit(values: dict[str, Any], templates: dict[str, dict[str, Any]]) -> None:
    """Merge the templates a neighbor inherits, and those they inherit, into its values.

    What is set first wins: the neighbor's own values, then each template in the order it is
    listed, a template's own values before those of the templates it inherits. Each template
    is merged once, however often it is inherited; one which inherits itself, through any
    chain, is refused.
    """
    merged: set[str] = set()
    for name in values.pop('inherit', []):
        _inherit(name, values, templates, (), merged)


def _inherit(
    name: str, values: dict[str, Any], templates: dict[str, dict[str, Any]], chain: tuple[str, ...], merged: set[str]
) -> None:
    if name in chain:
        raise ValueError(f'template {name} inherits itself: {" > ".join((*chain, name))}')
    if len(chain) >= MAX_INHERIT_DEPTH:
        raise ValueError(f'templates inherit each other more than {MAX_INHERIT_DEPTH} deep: {" > ".join(chain)}')
    if name in merged:
        return
    merged.add(name)
    # the templates are read before the neighbors (read.templates_first): this one is nowhere
    if name not in templates:
        log.warning(
            lazymsg('inherit {name}: no template has this name, nothing is inherited', name=name), 'configuration'
        )
    template = templates.get(name, {})
    transfer({key: value for key, value in template.items() if key != 'inherit'}, values)
    for parent in template.get('inherit', []):
        _inherit(parent, values, templates, (*chain, name), merged)


def families(values: dict[str, Any]) -> list[FamilyTuple]:
    configured = values.get('family', {})
    # `all` asks for every family exabgp knows, RTC included; no family block gets the default set
    if 'all' in configured:
        return NLRI.known_families()
    found: list[FamilyTuple] = []
    for afi_keyword in SAFIS:
        # a family named in two family blocks is negotiated once. A loop, not extend() of a
        # generator: mypyc builds the whole list before extending, and let the second one in
        for family in configured.get(afi_keyword, []):
            if family not in found:
                found.append(family)
    return found or default_families()


def check_mandatory(values: dict[str, Any]) -> None:
    missing = [name for name in MANDATORY if name not in values]
    if missing:
        raise ValueError('incomplete neighbor, missing {}'.format(', '.join(missing)))
    tcp_ao = values.get('tcp-ao', {})
    if tcp_ao:
        missing = [name for name in TCP_AO_MANDATORY if name not in tcp_ao]
        if missing:
            raise ValueError('incomplete tcp-ao, missing {}'.format(', '.join(missing)))


def check_role(values: dict[str, Any]) -> None:
    if 'role' not in values:
        return
    if 'local' not in values['role']:
        raise ValueError('incomplete role, missing local')
    if values.get('local-as') is None or values.get('peer-as') is None:
        raise ValueError('role requires explicit local-as and peer-as; auto is not allowed')
    if not values['local-as'] or not values['peer-as']:
        raise ValueError('role requires nonzero explicit local-as and peer-as')
    if values['local-as'] == values['peer-as']:
        raise ValueError('role requires unequal local-as and peer-as (eBGP only)')


def check_confederation(values: dict[str, Any]) -> None:
    if 'confederation' not in values:
        return
    confederation = values['confederation']
    if 'identifier' not in confederation:
        raise ValueError('incomplete confederation, missing identifier')
    if not values.get('local-as') or not values.get('peer-as'):
        raise ValueError('confederation requires explicit local-as and peer-as; auto is not allowed')
    if values['local-as'] == confederation['identifier']:
        raise ValueError('local-as is the Member-AS Number, it can not be the confederation identifier')
    if confederation['identifier'] in tuple(confederation.get('members', ())):
        raise ValueError('the confederation identifier can not also be a member')


def session(values: dict[str, Any]) -> SessionSettings:
    tcp_ao = values.get('tcp-ao', {})
    role = values.get('role', {})
    confederation = values.get('confederation', {})
    settings = SessionSettings(
        peer_address=values['peer-address'],
        local_as=values['local-as'] if values['local-as'] is not None else ASN(0),
        peer_as=values['peer-as'] if values['peer-as'] is not None else ASN(0),
        local_address=values.get('local-address'),
        router_id=values.get('router-id'),
        md5_password=values.get('md5-password', ''),
        md5_base64=values.get('md5-base64', False),
        tcp_ao_keyid=tcp_ao.get('keyid'),
        tcp_ao_algorithm=tcp_ao.get('algorithm', ''),
        tcp_ao_password=tcp_ao.get('password', ''),
        tcp_ao_base64=tcp_ao.get('base64', False),
        connect=values.get('connect', 0),
        listen=values.get('listen', 0),
        passive=values.get('passive', False),
        source_interface=values.get('source-interface', ''),
        outgoing_ttl=values.get('outgoing-ttl'),
        incoming_ttl=values.get('incoming-ttl'),
        local_link_local=values.get('local-link-local'),
        # kept with an auto-discovered local address: it was dropped, even when given
        md5_ip=values.get('md5-ip'),
    )
    if role:
        settings.role = role['local']
        settings.role_strict = role.get('strict', False)
        settings.role_add_meta = role.get('add-meta', True)
    if confederation:
        settings.confederation = confederation['identifier']
        settings.confederation_members = tuple(confederation.get('members', ()))
    return settings


# route-refresh configures both capabilities, route-refresh-normal and -enhanced each one
ROUTE_REFRESH_KEYWORDS = {
    'route-refresh-normal': Capability.CODE.ROUTE_REFRESH,
    'route-refresh-enhanced': Capability.CODE.ENHANCED_ROUTE_REFRESH,
}


def route_refresh(neighbor_capability: NeighborCapability, configured: dict[str, Any]) -> None:
    """What the route refresh statements advertise and require; the specific one wins over route-refresh."""
    both = configured.get('route-refresh')
    advertised: dict[str, bool] = {}
    required: set[CapabilityCode] = set()
    for keyword, code in ROUTE_REFRESH_KEYWORDS.items():
        word = configured.get(keyword, both)
        advertised[keyword] = bool(word)
        if word == REQUIRE:
            required.add(code)
    if advertised['route-refresh-enhanced'] and not advertised['route-refresh-normal']:
        raise ValueError(
            'enhanced route refresh works on the ROUTE-REFRESH message, it is not advertised without route refresh'
        )
    neighbor_capability.route_refresh = TriState.from_bool(advertised['route-refresh-normal'])
    neighbor_capability.enhanced_route_refresh = TriState.from_bool(advertised['route-refresh-enhanced'])
    neighbor_capability.required = neighbor_capability.required | frozenset(required)


def capability(values: dict[str, Any]) -> NeighborCapability:
    configured = values.get('capability', {})
    neighbor_capability = NeighborCapability()
    neighbor_capability.required = frozenset(
        code for name, code in REQUIRABLE.items() if configured.get(name) == REQUIRE
    )
    given = {name: True if value == REQUIRE else value for name, value in configured.items()}
    for name, attribute in TRISTATE_CAPABILITIES.items():
        if name in given:
            setattr(neighbor_capability, attribute, TriState.from_bool(given[name]))
    if 'add-path' in given:
        neighbor_capability.add_path = given['add-path']
    route_refresh(neighbor_capability, configured)
    if 'software-version' in given:
        neighbor_capability.software_version = 'exabgp' if given['software-version'] else None
    if given.get('link-local-nexthop') is not None:
        neighbor_capability.link_local_nexthop = TriState.from_bool(given['link-local-nexthop'])
    if 'link-local-prefer' in given:
        neighbor_capability.link_local_prefer = given['link-local-prefer']
    if 'multiple-labels' in given:
        neighbor_capability.multiple_labels = given['multiple-labels']
    graceful = given.get('graceful-restart', None)
    if graceful is False:
        neighbor_capability.graceful_restart = GracefulRestartConfig.disabled()
    elif isinstance(graceful, int) and 'graceful-restart' in given:
        # 0 is enabled with the hold-time as restart time, filled in when the neighbor is made
        neighbor_capability.graceful_restart = GracefulRestartConfig.with_time(graceful)
    return neighbor_capability


def addpaths(
    values: dict[str, Any], neighbor_capability: NeighborCapability, negotiated: list[FamilyTuple]
) -> list[FamilyTuple]:
    if not neighbor_capability.add_path:
        return []
    add_path = values.get('add-path', {})
    # `add-path { all; }` was ADD-PATH for no family: it is every family, as `family { all; }`
    if not add_path or 'all' in add_path:
        return list(negotiated)
    found: list[FamilyTuple] = []
    for afi_keyword in SAFIS:
        for family, limit in add_path.get(afi_keyword, []):
            # the neighbor's entries come first, then each template's: the first for a family wins
            if family in found:
                continue
            if family not in negotiated:
                log.debug(
                    lazymsg('skipping add-path family {family} as it is not negotiated', family=family), 'configuration'
                )
                continue
            found.append(family)
            if limit > 0:
                neighbor_capability.paths_limit_per_family[family] = limit
    if not found:
        # every family named is one the neighbor does not negotiate: ADD-PATH for none is off
        neighbor_capability.add_path = 0
    return found


def nexthops(
    values: dict[str, Any], neighbor_capability: NeighborCapability, negotiated: list[FamilyTuple]
) -> list[tuple[AFI, SAFI, AFI]]:
    # the capability is on when a nexthop block is present, unless it was set explicitly
    nexthop = values.get('nexthop', {})
    if neighbor_capability.nexthop.is_unset() and nexthop:
        neighbor_capability.nexthop = TriState.TRUE
    if not neighbor_capability.nexthop.is_enabled():
        return []
    found: list[tuple[AFI, SAFI, AFI]] = []
    for afi_keyword in nexthop:
        for entry in nexthop[afi_keyword]:
            afi, safi, _ = entry
            # RFC 8950 needs the family of the route, not the family of its next-hop
            if (afi, safi) not in negotiated:
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
