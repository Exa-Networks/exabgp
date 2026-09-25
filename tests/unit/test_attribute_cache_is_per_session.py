"""What a set of attribute bytes means depends on the session that received them.

`Attributes.unpack` memoised the last parse in `cls.cached` and `cls.previous`, two class
attributes shared by every session in the process, keyed on the wire bytes alone. The wire
bytes do not say what they mean:

- AS_PATH is read two octets at a time or four, on `negotiated.asn4` (RFC 6793 4.2.2)
- AIGP is accepted only where the session asked for it, and `unpack` answers None where it
  did not (RFC 7311 3.2)
- AGGREGATOR is six octets or eight, again on `negotiated.asn4`

So one peer's negotiation decided how the next peer's UPDATE was read, and the worst of it
is not a rendering difference: a route which the second session must treat as withdrawn was
installed instead, because the first session had parsed the same bytes successfully.

The cache now lives on `Negotiated`. Two attributes whose own `unpack` reads `negotiated`,
Aggregator and AIGP, additionally have `CACHING = False`, because `Attribute.cache` is keyed
by code and value and is still shared. The other nine cacheable attributes were checked and
none of them reads `negotiated`.
"""

from __future__ import annotations

from struct import pack
from typing import Any

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute, Attributes
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.aigp import AIGP
from exabgp.environment import getenv
from exabgp.logger import log

log.init(getenv())


def session(asn4: bool = False, aigp: bool = False) -> Any:
    negotiated = Negotiated({'capability': {'aigp': aigp}})
    negotiated.asn4 = asn4
    return negotiated


# one AS_SEQUENCE of one four octet ASN 65538. Read two octets at a time the same six bytes
# are a sequence of one with two octets left over, which is malformed.
AS_PATH = bytes([0x40, 0x02, 6]) + pack('!BB', 2, 1) + pack('!I', 65538)

AIGP_WIRE = bytes([0x80, 0x1A, 11]) + bytes([1]) + pack('!H', 11) + pack('!Q', 5)


def test_a_four_octet_path_is_not_read_as_four_on_a_two_octet_session() -> None:
    """The defect, stated as the outcome that matters: a route installed, not withdrawn."""
    Attributes.unpack(AS_PATH, Direction.IN, session(asn4=True))

    second = Attributes.unpack(AS_PATH, Direction.IN, session(asn4=False))

    assert Attribute.CODE.INTERNAL_TREAT_AS_WITHDRAW in second, (
        'the session which did not negotiate four octet AS numbers was handed the parse '
        'belonging to the session which did'
    )
    assert Attribute.CODE.AS_PATH not in second


def test_the_two_sessions_do_not_share_the_parsed_object() -> None:
    first = Attributes.unpack(AS_PATH, Direction.IN, session(asn4=True))
    second = Attributes.unpack(AS_PATH, Direction.IN, session(asn4=True))

    assert first is not second, 'one session was handed the object belonging to another'


def test_one_session_still_reuses_its_own_last_parse() -> None:
    """The cache is the point of the code and has to keep working, per session."""
    one = session(asn4=True)

    first = Attributes.unpack(AS_PATH, Direction.IN, one)
    again = Attributes.unpack(AS_PATH, Direction.IN, one)

    assert first is again


def test_a_session_which_refused_aigp_is_not_handed_one() -> None:
    """RFC 7311 3.2: AIGP is accepted only where the session asked for it."""
    asked = Attributes.unpack(AIGP_WIRE, Direction.IN, session(aigp=True))
    assert Attribute.CODE.AIGP in asked

    refused = Attributes.unpack(AIGP_WIRE, Direction.IN, session(aigp=False))

    assert Attribute.CODE.AIGP not in refused, 'an AIGP arrived on a session which refused it'


@pytest.mark.parametrize('klass,reads', [(Aggregator, 'negotiated.asn4'), (AIGP, 'negotiated.aigp')])
def test_an_attribute_whose_parse_reads_the_session_is_not_shared(klass: Any, reads: str) -> None:
    """`Attribute.cache` is keyed by code and value and shared, so these must stay out of it."""
    assert klass.CACHING is False, f'{klass.__name__}.unpack reads {reads}, so it cannot be cached by value'


def test_no_other_cacheable_attribute_reads_the_session() -> None:
    """The floor: if a new cacheable attribute starts reading negotiated, this fails.

    Checked by reading the source rather than by calling, because the fault is that a parse
    which depends on the session gets stored under a key which does not mention it, and that
    is visible in the code and invisible at runtime until two sessions differ.
    """
    import ast
    import pathlib

    offenders = []
    root = pathlib.Path(__file__).parent.parent.parent / 'src' / 'exabgp'
    walked = 0
    for path in root.rglob('*.py'):
        text = path.read_text()
        if 'CACHING = True' not in text:
            continue
        walked += 1
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == 'unpack':
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Attribute) and isinstance(sub.value, ast.Name):
                        if sub.value.id == 'negotiated':
                            offenders.append(f'{path.name}:{node.lineno} reads negotiated.{sub.attr}')

    assert walked >= 8, f'only {walked} cacheable attributes found, the scan is looking in the wrong place'
    assert not offenders, 'cacheable attributes whose parse depends on the session: ' + '; '.join(offenders)
