"""session.py

The blocks of a neighbor which describe the session: capabilities, API, TCP-AO, role,
confederation.

Their values are kept as the legacy parser did, by keyword, and the neighbor resolves them.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import re
import time
from typing import Any

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.configuration.grammar.error import ConfigError
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.types.base import Type
from exabgp.configuration.grammar.types.lists import OneOrList
from exabgp.configuration.grammar.types.word import Word, choice, integer, spelled, text
from exabgp.configuration.grammar.words import Words

# the spellings of the boolean validator, and of the older boolean helper some sections use
BOOLEAN_TRUE = ('true', 'enable', 'enabled', 'yes', '1')
BOOLEAN_FALSE = ('false', 'disable', 'disabled', 'no', '0')
ENABLE_TRUE = ('true', 'enable', 'enabled')
ENABLE_FALSE = ('false', 'disable', 'disabled')

REQUIRE = 'require'
GRACEFUL_RESTART_MAX = 4095  # RFC 4724: the restart time is twelve bits
TCP_AO_ALGORITHMS = ['hmac-sha-1-96', 'aes-128-cmac-96', 'hmac-sha-256']
TCP_AO_KEYID_MAX = 255
MAX_LIST_WORDS = 1024  # a bracketed list is written by hand, a real one holds a handful
MAX_CONFEDERATION_MEMBERS = 1024
ROLE_OTC_REMOVED = (
    "'role otc' was removed in 6.0.0: RFC 9234 section 5 says the operator MUST NOT have the "
    'ability to modify the Only-to-Customer procedures. Delete the line; the egress marking is '
    'unconditional for IPv4 and IPv6 unicast.'
)
NAME_CHARACTERS = frozenset('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_')


def boolean(bare: bool | None) -> Word[bool]:
    return spelled('boolean', BOOLEAN_TRUE, BOOLEAN_FALSE, bare)


def enabled(bare: bool | None) -> Word[bool]:
    return spelled('boolean', ENABLE_TRUE, ENABLE_FALSE, bare)


def requirable(bare: bool | None) -> Word[bool | str]:
    """enable, disable, or require: advertise it and refuse a peer which does not (RFC 5492 3)."""

    def convert(word: str) -> bool | str:
        lowered = word.lower()
        if lowered == REQUIRE:
            return REQUIRE
        if lowered in BOOLEAN_TRUE:
            return True
        if lowered in BOOLEAN_FALSE:
            return False
        if not lowered and bare is not None:
            return bare
        raise ValueError(f"'{word}' is not valid, it is enable, disable or require")

    examples = [*BOOLEAN_TRUE, *BOOLEAN_FALSE, REQUIRE, 'Require'] + ([''] if bare is not None else [])
    return Word(
        'requirable',
        'enable|disable|require',
        convert,
        examples,
        render=lambda value: [value if isinstance(value, str) else 'enable' if value else 'disable'],
        choices=['enable', 'disable', REQUIRE],
    )


def _graceful_restart(word: str) -> int | bool:
    if not word:
        return 0
    if word.lower() in ('disable', 'disabled'):
        return False
    try:
        seconds = int(word)
    except ValueError:
        raise ValueError(f"'{word}' is not valid, it is 0-{GRACEFUL_RESTART_MAX} or disable") from None
    if not 0 <= seconds <= GRACEFUL_RESTART_MAX:
        raise ValueError(f'graceful-restart {seconds} is invalid, it is 0-{GRACEFUL_RESTART_MAX}')
    return seconds


GRACEFUL_RESTART = Word(
    'graceful-restart',
    f'<0-{GRACEFUL_RESTART_MAX}>|disable',
    _graceful_restart,
    ['', '0', '120', str(GRACEFUL_RESTART_MAX), 'disable', 'disabled', 'DISABLE'],
    render=lambda value: ['disable' if value is False else str(value)],
)

ADD_PATH_MODES = {'disable': 0, 'disabled': 0, 'receive': 1, 'send': 2, 'send/receive': 3}


def _add_path_mode(word: str) -> int:
    mode = ADD_PATH_MODES.get(word.lower())
    if mode is None:
        raise ValueError(f"'{word.lower()}' is not a valid add-path option")
    return mode


ADD_PATH_MODE = Word(
    'add-path',
    'disable|receive|send|send/receive',
    _add_path_mode,
    [*ADD_PATH_MODES, 'SEND'],
    render=lambda value: [{0: 'disable', 1: 'receive', 2: 'send', 3: 'send/receive'}[value]],
    choices=list(ADD_PATH_MODES),
)

CAPABILITY = Block(
    'capability',
    field='capability',
    doc='the capabilities to negotiate',
    children=(
        Leaf('nexthop', requirable(True), field='nexthop'),
        Leaf('add-path', ADD_PATH_MODE, field='add-path'),
        Leaf('asn4', requirable(True), field='asn4'),
        Leaf('graceful-restart', GRACEFUL_RESTART, field='graceful-restart'),
        Leaf('multi-session', boolean(True), field='multi-session'),
        Leaf('operational', requirable(True), field='operational'),
        Leaf('route-refresh', requirable(True), field='route-refresh'),
        Leaf('aigp', boolean(True), field='aigp'),
        Leaf('extended-message', requirable(True), field='extended-message'),
        Leaf('software-version', requirable(False), field='software-version'),
        Leaf('link-local-nexthop', requirable(None), field='link-local-nexthop'),
        Leaf('link-local-prefer', boolean(False), field='link-local-prefer'),
    ),
)


def _regular_expression(word: str) -> str:
    try:
        re.compile(word)
    except re.error as exc:
        raise ValueError(f"'{word}' is not a valid regular expression: {exc}") from None
    return word


def _direction(keyword: str) -> Block:
    names = (
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
    return Block(
        keyword,
        field=keyword,
        doc=f'the messages {keyword == "send" and "sent" or "received"} which are given to the program',
        children=tuple(Leaf(name, boolean(True), field=name) for name in names),
    )


class APIName(Type[str]):
    """The optional name of an api block; without one it is named for the time it was read."""

    name = 'api name'

    def parse(self, words: Words) -> str:
        where = words.where()
        name = words.word() or 'auto-named-%d' % int(time.time() * 1000000)
        if any(character not in NAME_CHARACTERS for character in name):
            raise ConfigError(where, 'invalid character in name for api')
        return name

    def render(self, value: str) -> list[str]:
        return [] if value.startswith('auto-named-') else [value]

    def hint(self) -> str:
        return '[<name>]'

    def examples(self) -> list[str]:
        return ['', 'name', 'a.b-c_d']


def _api(name: str, values: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    # legacy: api names are unique across the whole configuration, not per neighbor
    used: set[str] = context.setdefault('api-names', set())
    if name in used:
        raise ValueError(f'the name "{name}" already exists in api')
    used.add(name)
    return values


API = Block(
    'api',
    field='api',
    build=_api,
    keep=Keep.NAMED,
    name=APIName(),
    doc='which API programs hear about this neighbor, and what they hear',
    children=(
        Leaf('processes', OneOrList(text('process'), 'processes', single=False), field='processes'),
        Leaf(
            'processes-match',
            OneOrList(
                Word('regular expression', '<regex>', _regular_expression, ['^a', 'b$']),
                'processes-match',
                single=False,
            ),
            field='processes-match',
        ),
        Leaf('neighbor-changes', enabled(True), field='neighbor-changes'),
        Leaf('negotiated', enabled(True), field='negotiated'),
        Leaf('fsm', enabled(True), field='fsm'),
        Leaf('signal', enabled(True), field='signal'),
        _direction('send'),
        _direction('receive'),
    ),
)

TCP_AO = Block(
    'tcp-ao',
    field='tcp-ao',
    doc='TCP-AO (RFC 5925) authentication',
    children=(
        Leaf('keyid', integer('keyid', 0, TCP_AO_KEYID_MAX), field='keyid'),
        Leaf('algorithm', choice('algorithm', TCP_AO_ALGORITHMS), field='algorithm'),
        Leaf('password', text('password'), field='password'),
        Leaf('base64', boolean(False), field='base64'),
    ),
)


def _role(word: str) -> RoleValue:
    return RoleValue.from_string(word)


def _role_switch(word: str) -> bool:
    if word not in ('enable', 'disable'):
        raise ValueError('role setting requires enable or disable')
    return word == 'enable'


ROLE_SWITCH = Word(
    'role setting',
    'enable|disable',
    _role_switch,
    ['enable', 'disable'],
    render=lambda value: ['enable' if value else 'disable'],
    choices=['enable', 'disable'],
)


def _removed(word: str) -> bool:
    raise ValueError(ROLE_OTC_REMOVED)


ROLE = Block(
    'role',
    field='role',
    doc='the RFC 9234 role of this router on the session',
    children=(
        Leaf(
            'local',
            Word(
                'role',
                '|'.join(str(role) for role in RoleValue.assigned()),
                _role,
                [str(role) for role in RoleValue.assigned()],
            ),
            field='local',
        ),
        Leaf('strict', ROLE_SWITCH, field='strict'),
        Leaf('add-meta', ROLE_SWITCH, field='add-meta'),
        Leaf('otc', Word('otc', '', _removed, []), field='otc'),
    ),
)


def _identifier(word: str) -> ASN:
    value = ASN.from_string(word)
    if not value:
        raise ValueError('the confederation identifier can not be AS 0')
    return value


class Members(Type[tuple[ASN, ...]]):
    """One AS number, or a list of them in brackets, kept as a tuple.

    A tuple, as the legacy parser kept it: a template and the neighbor inheriting it can not
    both give members (`transfer` refuses to merge a tuple), where a list would be joined.
    """

    name = 'confederation members'

    def __init__(self) -> None:
        self._list = OneOrList(
            Word('as-number', '<asn>', ASN.from_string, ['65001', '65002']),
            'confederation members',
            max_items=MAX_CONFEDERATION_MEMBERS,
        )

    def parse(self, words: Words) -> tuple[ASN, ...]:
        return tuple(self._list.parse(words))

    def render(self, value: tuple[ASN, ...]) -> list[str]:
        return self._list.render(list(value))

    def hint(self) -> str:
        return self._list.hint()

    def examples(self) -> list[str]:
        return self._list.examples()


CONFEDERATION = Block(
    'confederation',
    field='confederation',
    doc='RFC 5065 BGP confederation',
    children=(
        Leaf('identifier', Word('as-number', '<asn>', _identifier, ['65000', '1.1']), field='identifier'),
        Leaf('members', Members(), field='members'),
    ),
)
