"""BitResource.named: a `+`-joined bitmask is the bits it names, each once.

The parts were added, so naming a bit twice carried it into the next one: a flow matching
`fragment is-fragment+is-fragment` was sent as first-fragment (2 + 2 = 4), and
`tcp-flags syn+syn` as rst (2 + 2 = 4). A bitmask is the union of its bits.
"""

from __future__ import annotations

import pytest

from exabgp.protocol.ip.fragment import Fragment
from exabgp.protocol.ip.tcp.flag import TCPFlag


@pytest.mark.parametrize(
    'word,value',
    [
        ('syn', TCPFlag.SYN),
        ('syn+ack', TCPFlag.SYN | TCPFlag.ACK),
        ('syn+syn', TCPFlag.SYN),
        ('syn+ack+syn', TCPFlag.SYN | TCPFlag.ACK),
        ('0x12+syn', TCPFlag.SYN | TCPFlag.ACK),
    ],
)
def test_tcp_flags_named_twice_are_one_bit(word: str, value: int) -> None:
    assert int(TCPFlag.named(word)) == value


@pytest.mark.parametrize(
    'word,value',
    [
        ('is-fragment', Fragment.IS),
        ('is-fragment+is-fragment', Fragment.IS),
        ('first-fragment+is-fragment', Fragment.FIRST | Fragment.IS),
        ('dont-fragment+dont-fragment+last-fragment', Fragment.DONT | Fragment.LAST),
    ],
)
def test_fragment_bits_named_twice_are_one_bit(word: str, value: int) -> None:
    assert int(Fragment.named(word)) == value


def test_a_repeated_bit_still_prints_as_the_bit() -> None:
    assert str(TCPFlag.named('syn+syn')) == 'syn'
    assert str(Fragment.named('is-fragment+is-fragment')) == 'is-fragment'
