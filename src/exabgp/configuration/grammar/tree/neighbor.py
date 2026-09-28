"""neighbor.py

    neighbor <ip>[/<mask>] {
        local-as <asn>|auto; peer-as <asn>|auto; router-id <ipv4>; ...
        family { ... } capability { ... } api [<name>] { ... } ...
    }
    template { neighbor <name> { ... } }

A template holds the same statements as a neighbor, and a neighbor takes them with
`inherit <name>;` or `inherit [ <name> ... ];`.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any

from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.neighbor.settings import NeighborSettings
from exabgp.configuration.grammar import shape
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.shape import Shape
from exabgp.configuration.grammar.nodes import Block, Collect, Keep, Leaf
from exabgp.configuration.grammar.tree.family import ADD_PATH, FAMILY, NEXTHOP
from exabgp.configuration.grammar.tree.resolve import inherit, neighbor_settings
from exabgp.configuration.grammar.tree.announce import ANNOUNCE_BLOCK, STATIC
from exabgp.configuration.grammar.tree.flow import FLOW
from exabgp.configuration.grammar.tree.l2vpn import L2VPN_SECTION
from exabgp.configuration.grammar.tree.operational import OPERATIONAL
from exabgp.configuration.grammar.tree.static import ROUTES
from exabgp.configuration.grammar.tree.unresolve import neighbor_values
from exabgp.configuration.grammar.tree.session import (
    API,
    CAPABILITY,
    CONFEDERATION,
    NAME_CHARACTERS,
    ROLE,
    TCP_AO,
    boolean,
)
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.types.network import (
    ASN_OR_AUTO,
    HOLD_TIME,
    IP_ADDRESS,
    IP_OR_AUTO,
    IP_RANGE,
    PORT,
    ROUTER_ID,
    TTL,
)
from exabgp.configuration.grammar.types.word import Word, choice, integer, text
from exabgp.configuration.grammar.words import Words
from exabgp.environment import getenv
from exabgp.logger import lazymsg, log
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IPRange
from exabgp.util.psk import guessed_as_base64

MD5_BASE64_AUTO_REMOVED = (
    "'auto' guessed whether md5-password was base64 by looking at the password, and a "
    'hexadecimal password was decoded into a different key, so it was removed in 6.0. '
    'Use "md5-base64 true;" if the password is base64, or "md5-base64 false;" to use it '
    'exactly as it is written'
)


def _md5_base64(word: str) -> bool:
    status = word.lower()
    if status == 'auto':
        raise ValueError(MD5_BASE64_AUTO_REMOVED)
    if not status:
        return False
    if status in ('true', 'enable', 'enabled'):
        return True
    if status in ('false', 'disable', 'disabled'):
        return False
    raise ValueError(f"'{status}' is not a valid boolean")


MD5_BASE64 = Word(
    'md5-base64',
    'true|false',
    _md5_base64,
    ['true', 'enable', 'enabled', 'false', 'disable', 'disabled', '', 'TRUE'],
    render=lambda value: ['true' if value else 'false'],
    choices=['true', 'false'],
    shape=shape.boolean(),
)


# legacy: inherit takes any word, a template is only named with these characters
TEMPLATE_NAME_SHAPE = shape.string(pattern=r'[a-zA-Z0-9._-]+')


class Inherit(Type[list[str]]):
    """`inherit <name>;` or `inherit [ <name> ... ];`.

    legacy: the list is every word between the brackets, a comma included, and a name which
    is no template is ignored.
    """

    name = 'template names'

    def parse(self, words: Words) -> list[str]:
        where = words.where()
        found = [token.word for token in words.rest()]
        if len(found) == 1:
            return found
        if len(found) < 3 or found[0] != '[' or found[-1] != ']':
            raise ConfigError(where, 'invalid inherit list', expected=['<template>', '[ <template> ... ]'])
        return found[1:-1]

    def render(self, value: list[str]) -> list[str]:
        return value if len(value) == 1 else ['[', *value, ']']

    def hint(self) -> str:
        return '<template>|[ <template> ... ]'

    def examples(self) -> list[str]:
        return ['t', '[ t ]', '[ t u ]', '[ t, u ]']

    def shape(self) -> Shape:
        return shape.leaf_list(TEMPLATE_NAME_SHAPE, min_items=1)


class TemplateName(Type[str]):
    """The name of a template: letters, digits and `.-_`; with no name the `{` is the name, and refused."""

    name = 'template name'

    def parse(self, words: Words) -> str:
        where = words.where()
        name = '{' if words.at_end() else words.word()
        if any(character not in NAME_CHARACTERS for character in name):
            raise ConfigError(where, 'invalid character in name for template-neighbor')
        return name

    def render(self, value: str) -> list[str]:
        return [value]

    def hint(self) -> str:
        return '<name>'

    def examples(self) -> list[str]:
        return ['t', 'a.b-c_d']

    def shape(self) -> Shape:
        return TEMPLATE_NAME_SHAPE


LEAVES = (
    Leaf('peer-address', IP_RANGE, field='peer-address', doc='the peer, or the peers of a range'),
    Leaf('local-address', IP_OR_AUTO, field='local-address', doc='the address to connect from, auto to find it'),
    Leaf('local-link-local', IP_ADDRESS, field='local-link-local', doc='the IPv6 link-local address (fe80::/10)'),
    Leaf('local-as', ASN_OR_AUTO, field='local-as', doc='our AS, auto to use the peer AS', needed=True),
    Leaf('peer-as', ASN_OR_AUTO, field='peer-as', doc='the peer AS, auto to use ours', needed=True),
    Leaf('router-id', ROUTER_ID, field='router-id', doc='the BGP identifier, the local address by default'),
    Leaf('description', text('description'), field='description', doc='free text about the neighbor'),
    Leaf('host-name', text('host-name'), field='host-name', doc='sent in the hostname capability'),
    Leaf('domain-name', text('domain-name'), field='domain-name', doc='sent in the hostname capability'),
    Leaf('hold-time', HOLD_TIME, field='hold-time', doc='seconds, 0 disables the hold timer'),
    Leaf('rate-limit', integer('rate-limit'), field='rate-limit', doc='UPDATE messages per second'),
    Leaf('passive', boolean(True), field='passive', doc='wait for the peer to connect'),
    Leaf('listen', PORT, field='listen', doc='the port to listen on'),
    Leaf('connect', PORT, field='connect', doc='the port to connect to'),
    Leaf(
        'source-interface',
        text('source-interface'),
        field='source-interface',
        doc='the interface the session is bound to',
    ),
    Leaf('outgoing-ttl', TTL, field='outgoing-ttl', doc='the TTL of the packets sent, for a multihop session or GTSM'),
    Leaf('incoming-ttl', TTL, field='incoming-ttl', doc='the lowest TTL accepted (GTSM)'),
    Leaf('md5-password', text('md5-password'), field='md5-password', doc='the TCP MD5 signature key, RFC 2385'),
    Leaf('md5-base64', MD5_BASE64, field='md5-base64', doc='the md5-password is base64 encoded'),
    Leaf(
        'md5-ip',
        IP_ADDRESS,
        field='md5-ip',
        doc='the local address the TCP MD5 key is set on, the local-address by default',
    ),
    Leaf(
        'as-set',
        choice('as-set', ['withdraw', 'accept']),
        field='as-set',
        doc='RFC 9774, what to do with a route with an AS_SET',
    ),
    Leaf(
        'group-updates', boolean(True), field='group-updates', doc='send routes with the same attributes in one UPDATE'
    ),
    Leaf(
        'auto-flush',
        boolean(True),
        field='auto-flush',
        doc='send the routes an API command changes without waiting for a flush',
    ),
    Leaf(
        'adj-rib-out',
        boolean(False),
        field='adj-rib-out',
        doc='keep the routes sent, to send them again on a route refresh or a new session',
    ),
    Leaf('adj-rib-in', boolean(False), field='adj-rib-in', doc='keep the routes received'),
    Leaf(
        'manual-eor',
        boolean(False),
        field='manual-eor',
        doc='send the End-of-RIB markers only when the API asks for them',
    ),
    Leaf('shutdown', boolean(False), field='shutdown', doc='start with the session administratively down'),
    Leaf(
        'inherit',
        Inherit(),
        field='inherit',
        collect=Collect.EXTEND,
        doc='the templates whose statements the neighbor takes',
    ),
)

SECTIONS = (
    FAMILY,
    CAPABILITY,
    TCP_AO,
    ROLE,
    CONFEDERATION,
    ADD_PATH,
    NEXTHOP,
    API,
    STATIC,
    ANNOUNCE_BLOCK,
    FLOW,
    L2VPN_SECTION,
    OPERATIONAL,
)


def _check(neighbor: Neighbor, context: dict[str, Any]) -> None:
    """The checks the legacy parser made on the Neighbor it built."""
    interface = neighbor.session.source_interface
    if interface and len(interface) > MAX_INTERFACE_NAME:
        raise ValueError(f'source-interface {interface} is longer than {MAX_INTERFACE_NAME} characters')
    if interface and (any(c.isspace() for c in interface) or '/' in interface):
        raise ValueError(f'source-interface {interface} is not a valid interface name')
    session = neighbor.session
    if not session.auto_discovery and session.local_address.is_link_local():
        if not neighbor.capability.link_local_nexthop.is_enabled():
            raise ValueError('a link-local local-address requires capability link-local-nexthop enable')
        if session.outgoing_ttl is not None and session.outgoing_ttl > 1:
            raise ValueError('a link-local local-address can not be used on a multihop session')
    missing = neighbor.missing()
    if missing:
        raise ValueError(f'incomplete neighbor, missing {missing}')
    if not session.auto_discovery and session.local_address.afi != session.peer_address.afi:
        raise ValueError('local-address and peer-address must be of the same family')
    if session.local_link_local is not None and not session.local_link_local.is_link_local():
        raise ValueError('local-link-local must be an IPv6 link-local address (fe80::/10)')
    error = session.validate_md5() or session.validate_tcp_ao()
    if error:
        raise ValueError(error)
    # the peer-address of a neighbor block is always a range, read by IP_RANGE
    assert isinstance(session.peer_address, IPRange)
    size = session.peer_address.mask.size()
    if size > 1 and not (session.passive or getenv().bgp.passive):
        raise ValueError('can only use ip ranges for the peer address with passive neighbors')
    index = neighbor.index()
    seen: list[bytes] = context.setdefault('neighbor-index', [])
    if index in seen:
        raise ValueError(f'duplicate peer definition {session.peer_address}')
    seen.append(index)


# Linux caps an interface name at IFNAMSIZ, which leaves fifteen characters
MAX_INTERFACE_NAME = 15


def _neighbor(name: Any, values: dict[str, Any], context: dict[str, Any]) -> NeighborSettings:
    # the name is the peer-address, a peer-address statement in the block replaces it
    values.setdefault('peer-address', name)
    # legacy: the routes read since the last neighbor or template closed are this neighbor's
    routes = context.pop(ROUTES, [])
    inherit(values, context.setdefault('templates', {}))
    settings = neighbor_settings(values)
    settings.routes = routes + [
        route for section in ('static', 'l2vpn', 'flow') for route in values.get(section, {}).get('routes', [])
    ]
    settings.routes += values.get('routes', [])
    settings.operational = list(values.get('operational', {}).get('routes', []))
    neighbor = Neighbor.from_settings(settings, rib=False)
    _check(neighbor, context)
    _check_routes(neighbor)
    if 'md5-base64' not in values:
        _warn_hexadecimal_password(neighbor)
    return settings


def _warn_hexadecimal_password(neighbor: Neighbor) -> None:
    """Releases before 6.0 decoded an all hexadecimal password as base64 (#1423)."""
    if not guessed_as_base64(neighbor.session.md5_password):
        return
    log.warning(
        lazymsg(
            'the md5-password for {peer} is hexadecimal, which releases before 6.0 decoded as base64. '
            'It is now used exactly as it is written. Add "md5-base64 true;" if this session used '
            'to establish and needs the decoded key, or "md5-base64 false;" if the password is '
            'right as written, which also silences this message.',
            peer=neighbor.session.peer_address,
        ),
        'configuration',
    )


def _check_routes(neighbor: Neighbor) -> None:
    """Every route resolves its next-hop self, and is of a family the neighbor negotiates."""
    families = neighbor.families()
    for route in neighbor.routes:
        try:
            neighbor.resolve_self(route)
        except TypeError as exc:
            raise ValueError(str(exc)) from None
        family = route.nlri.family().afi_safi()
        if family not in families and family != (AFI.ipv4, SAFI.unicast):
            raise ValueError(
                f'Trying to announce a route of type {family[0]},{family[1]} when we are not announcing the family to our peer'
            )


def _template(name: Any, values: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    templates: dict[str, dict[str, Any]] = context.setdefault('templates', {})
    if name in templates:
        raise ValueError(f'the name "{name}" already exists in template-neighbor')
    values.setdefault('routes', []).extend(context.pop(ROUTES, []))
    templates[name] = values
    return values


NEIGHBOR = Block(
    'neighbor',
    field='neighbors',
    build=_neighbor,
    keep=Keep.LIST,
    name=IP_RANGE,
    doc='a BGP peer',
    complete=True,
    children=LEAVES + SECTIONS,
    unbuild=neighbor_values,
)

TEMPLATE = Block(
    'template',
    field='template',
    doc='statements shared by neighbors',
    children=(
        Block(
            'neighbor',
            field='neighbor',
            build=_template,
            keep=Keep.NAMED,
            name=TemplateName(),
            doc='a template, the statements of a neighbor which inherits it',
            children=LEAVES + SECTIONS,
        ),
    ),
)
