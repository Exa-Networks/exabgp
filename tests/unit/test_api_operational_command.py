"""An API operational command reads its message.

The words are the command split on spaces. The advisory is the text after its keyword, a pair
of quotes around it removed: the legacy parser kept the quotes in the advisory, and of a text
of several words sent the first. The other expectations were taken from the legacy parser
(configuration/operational/parser.py) before it was removed.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.read import read_operational

READ = [
    ('asm', 'afi ipv4 safi unicast advisory "hello"', 'operational ASM afi ipv4 safi unicast "68656c6c6f"', None),
    ('adm', 'afi ipv6 safi unicast advisory x y z', 'operational ADM afi ipv6 safi unicast "782079207a"', None),
    ('adm', 'afi ipv6 safi unicast advisory "x y"', 'operational ADM afi ipv6 safi unicast "782079"', None),
    # router-id is given where it is wanted, as an optional value
    (
        'rpcq',
        'afi ipv4 safi unicast router-id 1.2.3.4 sequence 5',
        'operational RPCQ afi ipv4 safi unicast router-id 1.2.3.4 sequence 5',
        5,
    ),
    ('rpcq', 'afi ipv4 safi unicast sequence 5', 'operational RPCQ afi ipv4 safi unicast', 5),
    ('rpcp', 'afi ipv4 safi unicast sequence 5 counter 9', 'operational RPCP afi ipv4 safi unicast counter 9', 5),
    # 0 is no sequence
    ('rpcq', 'AFI ipv4 SAFI unicast sequence 0', 'operational RPCQ afi ipv4 safi unicast', None),
]

REFUSED = [
    ('apcq', 'afi ipv4 safi unicast'),
    ('lpcp', 'afi ipv4 safi unicast sequence 1 counter 99999999999'),
    ('rpcq', 'afi ipv4 safi unicast sequence 5 trailing words'),
]


@pytest.mark.parametrize('kind,command,text,sequence', READ)
def test_a_message_is_read(kind: str, command: str, text: str, sequence: int | None) -> None:
    message = read_operational(kind, command.split(' '))
    assert message.extensive() == text
    assert getattr(message, 'sequence', None) == sequence


@pytest.mark.parametrize('kind,command', REFUSED)
def test_a_message_is_refused(kind: str, command: str) -> None:
    with pytest.raises(ValueError):
        read_operational(kind, command.split(' '))


def test_a_kind_which_is_no_message_is_none() -> None:
    assert read_operational('nothing', ['afi', 'ipv4']) is None
