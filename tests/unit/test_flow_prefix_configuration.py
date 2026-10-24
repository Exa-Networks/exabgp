"""A flow source/destination the parser could not read was dropped without a word.

`source()` and `destination()` in `exabgp/configuration/flow/parser.py` are generators
with three `if`/`elif` branches: IPv4, IPv6, IPv6-with-offset.  There was no `else`, so a
token matching none of them yielded nothing and raised nothing.  The caller,
`configuration/flow/__init__.py route()`, does `for adding in known[command](tokeniser):
change.nlri.add(adding)`, and an empty generator adds no component.

`flow { route x { match { source not-an-ip; } then { discard; } } }` therefore loaded, and
announced a FlowSpec NLRI of one byte, `00`: no components at all.  RFC 8955 section 4.2
makes such a rule a match on *every* packet, so a mistyped address turned a narrow filter
into discard-all.  Measured before the fix, through `Configuration.reload()`:

    changes: 1
    nlri str   : flow
    rules      : {}
    extensive  : flow extended-community rate-limit:0
    pack_nlri(): 00

The same function had a second, separate defect: nothing bounded the netmask or the IPv6
offset.  `int(netmask)` was handed straight to the component, which packs it into a single
wire byte, so `source 10.0.0.0/33` reached the wire as `0602210a000000` -- component type
2, prefix length `0x21`, which is not a legal IPv4 prefix length -- and an IPv6
`/64/200` packed an offset of 200 into `030240c8`.

Both are now configuration errors naming the token, in the shape
`configuration/static/mpls.py` uses for `route_distinguisher` and `prefix_sid`.
"""

from __future__ import annotations

from typing import Any

import pytest

from exabgp.bgp.message.update.nlri.flow import (
    Flow4Destination,
    Flow4Source,
    Flow6Destination,
    Flow6Source,
)
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.core.tokeniser import Iterator
from exabgp.configuration.flow.parser import destination, source
from exabgp.environment import getenv
from exabgp.logger import log

log.init(getenv())


def tokeniser_returning(*values: str) -> Any:
    """The production token iterator, primed with a fixed sequence."""
    return Iterator().replenish(list(values))


FLOW_CONFIGURATION = """
neighbor 127.0.0.1 {
    router-id 1.2.3.4;
    local-address 127.0.0.1;
    local-as 1;
    peer-as 1;
    family { %(family)s; }
    flow {
        route test {
            match { source %(token)s; }
            then { discard; }
        }
    }
}
"""


def load_flow(token: str, family: str = 'ipv4 flow') -> Any:
    """Parse a whole configuration the way the daemon does, not the helper alone."""
    text = FLOW_CONFIGURATION % dict(token=token, family=family)
    configuration = Configuration([text], text=True)
    return configuration.reload(), configuration


# --- the defect: the whole configuration, as an operator would meet it --------------------


def test_an_unparseable_source_does_not_become_a_match_everything_rule() -> None:
    """The measured failure: the rule loaded, with a one byte, no component NLRI."""
    ok, configuration = load_flow('not-an-ip')

    assert not ok, 'the configuration loaded, announcing a FlowSpec rule with no components'
    assert 'not-an-ip' in configuration.error.message


def test_an_out_of_range_netmask_does_not_reach_the_wire() -> None:
    """0x21 is not an IPv4 prefix length; the refusal belongs at configuration time."""
    ok, configuration = load_flow('10.0.0.0/33')

    assert not ok, 'a /33 loaded and packed 0x21 as the FlowSpec prefix length'
    assert '33' in configuration.error.message


def test_a_valid_flow_configuration_still_loads_and_still_packs_its_component() -> None:
    """Every refusal above is satisfied by a parser which refuses everything."""
    ok, configuration = load_flow('10.0.0.0/24')

    assert ok, configuration.error.message
    neighbor = next(iter(configuration.neighbors.values()))
    nlri = neighbor.changes[0].nlri
    assert nlri.pack_nlri() == bytes.fromhex('0502180a0000')


def test_a_valid_ipv6_flow_configuration_with_an_offset_still_loads() -> None:
    """`source ::1/128/120` is in etc/exabgp/conf-flow.conf and must keep working."""
    ok, configuration = load_flow('::1/128/120', family='ipv6 flow')

    assert ok, configuration.error.message


# --- the live path: `announce flow route ...` over the API --------------------------------
# A mitigation box injects its rules at runtime, so this is the path which mattered.  At
# HEAD `api_flow()` handed the reactor one Change packing `00`, and `inject_change` sent it.


def announce_flow(line: str) -> Any:
    """Drive `api_flow()`'s parsing half: what the reactor is handed for an API line."""
    configuration = Configuration([])
    configuration.flow.clear()
    if not configuration.partial('flow', line):
        return None, configuration
    return configuration.scope.pop_routes(), configuration


def test_an_unparseable_source_over_the_api_yields_no_route() -> None:
    routes, configuration = announce_flow('route { match { source not-an-ip; } then { discard; } }')

    assert routes is None, 'the API injected a FlowSpec rule with no components'
    assert 'not-an-ip' in configuration.error.message


def test_an_out_of_range_netmask_over_the_api_yields_no_route() -> None:
    routes, configuration = announce_flow('route { match { source 10.0.0.0/33; } then { discard; } }')

    assert routes is None, 'the API injected a rule whose prefix length was 0x21'
    assert '33' in configuration.error.message


def test_a_valid_source_over_the_api_still_yields_its_route() -> None:
    routes, configuration = announce_flow('route { match { source 10.0.0.0/24; } then { discard; } }')

    assert routes is not None, configuration.error.message
    assert len(routes) == 1
    assert routes[0].nlri.pack_nlri() == bytes.fromhex('0502180a0000')


# --- the helpers, one token at a time ----------------------------------------------------


UNRECOGNISED = ['not-an-ip', '10.0.0/24', '10.0.0.0', 'route', '']


@pytest.mark.parametrize('parser', [source, destination], ids=['source', 'destination'])
@pytest.mark.parametrize('token', UNRECOGNISED, ids=[_ or 'empty' for _ in UNRECOGNISED])
def test_a_token_matching_no_branch_is_a_configuration_error(parser: Any, token: str) -> None:
    with pytest.raises(ValueError) as raised:
        list(parser(tokeniser_returning(token)))

    if token:
        assert token in str(raised.value), 'the error does not name the token the operator wrote'


BAD_CONVERSION = ['10.0.0.256/24', '10.0.0.0/abc', '2001:db8:::/32', '2001:db8::/abc']


@pytest.mark.parametrize('parser', [source, destination], ids=['source', 'destination'])
@pytest.mark.parametrize('token', BAD_CONVERSION)
def test_a_token_a_branch_cannot_convert_is_a_configuration_error(parser: Any, token: str) -> None:
    with pytest.raises(ValueError) as raised:
        list(parser(tokeniser_returning(token)))

    assert token in str(raised.value), 'the error does not name the token the operator wrote'


OUT_OF_RANGE = [
    ('10.0.0.0/33', 'netmask 33'),
    ('10.0.0.0/99', 'netmask 99'),
    ('10.0.0.0/-1', 'netmask -1'),
    ('2001:db8::/129', 'netmask 129'),
    ('2001:db8::/-1', 'netmask -1'),
    ('2001:db8::/64/64', 'offset 64'),
    ('2001:db8::/64/200', 'offset 200'),
    ('2001:db8::/64/-1', 'offset -1'),
    ('2001:db8::/0/1', 'offset 1'),
]


@pytest.mark.parametrize('parser', [source, destination], ids=['source', 'destination'])
@pytest.mark.parametrize('token, expected', OUT_OF_RANGE, ids=[_[0] for _ in OUT_OF_RANGE])
def test_a_netmask_or_offset_outside_its_range_is_a_configuration_error(parser: Any, token: str, expected: str) -> None:
    with pytest.raises(ValueError) as raised:
        list(parser(tokeniser_returning(token)))

    assert expected in str(raised.value)


# --- the negative space: the boundaries of the new range checks --------------------------
# A range check which is one off at a boundary breaks a working deployment, which is worse
# than the bug, so every edge the operator can write has its own case.


ACCEPTED = [
    '10.0.0.0/0',
    '10.0.0.0/24',
    '10.0.0.0/32',
    '0.0.0.0/32',
    '255.255.255.255/32',
    '2001:db8::/0',
    '2001:db8::/32',
    '2001:db8::/128',
    '::/0',
    '::/0/0',
    '2001:db8::/32/0',
    '2001:db8::/48/16',
    '::1/128/120',
    '2a02:b80:15::7aca:39ff:feae:a87a/128/0',
]


@pytest.mark.parametrize('token', ACCEPTED)
def test_a_well_formed_source_still_parses(token: str) -> None:
    parsed = list(source(tokeniser_returning(token)))

    assert len(parsed) == 1
    assert isinstance(parsed[0], (Flow4Source, Flow6Source))


@pytest.mark.parametrize('token', ACCEPTED)
def test_a_well_formed_destination_still_parses(token: str) -> None:
    parsed = list(destination(tokeniser_returning(token)))

    assert len(parsed) == 1
    assert isinstance(parsed[0], (Flow4Destination, Flow6Destination))


@pytest.mark.parametrize('parser', [source, destination], ids=['source', 'destination'])
def test_the_offset_the_operator_wrote_survives_the_bound_check(parser: Any) -> None:
    parsed = list(parser(tokeniser_returning('2001:db8::/48/16')))

    assert parsed[0].offset == 16
