"""An API operational command reads its message as the legacy parser did.

The words are the command split on spaces: a quote stays in the advisory, and a quoted
text with a space is two words, of which the advisory is the first. The expectations were
taken from the legacy parser (configuration/operational/parser.py) before it was removed.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.read import read_operational

READ = [
    ('asm', 'afi ipv4 safi unicast advisory "hello"', 'operational ASM afi ipv4 safi unicast "2268656c6c6f22"', None),
    ('adm', 'afi ipv6 safi unicast advisory x y z', 'operational ADM afi ipv6 safi unicast "78"', None),
    ('rpcq', 'afi ipv4 safi unicast sequence 5', 'operational RPCQ afi ipv4 safi unicast', 5),
    ('rpcp', 'afi ipv4 safi unicast sequence 5 counter 9', 'operational RPCP afi ipv4 safi unicast counter 9', 5),
    # 0 is no sequence
    ('rpcq', 'AFI ipv4 SAFI unicast sequence 0', 'operational RPCQ afi ipv4 safi unicast', None),
]

REFUSED = [
    ('apcq', 'afi ipv4 safi unicast'),
    ('lpcp', 'afi ipv4 safi unicast sequence 1 counter 99999999999'),
    ('rpcq', 'afi ipv4 safi unicast router-id 1.2.3.4 sequence 5'),
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
