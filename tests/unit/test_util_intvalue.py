"""IntValue behaves like the int subclass it replaces, wherever the code relied on that.

Each test sets a value built on IntValue against the same value built on int, the way
AFI, ASN and the message codes were written before plan/wip-mypyc.md, and requires both
to give the same answer.
"""

from __future__ import annotations

import json
import struct
from typing import Any

import pytest

from exabgp.util.intvalue import IntValue, json_number


class Named(IntValue):
    def __str__(self) -> str:
        return 'named'


class OldNamed(int):
    def __str__(self) -> str:
        return 'named'


VALUES = [0, 1, 2, 255, 0x4004, 65535, 4294967295]


@pytest.mark.parametrize('number', VALUES)
def test_equal_and_hashed_like_the_int(number: int) -> None:
    value = Named(number)
    assert value == number and number == value
    assert value == Named(number)
    assert not value != number
    assert value != number + 1 and number + 1 != value
    assert hash(value) == hash(number) == hash(OldNamed(number))
    by_number: dict[object, str] = {number: 'found'}
    by_value: dict[object, str] = {value: 'found'}
    assert by_number[value] == 'found'
    assert by_value[number] == 'found'
    assert value in set(by_number) and number in set(by_value)


def test_not_equal_to_what_is_not_a_number() -> None:
    assert Named(1) != '1'
    assert Named(1) != None  # noqa: E711
    assert Named(1) != 1.5


@pytest.mark.parametrize('number', VALUES)
def test_int_and_percent_d_give_the_number(number: int) -> None:
    value = Named(number)
    assert int(value) == number
    assert '%d' % value == '%d' % OldNamed(number)
    assert struct.pack('!Q', int(value)) == struct.pack('!Q', OldNamed(number))


def test_there_is_no_index_so_every_implicit_use_is_found() -> None:
    """mypyc does not compile __index__, so the pure Python build must not have it either.

    Were it there, bytes([code]) would work in the tests and fail in the compiled build.
    """
    value: Any = Named(1)
    assert not hasattr(value, '__index__')
    with pytest.raises(TypeError):
        bytes([value])
    with pytest.raises(struct.error):
        struct.pack('!H', value)
    with pytest.raises(TypeError):
        hex(value)


@pytest.mark.parametrize('number', VALUES)
def test_formatted_like_an_int_subclass(number: int) -> None:
    value, old = Named(number), OldNamed(number)
    assert f'{value}' == f'{old}' == 'named'
    assert '{}'.format(value) == '{}'.format(old)
    assert '%s' % value == '%s' % old
    assert f'{value:04x}' == f'{old:04x}'
    assert f'{value:d}' == f'{old:d}'


def test_repr_is_the_number_unless_a_subclass_says_otherwise() -> None:
    assert repr(IntValue(12)) == repr(12)
    assert str(IntValue(12)) == str(12)


@pytest.mark.parametrize('number', VALUES)
def test_false_only_when_zero(number: int) -> None:
    assert bool(Named(number)) is bool(OldNamed(number))


def test_ordered_against_values_and_ints() -> None:
    assert Named(1) < Named(2) and Named(1) < 2
    assert Named(2) > Named(1) and Named(2) > 1
    assert Named(2) <= 2 and Named(2) >= 2
    assert 1 < Named(2) and 3 > Named(2)
    assert sorted([Named(3), Named(1), Named(2)]) == [1, 2, 3]


def test_ordered_against_floats_like_the_int() -> None:
    for number in (179.5, 180.0, 180.5):
        assert (Named(180) < number) is (OldNamed(180) < number)
        assert (Named(180) > number) is (OldNamed(180) > number)
        assert (number > Named(180)) is (number > OldNamed(180))
        assert (number <= Named(180)) is (number <= OldNamed(180))
        assert (Named(180) == number) is (OldNamed(180) == number)
        assert (number != Named(180)) is (number != OldNamed(180))


def test_takes_what_int_takes_and_holds_a_plain_int() -> None:
    boolean: int = True
    wrapped: Any = Named(7)
    assert type(IntValue(boolean).value) is int and IntValue(boolean).value == 1
    assert type(IntValue(wrapped).value) is int and IntValue(wrapped).value == 7
    text: Any = '1'
    number: Any = 1.5
    with pytest.raises(TypeError):
        IntValue(text)
    with pytest.raises(TypeError):
        IntValue(number)


def test_json_writes_the_number_as_it_wrote_the_int_subclass() -> None:
    document = {'as': Named(65000), 'list': [Named(1), 2]}
    assert json.dumps(document, default=json_number) == json.dumps({'as': OldNamed(65000), 'list': [OldNamed(1), 2]})


def test_json_still_refuses_what_it_cannot_write() -> None:
    with pytest.raises(TypeError):
        json.dumps({'object': object()}, default=json_number)
