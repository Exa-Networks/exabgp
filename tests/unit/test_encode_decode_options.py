"""encode -i / decode -i turn add-path on, and encode -a / -z refuse a bad AS number cleanly.

create_minimal_configuration() listed the families as add-path ones but left the ADD-PATH
capability disabled, so neither side negotiated it: encode -i wrote no Path Identifier and
decode -i read the identifier as prefixes. An AS number argparse took as any int reached
ASN() and came out as a traceback asking for a bug report.
"""

from __future__ import annotations

import argparse

import pytest

from exabgp.application import encode
from exabgp.configuration.check import _negotiated
from exabgp.configuration.setup import create_minimal_configuration
from exabgp.protocol.family import AFI, SAFI


def test_add_path_option_negotiates_add_path_both_ways() -> None:
    configuration = create_minimal_configuration(add_path=True)
    neighbor = next(iter(configuration.neighbors.values()))
    negotiated_in, negotiated_out = _negotiated(neighbor)
    assert negotiated_out.addpath.send(AFI.ipv4, SAFI.unicast)
    assert negotiated_in.addpath.receive(AFI.ipv4, SAFI.unicast)


def test_without_add_path_option_nothing_is_negotiated() -> None:
    configuration = create_minimal_configuration(add_path=False)
    neighbor = next(iter(configuration.neighbors.values()))
    _, negotiated_out = _negotiated(neighbor)
    assert not negotiated_out.addpath.send(AFI.ipv4, SAFI.unicast)


def test_encode_with_add_path_writes_the_path_identifier(capsys: pytest.CaptureFixture[str]) -> None:
    arguments = _parser().parse_args(['-i', '-n', 'route 10.0.0.0/24 next-hop 1.2.3.4 path-information 1.2.3.4'])
    encode.cmdline(arguments)
    assert capsys.readouterr().out.strip() == '01020304180A0000'


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    encode.setargs(parser)
    return parser


@pytest.mark.parametrize('flag', ['-a', '-z'])
@pytest.mark.parametrize('value', ['4294967296', '-1', '1e3', '٣'])
def test_an_out_of_range_as_is_an_argument_error(flag: str, value: str) -> None:
    with pytest.raises(SystemExit) as raised:
        _parser().parse_args([flag, value, 'route 10.0.0.0/24 next-hop 1.2.3.4'])
    assert raised.value.code == 2


def test_the_largest_as_is_accepted() -> None:
    arguments = _parser().parse_args(['-a', '4294967295', '-z', '0', 'route 10.0.0.0/24 next-hop 1.2.3.4'])
    assert (arguments.local_as, arguments.peer_as) == (4294967295, 0)
