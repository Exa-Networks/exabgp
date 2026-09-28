"""A route distinguisher and a route target, as the configuration reads them.

RFC 4364 4.2 gives three route distinguisher types, RFC 4360 3.1 and 3.2 the route targets
of the same three shapes: a two octet AS with four octets of number (type 0), an IPv4
address with two (type 1), a four octet AS with two (type 2). The value picks the type.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.lexer import lex_text
from exabgp.configuration.grammar.types.bgp import ROUTE_DISTINGUISHER, extended_community
from exabgp.configuration.grammar.words import Words


def _words(text: str) -> Words:
    statement = lex_text(f'rd {text};')[0]
    return Words(tuple(statement.words[1:]), statement.tokens[-1])


@pytest.mark.parametrize(
    'text,packed',
    [
        ('65000:100', '0000fde800000064'),  # type 0: 2 octet AS, 4 octet number
        ('192.0.2.1:100', '0001c00002010064'),  # type 1: IPv4 address, 2 octet number
        ('4200000000:100', '0002fa56ea000064'),  # type 2: 4 octet AS, 2 octet number
    ],
)
def test_a_route_distinguisher_is_typed_by_its_value(text: str, packed: str) -> None:
    rd = ROUTE_DISTINGUISHER.parse(_words(text))
    assert bytes(rd.pack_rd()).hex() == packed
    assert len(rd) == 8


@pytest.mark.parametrize(
    'text,reason',
    [
        ('65000', 'is not a valid route-distinguisher'),
        ('65000:abc', 'the suffix is a number'),
        ('999.0.0.1:100', 'invalid IPv4 address'),
        ('192.0.2.1:100000', 'suffix must be 0-65535'),  # type 1 keeps two octets for the number
    ],
)
def test_a_route_distinguisher_is_refused(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        ROUTE_DISTINGUISHER.parse(_words(text))


@pytest.mark.parametrize(
    'text,packed',
    [
        ('65000:100', '0002fde800000064'),  # type 0, the target: prefix implied
        ('target:65000:100', '0002fde800000064'),
        ('192.0.2.1:100', '0102c00002010064'),  # type 1
        ('target:192.0.2.1:100', '0102c00002010064'),
        ('4200000000:100', '0202fa56ea000064'),  # type 2
    ],
)
def test_a_route_target_is_typed_by_its_value(text: str, packed: str) -> None:
    assert extended_community(text).community.hex() == packed


@pytest.mark.parametrize(
    'text,reason',
    [
        ('65000:100:200', 'invalid extended community type'),
        ('65000:abc', 'invalid extended community'),
        ('999.0.0.1:100', 'is not a decimal number 0-255'),
        ('192.0.2.1:100000', 'value is too large'),  # type 1 keeps two octets for the number
    ],
)
def test_a_route_target_is_refused(text: str, reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        extended_community(text)
