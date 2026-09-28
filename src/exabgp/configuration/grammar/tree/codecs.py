"""codecs.py

The parts of a neighbor, each read from the values of the neighbor block into its
NeighborSettings and printed back (a Codec, section.py): the rules are in resolve.py and
unresolve.py, a codec pairs the two for one part and names the statements it owns.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.neighbor.settings import NeighborSettings
from exabgp.configuration.grammar.context import PrintContext
from exabgp.configuration.grammar.render import STATEMENTS
from exabgp.configuration.grammar.section import Codec, Values
from exabgp.configuration.grammar.tree import resolve, unresolve
from exabgp.configuration.grammar.tree.operational import kind
from exabgp.logger import lazymsg, log


class SessionCodec(Codec):
    """The TCP session and who is at each end of it."""

    fields = (
        'peer-address',
        'local-address',
        'local-link-local',
        'local-as',
        'peer-as',
        'router-id',
        'passive',
        'listen',
        'connect',
        'source-interface',
        'outgoing-ttl',
        'incoming-ttl',
        'md5-password',
        'md5-base64',
        'md5-ip',
        'tcp-ao',
        'role',
        'confederation',
    )

    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        resolve.check_mandatory(values)
        resolve.check_role(values)
        resolve.check_confederation(values)
        settings.session = resolve.session(values)

    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        # the peer-address is the name of the neighbor block
        return unresolve.session_values(settings.session)


class FamilyCodec(Codec):
    """The families negotiated, and the prefix limit of each."""

    fields = ('family',)

    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        settings.families = resolve.families(values)
        limits = values.get('family', {}).get('prefix-limit', [])
        settings.prefix_limit = {family: limit for family, limit in limits if family in settings.families}

    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        return {'family': unresolve.families(settings)}


class CapabilityCodec(Codec):
    """What the OPEN advertises, and requires of the peer."""

    fields = ('capability',)

    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        settings.capability = resolve.capability(values)

    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        return {'capability': unresolve.capability(settings.capability)}


# the policy statements, each set on the NeighborSettings field of the same name
POLICY = (
    'description',
    'rate-limit',
    'host-name',
    'domain-name',
    'group-updates',
    'as-set',
    'tunnel-encapsulation',
    'route-target-filter',
    'auto-flush',
    'adj-rib-in',
    'adj-rib-out',
    'manual-eor',
    'shutdown',
)


class PolicyCodec(Codec):
    """How the neighbor is run: its timers, its RIBs, what is sent to it."""

    fields = ('hold-time', *POLICY)

    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        hold_time = values.get('hold-time')
        if hold_time is not None:
            settings.hold_time = HoldTime(hold_time)
        for keyword in POLICY:
            if values.get(keyword) is not None:
                setattr(settings, keyword.replace('-', '_'), values[keyword])

    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        values: Values = {keyword: getattr(settings, keyword.replace('-', '_')) for keyword in POLICY}
        values['hold-time'] = int(settings.hold_time)
        # an empty text is said by omission, a statement can not give it
        for keyword in ('description', 'host-name', 'domain-name'):
            values[keyword] = values[keyword] or None
        return values


class AddPathCodec(Codec):
    """The families ADD-PATH is negotiated for, and their PATHS-LIMIT."""

    fields = ('add-path',)

    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        settings.addpaths = resolve.addpaths(values, settings.capability, settings.families)

    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        return {'add-path': unresolve.add_path(settings)}


class NextHopCodec(Codec):
    """The families whose next-hop may be of the other address family (RFC 8950)."""

    fields = ('nexthop',)

    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        settings.nexthops = resolve.nexthops(values, settings.capability, settings.families)

    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        nexthop: dict[str, Any] = {}
        for entry in settings.nexthops:
            nexthop.setdefault(entry[0].name(), []).append(entry)
        return {'nexthop': nexthop or None}


class APICodec(Codec):
    """Which API programs hear about the neighbor, and what they hear."""

    fields = ('api',)

    def resolve(self, values: Values, settings: NeighborSettings) -> None:
        settings.api = resolve.api(values.get('api', {}))

    def unresolve(self, settings: NeighborSettings, context: PrintContext) -> Values:
        return {'api': unresolve.api(settings.api, context.api_names) or None}


# in their order: a codec reads what the ones before it set
CODECS: tuple[Codec, ...] = (
    SessionCodec(),
    FamilyCodec(),
    CapabilityCodec(),
    PolicyCodec(),
    AddPathCodec(),
    NextHopCodec(),
    APICodec(),
)

# the fields of a neighbor block no codec owns: the neighbor section itself handles them
NEIGHBOR_FIELDS = ('inherit', 'static', 'announce', 'flow', 'l2vpn', 'operational')


def neighbor_settings(values: Values) -> NeighborSettings:
    """The NeighborSettings the values of a neighbor block, its templates merged, make."""
    settings = NeighborSettings()
    for codec in CODECS:
        codec.resolve(values, settings)
    if settings.capability.route_refresh.is_enabled() and not settings.adj_rib_out:
        log.warning(
            lazymsg(
                'neighbor.route_refresh.adj_rib_out peer={peer} action=auto_enabled reason=route_refresh_requires_cache',
                peer=settings.session.peer_address,
            ),
            'configuration',
        )
        settings.adj_rib_out = True
    return settings


def neighbor_values(settings: NeighborSettings, context: PrintContext) -> tuple[Any, Values]:
    """The name and the statements of the neighbor block which reads back as `settings`.

    Everything is written out, defaults included, so the printed neighbor does not depend on
    what the defaults of the reader are.
    """
    values: Values = {}
    for codec in CODECS:
        values.update(codec.unresolve(settings, context))
    if settings.routes:
        values.update(unresolve.routes(settings.routes))
    if settings.operational:
        values['operational'] = {STATEMENTS: [(kind(message), message) for message in settings.operational]}
    return settings.session.peer_address, {keyword: value for keyword, value in values.items() if value is not None}
