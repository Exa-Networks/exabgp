"""The as-path of a route: what the configuration reads and what exabgp prints.

    as-path [ 1 2 ] ( 3 4 ) confed-sequence [ 5 ] confed-set [ 6 7 ];

`[ ]` is an AS_SEQUENCE and `( )` an AS_SET.  The two confederation segments are named,
because `{` and `}` delimit sections in the configuration and could never be read inside
a route: `as-path [ { 5 } ]`, which the parser claimed to accept, failed in every form.

What exabgp prints has to read back as the same path.  It printed a sequence with `( )`
and a set with `[ ]`, so a route shown by exabgp and given back to it swapped them.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.aspath import (
    CONFED_SEQUENCE,
    CONFED_SET,
    SEQUENCE,
    SET,
    AS2Path,
    ASPath,
)
from exabgp.configuration.grammar.lexer import lex_text
from exabgp.configuration.grammar.types.bgp import MAX_SEGMENT_ASNS, ASPathType
from exabgp.configuration.grammar.words import Words


def parse(text: str) -> ASPath:
    statement = lex_text(f'as-path {text};')[0]
    return ASPathType().parse(Words(tuple(statement.words[1:]), statement.tokens[-1]))


def shape(path: ASPath) -> list[tuple[str, list[int]]]:
    return [(type(segment).__name__, [int(asn) for asn in segment]) for segment in path.aspath]


# ==============================================================================
# Reading
# ==============================================================================


@pytest.mark.parametrize(
    'text,expected',
    [
        ('65001', [('SEQUENCE', [65001])]),
        ('[ 1 2 ]', [('SEQUENCE', [1, 2])]),
        ('( 3 4 )', [('SET', [3, 4])]),
        ('[ 1 , 2 ]', [('SEQUENCE', [1, 2])]),
        ('confed-sequence [ 5 6 ]', [('CONFED_SEQUENCE', [5, 6])]),
        ('confed-set [ 7 ]', [('CONFED_SET', [7])]),
        ('confed-set ( 7 8 )', [('CONFED_SET', [7, 8])]),
        (
            'confed-sequence [ 5 ] [ 1 2 ] ( 3 4 )',
            [('CONFED_SEQUENCE', [5]), ('SEQUENCE', [1, 2]), ('SET', [3, 4])],
        ),
        ('[ ]', []),
    ],
)
def test_the_configuration_reads(text: str, expected: list) -> None:
    assert shape(parse(text)) == expected


@pytest.mark.parametrize(
    'text',
    [
        '[ 1 2 )',  # closed with the wrong bracket
        '[ 1 2',  # never closed
        '( )',  # an empty segment
        '[ 1 ] ( )',
        'confed-set 7',  # a keyword with no bracket
        'confed-sequence { 5 }',  # the braces which never worked
        '[ 1 two ]',
    ],
)
def test_a_malformed_as_path_is_refused(text: str) -> None:
    with pytest.raises(ValueError):
        parse(text)


def test_a_segment_is_capped_at_what_its_length_octet_holds() -> None:
    parse('[ ' + ' '.join(['1'] * MAX_SEGMENT_ASNS) + ' ]')

    with pytest.raises(ValueError):
        parse('[ ' + ' '.join(['1'] * (MAX_SEGMENT_ASNS + 1)) + ' ]')


# ==============================================================================
# Printing reads back
# ==============================================================================


def test_a_sequence_prints_with_square_brackets_and_a_set_with_round_ones() -> None:
    path = AS2Path.make_aspath([SEQUENCE([ASN(1), ASN(2)]), SET([ASN(3), ASN(4)])], True)

    assert str(path) == '[ 1 2 ] ( 3 4 )'


@pytest.mark.parametrize(
    'segments',
    [
        [SEQUENCE([ASN(1), ASN(2)]), SET([ASN(3), ASN(4)])],
        [CONFED_SEQUENCE([ASN(5)]), CONFED_SET([ASN(6), ASN(7)]), SEQUENCE([ASN(1)])],
        [SET([ASN(9)])],
    ],
)
def test_what_exabgp_prints_it_reads_back_as_the_same_path(segments: list) -> None:
    path = AS2Path.make_aspath(segments, True)

    assert shape(parse(str(path))) == shape(path)
