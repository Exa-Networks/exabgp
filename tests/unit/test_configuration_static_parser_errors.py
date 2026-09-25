"""Two static configuration parsers answered a mistyped value with the wrong exception.

`Configuration.reload` has a catch-all which turns any exception into "problem parsing
configuration file line N / error message: <exc>", so neither of these killed the daemon.
What they cost is the diagnostic: the operator was shown the internals of the failure
instead of the token they wrote.

`static/parser.py prefix()` built an `IPRange` straight from the token.  That reaches
`socket.inet_pton`, which answers a malformed address with a bare `OSError`, so
`route 999.999.999.999/24` reported "illegal IP address string passed to inet_pton" and
named neither the address nor what was wrong with it.  The `# XXX: could raise` comment on
the line above was the whole of the handling.

`static/mpls.py prefix_sid()` assigns `label_sid` only inside its `if value == '[':` branch,
and reads `int(label_sid)` after the `try` has closed, so `bgp-prefix-sid 300` raised
`UnboundLocalError` past the handler which exists to report a malformed attribute.  That is
the same shape as the route-distinguisher defect pinned in
`tests/unit/test_route_distinguisher_configuration.py`.
"""

from __future__ import annotations

from typing import Any

import pytest

from exabgp.configuration.core.tokeniser import Iterator
from exabgp.configuration.static.mpls import prefix_sid
from exabgp.configuration.static.parser import prefix


def tokeniser_returning(*values: str) -> Any:
    """The production token iterator, primed with a fixed sequence."""
    return Iterator().replenish(list(values))


@pytest.mark.parametrize(
    'token',
    ['999.999.999.999/24', 'not-an-ip', '10.0.0.0/33', '2001:db8::1:invalid/64'],
)
def test_an_unparseable_prefix_is_a_configuration_error(token: str) -> None:
    """OSError is the defect: the configuration layer reports what it is handed."""
    with pytest.raises(ValueError) as raised:
        prefix(tokeniser_returning(token))

    assert token.split('/')[0] in str(raised.value), 'the error does not name the address the operator wrote'


@pytest.mark.parametrize('token', ['300', '(', ''], ids=['bare-number', 'wrong-bracket', 'nothing'])
def test_a_prefix_sid_without_an_opening_bracket_is_a_configuration_error(token: str) -> None:
    """UnboundLocalError reached the operator from outside the try which should have caught it."""
    with pytest.raises(ValueError):
        prefix_sid(tokeniser_returning(token))


# --- the negative space: the forms an operator really writes -----------------------------


@pytest.mark.parametrize('token', ['10.0.0.0/24', '192.0.2.0/24', '2001:db8::/32', '10.0.0.1'])
def test_a_well_formed_prefix_still_parses(token: str) -> None:
    """Every refusal above is satisfied by a parser which refuses everything."""
    parsed = prefix(tokeniser_returning(token))

    assert str(parsed).startswith(token.split('/')[0])


def test_a_well_formed_prefix_sid_still_parses() -> None:
    parsed = prefix_sid(tokeniser_returning('[', '300', ']'))

    assert parsed is not None


def test_a_network_with_host_bits_set_is_still_refused() -> None:
    """The check which was already there must survive the new one wrapping the line above it."""
    with pytest.raises(ValueError):
        prefix(tokeniser_returning('10.0.0.1/24'))
