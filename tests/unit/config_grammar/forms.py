"""The forms corpus: every way of writing every keyword, run through both parsers.

Two sources feed it:

- generated: for every leaf the grammar declares, one form per spelling its type lists in
  `examples()`, so every declared spelling is checked against the legacy parser
- written by hand: spellings and whole documents found by reading or probing the legacy
  parser, which the grammar must match, and invalid forms both must refuse

A form is a statement placed in the smallest document that makes it legal, the WRAPPERS
entry of its section.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from config_grammar.forms_neighbor import BOOLEANS, NEIGHBOR_DOCUMENTS, NEIGHBOR_FORMS, SECTION_NEEDS
from config_grammar.forms_route import (
    ANNOUNCE_FAMILIES,
    ANNOUNCE_FORMS,
    ANNOUNCE_NEXTHOP,
    ANNOUNCE_PREFIX,
    ROUTE_DOCUMENTS_BODY,
    NETMASK_DOCUMENT_BODY,
    ROUTE_VALUE_FORMS,
    RTC_FORMS,
)
from config_grammar.forms_flow import FLOW_DOCUMENT_BODIES, MATCH_FORMS, ROUTE_FORMS, SCOPE_FORMS, THEN_FORMS
from config_grammar.forms_l2vpn import L2VPN_DOCUMENT_BODIES, L2VPN_LEVEL_FORMS, VPLS, VPLS_BLOCK, VPLS_VALUE_FORMS
from config_grammar.forms_neighbor import _N
from config_grammar.forms_operational import OPERATIONAL_DOCUMENT_BODIES, OPERATIONAL_FORMS
from config_grammar.forms_select import SELECT_FORMS
from config_grammar.forms_sr_policy import SR_POLICY_FORMS
from exabgp.configuration.grammar.nodes import Block, Leaf
from exabgp.configuration.grammar.tree.root import ROOT

# {form} is replaced by the statement under test. A form for a mandatory leaf replaces the
# statement the wrapper gives it, so a section has one wrapper per mandatory leaf.
WRAPPERS: dict[tuple[str, ...], dict[str, str]] = {
    ('process',): {
        '': 'process p {{ run /bin/cat; {form}; }}',
        'run': 'process p {{ {form}; }}',
    },
}

NEIGHBOR = (
    'neighbor 127.0.0.1 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; {inner} }}'
)
TEMPLATE = (
    'template {{ neighbor t {{ {inner} }} }} '
    'neighbor 127.0.0.1 {{ inherit t; router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; }}'
)


# how a section below neighbor is opened, when its keyword is not enough
SECTION_OPEN = {'route': 'route 10.0.0.0/24'}


def _nested(path: tuple[str, ...]) -> str:
    """`{form};` inside the sections of the path below neighbor, braces escaped for format."""
    inner = SECTION_NEEDS.get(path, '') + ' {form};'
    for keyword in reversed(path):
        inner = f'{SECTION_OPEN.get(keyword, keyword)} {{{{ {inner} }}}}'
    return inner


def wrapper(path: tuple[str, ...], keyword: str) -> str:
    if path in WRAPPERS:
        wrappers = WRAPPERS[path]
        return wrappers.get(keyword, wrappers[''])
    if path[:1] == ('neighbor',):
        return NEIGHBOR.replace('{inner}', _nested(path[1:]))
    if path[:2] == ('template', 'neighbor'):
        return TEMPLATE.replace('{inner}', _nested(path[2:]))
    raise KeyError(f'no wrapper for the section {"/".join(path)}: its forms can not be tested')


@dataclass(frozen=True)
class Form:
    path: tuple[str, ...]  # the sections the statement sits in, from the top
    statement: str  # without the terminating ;
    # whether the legacy parser accepts it; None for generated forms, which may be refused
    # by the section around them (an IPv6 local-address next to an IPv4 peer)
    valid: bool | None = True

    @property
    def keyword(self) -> str:
        return self.statement.split(' ', 1)[0]

    def document(self) -> str:
        return wrapper(self.path, self.keyword).format(form=self.statement)


# written out here rather than taken from the grammar: the generated forms only check the
# spellings the grammar knows, these check the grammar knows every spelling legacy takes

HAND: list[Form] = [
    *[Form(('process',), f'respawn {spelling}') for spelling in BOOLEANS],
    Form(('process',), 'respawn'),
    *[Form(('process',), f'encoder {spelling}') for spelling in ['text', 'json', 'TEXT', 'Json']],
    *[Form(('process',), f'on-exit {spelling}') for spelling in ['withdraw', 'keep', 'KEEP']],
    # legacy: the words a value does not use are ignored
    Form(('process',), 'respawn false extra'),
    Form(('process',), 'encoder json extra'),
    Form(('process',), 'respawn ""'),
    Form(('process',), 'on-exit "keep"'),
    Form(('process',), 'run /bin/cat "with space" \'and quote\''),
    Form(('process',), 'respawn [ true ]', valid=False),
    Form(('process',), 'respawn 2', valid=False),
    Form(('process',), 'encoder', valid=False),
    Form(('process',), 'encoder jsn', valid=False),
    Form(('process',), 'on-exit maybe', valid=False),
    Form(('process',), 'run', valid=False),
    Form(('process',), 'run ""', valid=False),
    Form(('process',), 'run /nonexistent/program', valid=False),
    Form(('process',), 'run /tmp', valid=False),
    Form(('process',), 'encodr json', valid=False),
    Form(('process',), '', valid=False),
]

# whole documents, for what is not a statement inside one section
DOCUMENTS: list[tuple[str, bool]] = [
    ('process p { run /bin/cat; }', True),
    ('process p { run /bin/cat; } process q { run /bin/cat; respawn false; }', True),
    ('process p { run /bin/cat; }\nprocess q { run /bin/cat; respawn; }', True),
    ('process p { run /bin/cat; run /bin/echo x; }', True),
    ('process p { run /bin/cat; encoder json; encoder text; }', True),
    # legacy: the name is the word after the keyword, whatever it is
    ('process { run /bin/cat; }', True),
    ('process a b { run /bin/cat; }', True),
    ('process p$ { run /bin/cat; }', True),
    ('process p.1-_x { run /bin/cat; }', True),
    # legacy: words before a `}` are ignored
    ('process p { run /bin/cat; hold 1 }', True),
    ('process p { run /bin/cat }', False),
    # legacy: a `}` with nothing open ends the configuration
    ('process p { run /bin/cat; } }', True),
    ('process p { run /bin/cat; } } process q { run /bin/cat; }', True),
    ('process p { run /bin/cat; } } this is ignored {', True),
    # legacy: sections still open at the end are closed
    ('process p { run /bin/cat;', True),
    ('process p { run /bin/cat; } process p { run /bin/cat; }', False),
    ('process p { }', False),
    ('process p { run /bin/cat; respawn { } }', False),
    ('process p { ; run /bin/cat; }', False),
    ('', False),
    ('   ', False),
    ('# only a comment', False),
    ('foo;', False),
    (';', False),
    ('{', False),
    ('unknown { }', False),
    *NEIGHBOR_DOCUMENTS,
    *[
        (NEIGHBOR.replace('{inner}', body).replace('{{', '{').replace('}}', '}'), valid)
        for body, valid in ROUTE_DOCUMENTS_BODY
    ],
]


def _leaves(block: Block, path: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], Leaf]]:
    for child in block.children:
        if isinstance(child, Leaf):
            yield path, child
        else:
            yield from _leaves(child, path + (child.keyword,))


def declared_leaves() -> list[tuple[tuple[str, ...], Leaf]]:
    return list(_leaves(ROOT, ()))


def generated() -> list[Form]:
    forms = []
    for path, leaf in declared_leaves():
        for example in leaf.type.examples():
            forms.append(Form(path, f'{leaf.keyword} {example}'.rstrip(), valid=None))
    return forms


def neighbor_forms() -> list[Form]:
    """Each neighbor form in a neighbor, and in a template it inherits (there, only compared)."""
    forms = []
    for path, statement, valid in NEIGHBOR_FORMS:
        forms.append(Form(('neighbor', *path), statement, valid))
        forms.append(Form(('template', 'neighbor', *path), statement, None))
    return forms


def route_forms() -> list[Form]:
    """Each route value in a one-line route and in a route block, in a neighbor and a template."""
    forms = []
    for value, valid in ROUTE_VALUE_FORMS:
        line = f'route 10.0.0.0/24 next-hop 10.0.0.1 {value}'
        forms.append(Form(('neighbor', 'static'), line, valid))
        forms.append(Form(('template', 'neighbor', 'static'), line, None))
        forms.append(Form(('neighbor', 'static', 'route'), value, valid))
    forms.append(Form(('neighbor', 'static'), 'attributes next-hop 10.0.0.1 nlri nothing', False))
    forms.append(Form(('neighbor', 'static'), 'attribute next-hop 10.0.0.1 nlri nothing', False))
    return forms


def announce_forms() -> list[Form]:
    """Each announce family with the static values (compared only), and the written corpus."""
    forms = []
    for afi, families in ANNOUNCE_FAMILIES.items():
        for family in families:
            for value, _ in ROUTE_VALUE_FORMS:
                line = f'{family} {ANNOUNCE_PREFIX[afi]} next-hop {ANNOUNCE_NEXTHOP[afi]} {value}'
                forms.append(Form(('neighbor', 'announce', afi), line, None))
    for afi, family, rest, valid in ANNOUNCE_FORMS:
        forms.append(Form(('neighbor', 'announce', afi), f'{family} {rest}', valid))
        forms.append(Form(('template', 'neighbor', 'announce', afi), f'{family} {rest}', None))
    # without `family { ipv4 rtc; }` a valid rtc route is refused for its family: compared only
    for path in (('neighbor', 'static'), ('template', 'neighbor', 'static')):
        forms.append(Form(path, 'rtc default next-hop self', None))
    forms.append(Form(('neighbor', 'static'), 'rtc origin-as x route-target 65001:100', False))
    forms.append(Form(('neighbor', 'announce', 'ipv4'), 'rtc default next-hop self', None))
    forms.append(Form(('template', 'neighbor', 'announce', 'ipv4'), 'rtc default next-hop self', None))
    forms.append(Form(('neighbor', 'announce', 'ipv4'), 'rtc origin-as x route-target 65001:100', False))
    return forms


def _rtc_documents() -> list[tuple[str, bool]]:
    documents = []
    for rest, valid in RTC_FORMS:
        for section in ('announce { ipv4 { rtc %s; } }', 'static { rtc %s; }'):
            body = 'family { ipv4 rtc; } ' + section % rest
            documents.append((NEIGHBOR.replace('{inner}', body).replace('{{', '{').replace('}}', '}'), valid))
            template = f'template {{ neighbor t {{ {section % rest} }} }} neighbor 127.0.0.1 {{ inherit t; {_N} family {{ ipv4 rtc; }} }}'
            documents.append((template, valid))
    return documents


def select_forms() -> list[Form]:
    forms = []
    for afi, family, route, valid in SELECT_FORMS:
        forms.append(Form(('neighbor', 'announce', afi), f'{family} {route}', valid))
        forms.append(Form(('template', 'neighbor', 'announce', afi), f'{family} {route}', None))
    return forms


def _sr_policy_path(place: str) -> tuple[str, ...]:
    return ('static',) if place == 'static' else ('announce', place)


def sr_policy_forms() -> list[Form]:
    """Without its families a neighbor refuses some routes and not others: compared only, bar the refused."""
    forms = []
    for place, route, valid in SR_POLICY_FORMS:
        path = _sr_policy_path(place)
        forms.append(Form(('neighbor', *path), f'sr-policy {route}', None if valid else False))
        forms.append(Form(('template', 'neighbor', *path), f'sr-policy {route}', None))
    return forms


def _sr_policy_documents() -> list[tuple[str, bool]]:
    families = 'family { ipv4 sr-policy; ipv6 sr-policy; }'
    documents = []
    for place, route, valid in SR_POLICY_FORMS:
        section = f'sr-policy {route};'
        for keyword in reversed(_sr_policy_path(place)):
            section = f'{keyword} {{ {section} }}'
        documents.append((f'neighbor 127.0.0.1 {{ {_N} {families} {section} }}', valid))
        template = f'template {{ neighbor t {{ {section} }} }} neighbor 127.0.0.1 {{ inherit t; {_N} {families} }}'
        documents.append((template, valid))
    return documents


def all_forms() -> list[Form]:
    return (
        generated()
        + HAND
        + neighbor_forms()
        + route_forms()
        + announce_forms()
        + flow_forms()
        + l2vpn_forms()
        + select_forms()
        + sr_policy_forms()
        + operational_forms()
    )


DOCUMENTS.extend(_rtc_documents())
DOCUMENTS.extend(_sr_policy_documents())
DOCUMENTS.append((NEIGHBOR.replace('{inner}', NETMASK_DOCUMENT_BODY).replace('{{', '{').replace('}}', '}'), True))


def flow_forms() -> list[Form]:
    """Each flow value in its block of a route block, and each match in a one-line route."""
    forms = []
    route = ('neighbor', 'flow', 'route')
    for block, entries in (('match', MATCH_FORMS), ('then', THEN_FORMS), ('scope', SCOPE_FORMS)):
        for statement, valid in entries:
            forms.append(Form(route + (block,), statement, valid))
            forms.append(Form(('template', 'neighbor', 'flow', 'route', block), statement, None))
    for statement, valid in ROUTE_FORMS:
        forms.append(Form(route, statement, valid))
        forms.append(Form(('template', 'neighbor', 'flow', 'route'), statement, None))
    for statement, _ in MATCH_FORMS + THEN_FORMS + SCOPE_FORMS:
        forms.append(Form(('neighbor', 'flow'), f'route destination 10.0.0.0/24 {statement}', None))
        forms.append(Form(('neighbor', 'announce', 'ipv4'), f'flow destination 10.0.0.0/24 {statement}', None))
    forms.append(Form(('neighbor', 'flow'), 'route nothing 1', False))
    forms.append(Form(('neighbor', 'announce', 'ipv4'), 'flow nothing 1', False))
    forms.append(Form(('neighbor', 'announce', 'ipv4'), 'flow-vpn nothing 1', False))
    forms.append(Form(('neighbor', 'announce', 'ipv6'), 'flow-vpn nothing 1', False))
    forms.append(Form(('neighbor', 'announce', 'ipv4'), 'flow-vpn rd 1:1 destination 10.0.0.0/24', None))
    forms.append(Form(('neighbor', 'announce', 'ipv6'), 'flow destination 2001:db8::/32', None))
    forms.append(Form(('neighbor', 'announce', 'ipv6'), 'flow-vpn rd 1:1 destination 2001:db8::/32', None))
    forms.append(Form(('neighbor', 'announce', 'ipv6'), 'flow nothing 1', False))
    for afi in ('ipv4', 'ipv6'):
        forms.append(Form(('template', 'neighbor', 'announce', afi), 'flow destination 10.0.0.0/24', None))
        forms.append(Form(('template', 'neighbor', 'announce', afi), 'flow-vpn rd 1:1 destination 10.0.0.0/24', None))
    forms.append(Form(('template', 'neighbor', 'flow'), 'route destination 10.0.0.0/24', None))
    return forms


_FLOW_ROUTE = 'flow {{ route r {{ %s }} }}'
WRAPPERS[('neighbor', 'flow', 'route')] = {
    '': NEIGHBOR.replace('{inner}', _FLOW_ROUTE % 'match {{ destination 10.0.0.0/24; }} {form};')
}
WRAPPERS[('neighbor', 'flow', 'route', 'match')] = {
    '': NEIGHBOR.replace('{inner}', _FLOW_ROUTE % 'match {{ {form}; }}')
}
for _block in ('then', 'scope'):
    WRAPPERS[('neighbor', 'flow', 'route', _block)] = {
        '': NEIGHBOR.replace(
            '{inner}', _FLOW_ROUTE % ('match {{ destination 10.0.0.0/24; }} %s {{ {form}; }}' % _block)
        )
    }
_TEMPLATE_FLOW = (
    'template {{ neighbor t {{ %s }} }} neighbor 127.0.0.1 {{ inherit t; '
    + _N.replace('{', '{{').replace('}', '}}')
    + ' }}'
)
WRAPPERS[('template', 'neighbor', 'flow', 'route')] = {
    '': _TEMPLATE_FLOW % (_FLOW_ROUTE % 'match {{ destination 10.0.0.0/24; }} {form};')
}
WRAPPERS[('template', 'neighbor', 'flow', 'route', 'match')] = {
    '': _TEMPLATE_FLOW % (_FLOW_ROUTE % 'match {{ {form}; }}')
}
for _block in ('then', 'scope'):
    WRAPPERS[('template', 'neighbor', 'flow', 'route', _block)] = {
        '': _TEMPLATE_FLOW % (_FLOW_ROUTE % ('match {{ destination 10.0.0.0/24; }} %s {{ {form}; }}' % _block))
    }

DOCUMENTS.extend(
    (NEIGHBOR.replace('{inner}', body).replace('{{', '{').replace('}}', '}'), valid)
    for body, valid in FLOW_DOCUMENT_BODIES
)


def l2vpn_forms() -> list[Form]:
    """Each VPLS value on a one-line route, in a vpls block, in an announce family; the l2vpn level."""
    forms = []
    for value, valid in VPLS_VALUE_FORMS:
        forms.append(Form(('neighbor', 'l2vpn'), f'vpls {VPLS} {value}', valid))
        forms.append(Form(('neighbor', 'l2vpn', 'vpls'), value, valid))
        forms.append(Form(('neighbor', 'announce', 'l2vpn'), f'vpls {VPLS} {value}', valid))
        forms.append(Form(('template', 'neighbor', 'l2vpn'), f'vpls {VPLS} {value}', None))
        forms.append(Form(('template', 'neighbor', 'l2vpn', 'vpls'), value, None))
        forms.append(Form(('template', 'neighbor', 'announce', 'l2vpn'), f'vpls {VPLS} {value}', None))
    for statement, valid in L2VPN_LEVEL_FORMS:
        forms.append(Form(('neighbor', 'l2vpn'), statement.rstrip(), valid))
        forms.append(Form(('template', 'neighbor', 'l2vpn'), statement.rstrip(), None))
    return forms


_VPLS_BLOCK = VPLS_BLOCK.replace('{', '{{').replace('}', '}}')
WRAPPERS[('neighbor', 'l2vpn', 'vpls')] = {
    '': NEIGHBOR.replace('{inner}', 'l2vpn {{ vpls site {{ ' + _VPLS_BLOCK + ' {form}; }} }}')
}
# a statement of the l2vpn section follows a vpls route, which it may change; a route stands alone
WRAPPERS[('neighbor', 'l2vpn')] = {
    '': NEIGHBOR.replace('{inner}', f'l2vpn {{{{ vpls {VPLS}; {{form}}; }}}}'),
    'vpls': NEIGHBOR.replace('{inner}', 'l2vpn {{ {form}; }}'),
}
WRAPPERS[('template', 'neighbor', 'l2vpn', 'vpls')] = {
    '': _TEMPLATE_FLOW % ('l2vpn {{ vpls site {{ ' + _VPLS_BLOCK + ' {form}; }} }}')
}
WRAPPERS[('template', 'neighbor', 'l2vpn')] = {
    '': _TEMPLATE_FLOW % f'l2vpn {{{{ vpls {VPLS}; {{form}}; }}}}',
    'vpls': _TEMPLATE_FLOW % 'l2vpn {{ {form}; }}',
}

DOCUMENTS.extend(
    (NEIGHBOR.replace('{inner}', body).replace('{{', '{').replace('}}', '}'), valid)
    for body, valid in L2VPN_DOCUMENT_BODIES
)


def operational_forms() -> list[Form]:
    forms = []
    for statement, valid in OPERATIONAL_FORMS:
        forms.append(Form(('neighbor', 'operational'), statement, valid))
        forms.append(Form(('template', 'neighbor', 'operational'), statement, None))
    return forms


DOCUMENTS.extend(
    (NEIGHBOR.replace('{inner}', body).replace('{{', '{').replace('}}', '}'), valid)
    for body, valid in OPERATIONAL_DOCUMENT_BODIES
)
# the messages of the neighbor, then those of its template
DOCUMENTS.append(
    (
        'template { neighbor t { operational { rpcq afi ipv4 safi unicast sequence 3; } } } '
        f'neighbor 127.0.0.1 {{ inherit t; {_N} operational {{ apcq afi ipv4 safi unicast sequence 4; }} }}',
        True,
    )
)
