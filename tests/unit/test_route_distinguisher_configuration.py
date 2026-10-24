"""A route-distinguisher the operator mistyped crashed the parser, or reached the wire short.

`configuration/static/mpls.py route_distinguisher()` only assigned `prefix` and `suffix` when
the token held a ':' past index 0.  `rd 12345` and `rd :100` left both unbound and the next
line raised `UnboundLocalError`: an unhandled traceback out of the configuration parser,
where every other malformed value there is a `ValueError` naming the token.

The worse half is silent.  RFC 4364 section 4.2 gives a type 1 route-distinguisher two octets
of type, four of IPv4 administrator and two of assigned number.  Nothing counted the octets
the operator wrote, and `RouteDistinguisher.__init__` does not check its own length either,
so `rd 1.2:100` packed six bytes, `rd 1.2.3:100` seven and `rd 1.2.3.4.5:100` nine.  All three
were accepted at configuration time and sent to the peer as a route-distinguisher no receiver
can read, with no diagnostic anywhere.

The remaining cases reported something, but named a fragment rather than the line:
`bytes([400])` says only "bytes must be in range(0, 256)", `int('abc')` says only
"invalid literal for int() with base 10: 'abc'", and a negative field passed the two
unbounded `<` comparisons and reached `struct.pack`, which raises `struct.error`, not a
`ValueError` the configuration layer knows how to report.

`route_distinguisher()` is shared: `mvpn_sharedjoin`, `mvpn_sourcejoin`, `mvpn_sourcead` and
the `srv6_mup_*` parsers call it with no wrapping of their own, so two of those are exercised
below rather than assumed.
"""

from __future__ import annotations

from typing import Any

import pytest

from exabgp.configuration.core.tokeniser import Iterator
from exabgp.configuration.static.mpls import mvpn_sharedjoin, route_distinguisher, srv6_mup_isd
from exabgp.protocol.family import AFI

IPV4_RD_OCTETS = 4
RD_SIZE = 8


def tokeniser_returning(*values: str) -> Any:
    """The production token iterator, primed with a fixed sequence.

    Not a Mock: the parsers reached below rely on `consume()` and on '' rather than an
    exception once the tokens run out, and a stub which answers differently would pin a
    behaviour the configuration layer does not have.
    """
    return Iterator().replenish(list(values))


@pytest.mark.parametrize('token', ['12345', ':100'], ids=['no-colon', 'leading-colon'])
def test_a_route_distinguisher_with_no_usable_separator_is_a_configuration_error(token: str) -> None:
    """UnboundLocalError is the defect: the parser cannot report what it did not assign."""
    with pytest.raises(ValueError) as raised:
        route_distinguisher(tokeniser_returning(token))

    assert token in str(raised.value), 'the error does not name the token the operator wrote'


@pytest.mark.parametrize('token', ['1.2:100', '1.2.3:100', '1.2.3.4.5:100'])
def test_a_wrong_ipv4_octet_count_is_refused_rather_than_packed(token: str) -> None:
    """Six, seven and nine octet route-distinguishers were sent to the peer."""
    with pytest.raises(ValueError) as raised:
        route_distinguisher(tokeniser_returning(token))

    assert token in str(raised.value)


@pytest.mark.parametrize(
    'token',
    ['abc:100', '1.2.3.400:100', '1.2.3.abc:100', '192.0.2.1:abc'],
)
def test_an_unreadable_field_names_the_whole_token(token: str) -> None:
    with pytest.raises(ValueError) as raised:
        route_distinguisher(tokeniser_returning(token))

    assert token in str(raised.value), 'the error names a fragment rather than the configuration line'


@pytest.mark.parametrize('token', ['-1:1', '1:-1', '192.0.2.1:-1'])
def test_a_negative_field_is_a_value_error_and_not_a_struct_error(token: str) -> None:
    """Both comparisons had no lower bound, so a negative number reached struct.pack."""
    with pytest.raises(ValueError) as raised:
        route_distinguisher(tokeniser_returning(token))

    assert token in str(raised.value)


def test_the_shared_function_reaches_the_mvpn_caller() -> None:
    """mvpn_sharedjoin does no wrapping of its own, so the fix has to arrive through it."""
    tokeniser = tokeniser_returning('rp', '1.2.3.4', 'group', '5.6.7.8', 'rd', '12345', 'source-as', '100')

    with pytest.raises(ValueError) as raised:
        mvpn_sharedjoin(tokeniser, AFI.ipv4, None)

    assert '12345' in str(raised.value)


def test_the_shared_function_reaches_the_srv6_mup_caller() -> None:
    tokeniser = tokeniser_returning('10.0.0.0/24', 'rd', '12345')

    with pytest.raises(ValueError) as raised:
        srv6_mup_isd(tokeniser, AFI.ipv4)

    assert '12345' in str(raised.value)


# --- the negative space: the forms an operator really writes -----------------------------


@pytest.mark.parametrize(
    'token,expected',
    [
        ('192.0.2.1:100', bytes([0, 1, 192, 0, 2, 1, 0, 100])),
        ('100:1', bytes([0, 0]) + bytes([0, 100]) + bytes([0, 0, 0, 1])),
        ('70000:1', bytes([0, 2]) + bytes([0, 1, 17, 112]) + bytes([0, 1])),
    ],
    ids=['type-1-ipv4', 'type-0-two-byte-asn', 'type-2-four-byte-asn'],
)
def test_a_well_formed_route_distinguisher_packs_exactly_eight_bytes(token: str, expected: bytes) -> None:
    """Every refusal above is satisfied by a parser which refuses everything."""
    parsed: Any = route_distinguisher(tokeniser_returning(token))

    assert len(parsed.pack()) == RD_SIZE
    assert parsed.pack() == expected
