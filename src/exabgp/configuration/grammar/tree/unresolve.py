"""unresolve.py

The statements which make a NeighborSettings: the inverse of resolve.py, for printing.

Everything is written out, defaults included, so the printed neighbor does not depend on
what the defaults of the reader are. Values are given the way each leaf reads them: one
entry per statement for the leaves which may be repeated.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from collections import Counter
from itertools import count
from typing import Any, Iterator

from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.neighbor.capability import NeighborCapability
from exabgp.bgp.neighbor.settings import NeighborSettings, SessionSettings
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.nlri.empty import Empty
from exabgp.configuration.grammar.tree.family import SAFIS, default_families
from exabgp.configuration.grammar.tree.resolve import API_COMMANDS, API_MESSAGES, REQUIRABLE, REQUIRE
from exabgp.protocol.family import AFI, FamilyTuple
from exabgp.util.enumeration import TriState


def _afi_keyword(afi: AFI) -> str:
    for keyword, safis in SAFIS.items():
        if any(family[0] == afi for family in safis.values()):
            return keyword
    raise ValueError(f'no family keyword for {afi}')


def _session(session: SessionSettings) -> dict[str, Any]:
    values: dict[str, Any] = {
        'local-as': session.local_as,
        'peer-as': session.peer_as,
        'passive': session.passive,
        'md5-base64': session.md5_base64,
    }
    optional = {
        'local-address': session.local_address,
        'local-link-local': session.local_link_local,
        'router-id': session.router_id,
        'md5-password': session.md5_password or None,
        'md5-ip': session.md5_ip if session.local_address is not None else None,
        'source-interface': session.source_interface or None,
        'outgoing-ttl': session.outgoing_ttl,
        'incoming-ttl': session.incoming_ttl,
        'listen': session.listen or None,
        'connect': session.connect or None,
    }
    values.update({keyword: value for keyword, value in optional.items() if value is not None})
    if session.tcp_ao_password:
        values['tcp-ao'] = {
            'keyid': session.tcp_ao_keyid,
            'algorithm': session.tcp_ao_algorithm,
            'password': session.tcp_ao_password,
            'base64': session.tcp_ao_base64,
        }
    if session.role != RoleValue.NO_ROLE:
        values['role'] = {'local': session.role, 'strict': session.role_strict, 'add-meta': session.role_add_meta}
    if session.confederation:
        values['confederation'] = {
            'identifier': session.confederation,
            'members': tuple(session.confederation_members),
        }
    return values


def _tristate(state: TriState) -> bool | None:
    return None if state.is_unset() else state.is_enabled()


def _capability(cap: NeighborCapability) -> dict[str, Any]:
    values: dict[str, Any] = {
        'asn4': _tristate(cap.asn4),
        'extended-message': _tristate(cap.extended_message),
        'multi-session': _tristate(cap.multi_session),
        'operational': _tristate(cap.operational),
        'nexthop': _tristate(cap.nexthop),
        'aigp': _tristate(cap.aigp),
        'link-local-nexthop': _tristate(cap.link_local_nexthop),
        'add-path': cap.add_path,
        'route-refresh': bool(cap.route_refresh),
        'software-version': cap.software_version is not None,
        'link-local-prefer': cap.link_local_prefer,
        'graceful-restart': cap.graceful_restart.time if cap.graceful_restart.is_enabled() else False,
    }
    for name, code in REQUIRABLE.items():
        if code in cap.required:
            values[name] = REQUIRE
    return {keyword: value for keyword, value in values.items() if value is not None}


def _families(settings: NeighborSettings) -> dict[str, Any] | None:
    # the defaults hold families no statement names (ipv6 multicast): they are said by omission
    if not settings.prefix_limit:
        if settings.families == default_families():
            return None
        if settings.families == NLRI.known_families():
            return {'all': [None]}
    family: dict[str, Any] = {}
    for each in settings.families:
        family.setdefault(_afi_keyword(each[0]), []).append((each, settings.prefix_limit.get(each, 0)))
    return family


def _add_path(settings: NeighborSettings) -> dict[str, Any] | None:
    if not settings.capability.add_path:
        return None
    if not settings.addpaths:
        # legacy: `add-path { all; }` negotiates ADD-PATH for no family, the one way to say none
        return {'all': [None]}
    if settings.addpaths == settings.families and not settings.capability.paths_limit_per_family:
        # no add-path block: every negotiated family, some of which no statement can name
        return None
    limits: dict[FamilyTuple, int] = settings.capability.paths_limit_per_family
    add_path: dict[str, Any] = {}
    for each in settings.addpaths:
        add_path.setdefault(_afi_keyword(each[0]), []).append((each, limits.get(each, 0)))
    return add_path


def _api(api: dict[str, Any], names: Iterator[int]) -> dict[str, Any]:
    """One api block per process, with the flags of that process; the matches in a block of their own."""
    blocks: dict[str, Any] = {}
    # a process may be listed more than once, each time with its own flags: the n-th block
    # of a process has a flag when the process is in that flag's list at least n times
    written: Counter[str] = Counter()
    for process in api.get('processes', []):
        written[process] += 1
        nth = written[process]
        block: dict[str, Any] = {'processes': [process]}
        for command in API_COMMANDS:
            block[command] = api.get(command, []).count(process) >= nth
        for direction in ('send', 'receive'):
            block[direction] = {
                message: api.get(f'{direction}-{message}', []).count(process) >= nth for message in API_MESSAGES
            }
        blocks[f'api-{next(names)}'] = block
    if api.get('processes-match'):
        blocks[f'api-{next(names)}'] = {'processes-match': list(api['processes-match'])}
    return blocks


def _routes(routes: list[Any]) -> dict[str, Any]:
    """The static and announce sections which print the routes, each where a statement reads it back.

    The order of the routes is kept within a section, not across them: a route only an announce
    family writes follows the static routes.
    """
    from exabgp.bgp.message.update.nlri import RTC
    from exabgp.configuration.grammar.tree.announce import announce_family

    static: dict[str, list[Any]] = {'_routes': [], '_attributes': [], '_rtc': []}
    announce: dict[str, dict[str, list[Any]]] = {}
    for route in routes:
        if isinstance(route.nlri, Empty):
            static['_attributes'].append([route])
        elif isinstance(route.nlri, RTC):
            static['_rtc'].append([route])
        elif (place := announce_family(route)) is not None:
            announce.setdefault(place[0], {}).setdefault(f'_{place[1]}', []).append([route])
        else:
            static['_routes'].append([route])
    printed: dict[str, Any] = {'static': static}
    if announce:
        printed['announce'] = announce
    return printed


def neighbor_values(settings: NeighborSettings, context: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """The name and the statements of the neighbor block which reads back as `settings`.

    api blocks are named when printed, counting through the configuration printed: one left
    unnamed is named for the microsecond it is read in, and two could share it.
    """
    names: Iterator[int] = context.setdefault('api-names', count(1))
    values = _session(settings.session)
    values.update(
        {
            'description': settings.description or None,
            'hold-time': int(settings.hold_time),
            'rate-limit': settings.rate_limit,
            'host-name': settings.host_name or None,
            'domain-name': settings.domain_name or None,
            'group-updates': settings.group_updates,
            'as-set': settings.as_set,
            'auto-flush': settings.auto_flush,
            'adj-rib-in': settings.adj_rib_in,
            'adj-rib-out': settings.adj_rib_out,
            'manual-eor': settings.manual_eor,
            'shutdown': settings.shutdown,
            'capability': _capability(settings.capability),
            'family': _families(settings),
            'add-path': _add_path(settings),
            'api': _api(settings.api, names) or None,
        }
    )
    if settings.routes:
        values.update(_routes(settings.routes))
    nexthop: dict[str, Any] = {}
    for entry in settings.nexthops:
        nexthop.setdefault(entry[0].name(), []).append(entry)
    if nexthop:
        values['nexthop'] = nexthop
    return settings.session.peer_address, {keyword: value for keyword, value in values.items() if value is not None}
