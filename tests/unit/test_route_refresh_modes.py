"""Route refresh, RFC 2918, and enhanced route refresh, RFC 7313, configured together or apart.

`route-refresh enable|disable|require` configures both capabilities, as it always did, and
`require` requires both of the peer. `route-refresh-normal` and `route-refresh-enhanced`
configure one each, and win over `route-refresh` for it, whatever their order. Enhanced route
refresh works on the ROUTE-REFRESH message: advertised without route refresh, it is refused.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.configuration import Configuration
from exabgp.util.enumeration import TriState

NORMAL = Capability.CODE.ROUTE_REFRESH
ENHANCED = Capability.CODE.ENHANCED_ROUTE_REFRESH
ON, OFF = TriState.TRUE, TriState.FALSE
TEMPLATE = (
    'neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-address 192.0.2.2; local-as 65001; peer-as 65002; '
    'capability {{ {statements} }} }}'
)

# the statements, whether each capability is advertised, what is required of the peer, and
# how they are printed back
CASES = [
    ('', OFF, OFF, set(), 'route-refresh disable;'),
    ('route-refresh disable;', OFF, OFF, set(), 'route-refresh disable;'),
    ('route-refresh enable;', ON, ON, set(), 'route-refresh enable;'),
    ('route-refresh require;', ON, ON, {NORMAL, ENHANCED}, 'route-refresh require;'),
    (
        'route-refresh-normal enable;',
        ON,
        OFF,
        set(),
        'route-refresh-normal enable;route-refresh-enhanced disable;',
    ),
    (
        'route-refresh-normal require; route-refresh-enhanced disable;',
        ON,
        OFF,
        {NORMAL},
        'route-refresh-normal require;route-refresh-enhanced disable;',
    ),
    (
        'route-refresh enable; route-refresh-normal require;',
        ON,
        ON,
        {NORMAL},
        'route-refresh-normal require;route-refresh-enhanced enable;',
    ),
    (
        'route-refresh-enhanced require; route-refresh enable;',
        ON,
        ON,
        {ENHANCED},
        'route-refresh-normal enable;route-refresh-enhanced require;',
    ),
    ('route-refresh-normal enable; route-refresh-enhanced enable;', ON, ON, set(), 'route-refresh enable;'),
]


def neighbor(statements: str) -> Neighbor:
    configuration = Configuration([TEMPLATE.format(statements=statements)], text=True)
    assert configuration.reload(), str(configuration.error)
    (found,) = configuration.neighbors.values()
    return found


@pytest.mark.parametrize('statements,normal,enhanced,required,printed', CASES)
def test_the_statements_advertise_and_require(
    statements: str, normal: TriState, enhanced: TriState, required: set[int], printed: str
) -> None:
    capability = neighbor(statements).capability
    assert capability.route_refresh == normal
    assert capability.enhanced_route_refresh == enhanced
    assert capability.required & {NORMAL, ENHANCED} == required


@pytest.mark.parametrize('statements,normal,enhanced,required,printed', CASES)
def test_they_are_printed_back_as_statements_which_read_the_same(
    statements: str, normal: TriState, enhanced: TriState, required: set[int], printed: str
) -> None:
    capability = neighbor(statements).capability
    written = ''.join(f'{keyword} {word};' for keyword, word in capability.route_refresh_statements())
    assert written == printed
    again = neighbor(written).capability
    assert (again.route_refresh, again.enhanced_route_refresh, again.required) == (
        capability.route_refresh,
        capability.enhanced_route_refresh,
        capability.required,
    )


@pytest.mark.parametrize('spelling,advertised', [('true', ON), ('', ON), ('no', OFF), ('Require', ON)])
def test_the_older_spellings_keep_their_meaning(spelling: str, advertised: TriState) -> None:
    capability = neighbor(f'route-refresh {spelling};').capability
    assert capability.route_refresh == advertised
    assert capability.enhanced_route_refresh == advertised


@pytest.mark.parametrize(
    'statements', ['route-refresh-enhanced enable;', 'route-refresh enable; route-refresh-normal disable;']
)
def test_enhanced_route_refresh_is_not_advertised_alone(statements: str) -> None:
    configuration = Configuration([TEMPLATE.format(statements=statements)], text=True)
    assert not configuration.reload()
    assert 'not advertised without route refresh' in str(configuration.error)
