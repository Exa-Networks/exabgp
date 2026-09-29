"""The paths of `exabgp encode`'s cmdline which the existing tests do not reach.

`tests/unit/application/test_encode_app.py` drives cmdline with a route on the command
line, but measured with branch coverage on 2026-09-29 it never ran `--debug` or `--pdb`, a
configuration file (read or refused), a configuration without a neighbor, an `otc self`
route, a route whose family the neighbor does not carry, a neighbor whose RIB is disabled,
or a ValueError raised while a neighbor's routes are encoded.  Nor did it check the bytes
written, only their shape.  These tests pin what cmdline does on each before it is split
into helpers (plan-large-function-decomposition): the exact text on stdout, and the exit
code, whether returned or raised through `sys.exit`.
"""

from __future__ import annotations

import argparse
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from exabgp.application import encode
from exabgp.application.encode import cmdline, setargs
from exabgp.configuration.setup import create_minimal_configuration
from exabgp.environment import getenv

ETC = Path(__file__).resolve().parents[3] / 'etc' / 'exabgp'

MARKER = 'F' * 32
ROUTE = 'route 10.0.0.0/24 next-hop 1.2.3.4'
UPDATE = MARKER + '00300200000015400101004002004003040102030440050400000064180A0000'


def _run(argv: list[str]) -> tuple[int | str | None, str]:
    """Run cmdline on parsed argv, return its exit code and what it wrote on stdout."""
    parser = argparse.ArgumentParser()
    setargs(parser)
    arguments = parser.parse_args(argv)
    with patch('sys.stdout', new_callable=StringIO) as stdout:
        try:
            code: int | str | None = cmdline(arguments)
        except SystemExit as exit:
            code = exit.code
    return code, stdout.getvalue()


@pytest.fixture(autouse=True)
def _restore_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Undo what cmdline writes into the process wide environment."""
    env = getenv()
    monkeypatch.setattr(env.log, 'all', env.log.all)
    monkeypatch.setattr(env.log, 'level', env.log.level)
    monkeypatch.setattr(env.log, 'parser', env.log.parser)
    monkeypatch.setattr(env.debug, 'pdb', env.debug.pdb)
    monkeypatch.setattr(env.bgp, 'passive', env.bgp.passive)
    monkeypatch.setattr(env.tcp, 'bind', env.tcp.bind)


class TestUsage:
    def test_no_route_and_no_configuration_prints_usage(self) -> None:
        code, output = _run([])
        assert code == 1
        assert output.startswith('Environment values are:\n - ')
        assert output.endswith(
            '\n\nUsage: exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4"\n'
            '       exabgp encode -c myconfig.conf\n\n'
            'Examples:\n'
            '  exabgp encode "route 10.0.0.0/24 next-hop 192.168.1.1"\n'
            '  exabgp encode "route 10.0.0.0/24 next-hop 1.2.3.4 origin igp as-path [65000 65001]"\n'
            '  exabgp encode -f "ipv6 unicast" "route 2001:db8::/32 next-hop 2001:db8::1"\n'
            '  exabgp encode -n "route 10.0.0.0/24 next-hop 1.2.3.4"  # NLRI only\n'
        )


class TestEnvironment:
    def test_the_environment_is_set_for_an_offline_encoder(self) -> None:
        env = getenv()
        env.bgp.passive = False
        env.log.parser = False
        env.tcp.bind = ['127.0.0.1']
        assert _run([ROUTE]) == (0, UPDATE + '\n')
        assert env.bgp.passive is True
        assert env.log.parser is True
        assert env.tcp.bind == []

    def test_debug_turns_logging_on_instead_of_silencing_it(self) -> None:
        env = getenv()
        with patch.object(encode, 'log') as log, patch.object(encode, 'trace_interceptor') as trace:
            assert _run(['-d', ROUTE]) == (0, UPDATE + '\n')
        assert env.log.all is True
        assert env.log.level == 'DEBUG'
        log.silence.assert_not_called()
        log.init.assert_called_once_with(env)
        trace.assert_called_once_with(env.debug.pdb)

    def test_without_debug_logging_is_silenced(self) -> None:
        env = getenv()
        with patch.object(encode, 'log') as log, patch.object(encode, 'trace_interceptor'):
            assert _run([ROUTE]) == (0, UPDATE + '\n')
        log.silence.assert_called_once_with()
        assert [call[0] for call in log.method_calls] == ['silence', 'init']
        log.init.assert_called_once_with(env)

    def test_pdb_is_handed_to_the_trace_interceptor(self) -> None:
        env = getenv()
        env.debug.pdb = False
        with patch.object(encode, 'log'), patch.object(encode, 'trace_interceptor') as trace:
            assert _run(['-p', ROUTE]) == (0, UPDATE + '\n')
        assert env.debug.pdb is True
        trace.assert_called_once_with(True)


class TestRouteArgument:
    def test_update_exact_bytes(self) -> None:
        assert _run([ROUTE]) == (0, UPDATE + '\n')

    def test_no_header_drops_the_nineteen_bytes(self) -> None:
        assert _run(['--no-header', ROUTE]) == (0, UPDATE[38:] + '\n')

    def test_nlri_only_wins_over_no_header(self) -> None:
        assert _run(['-n', '--no-header', ROUTE]) == (0, '180A0000\n')

    def test_split_writes_one_line_per_update(self) -> None:
        code, output = _run([ROUTE + ' split /26'])
        assert code == 0
        head = MARKER + '003102000000154001010040020040030401020304400504000000641A0A0000'
        assert output == ''.join(f'{head}{last}\n' for last in ('00', '40', '80', 'C0'))

    def test_ipv6_update_exact_bytes(self) -> None:
        code, output = _run(['-f', 'ipv6 unicast', '-n', 'route 2001:db8::/32 next-hop 2001:db8::1'])
        assert (code, output) == (0, '2020010DB8\n')

    def test_as_numbers_reach_the_as_path(self) -> None:
        code, output = _run(['-a', '65000', '-z', '65001', ROUTE])
        assert (code, output) == (0, MARKER + '002F02000000144001010040020602010000FDE840030401020304180A0000\n')

    def test_only_the_routes_of_a_negotiated_family_are_kept(self) -> None:
        text = f'{ROUTE}; route 2001:db8::/32 next-hop 2001:db8::1'
        assert _run([text]) == (0, UPDATE + '\n')

    def test_a_route_of_another_family_is_refused(self) -> None:
        text = 'route 2001:db8::/32 next-hop 2001:db8::1'
        assert _run([text]) == (1, f'configuration error: Failed to parse route: {text}\n')

    def test_a_route_which_does_not_parse_is_refused(self) -> None:
        assert _run(['invalid']) == (1, 'configuration error: Failed to parse route: invalid\n')

    def test_an_invalid_family_is_refused(self) -> None:
        assert _run(['-f', 'invalid', ROUTE]) == (1, 'configuration error: Invalid family format: invalid\n')

    def test_otc_self_is_refused_without_a_neighbor(self) -> None:
        assert _run([ROUTE + ' otc self']) == (
            1,
            'configuration error: OTC self and role names require a real neighbor: '
            'use encode -c or a literal OTC ASN\n',
        )

    def test_a_literal_otc_is_encoded(self) -> None:
        code, output = _run(['-n', ROUTE + ' otc 65000'])
        assert (code, output) == (0, '180A0000\n')


class TestConfigurationFile:
    def test_configuration_file_is_encoded(self) -> None:
        code, output = _run(['-c', str(ETC / 'conf-ipself4.conf')])
        assert code == 0
        assert output == MARKER + '00310200000015400101004002004003047F0000014005040000006420' + '0A000000\n'

    def test_configuration_file_nlri_only(self) -> None:
        assert _run(['-n', '-c', str(ETC / 'conf-ipself4.conf')]) == (0, '200A000000\n')

    def test_route_is_ignored_when_a_configuration_is_given(self) -> None:
        code, output = _run(['-n', '-c', str(ETC / 'conf-ipself4.conf'), ROUTE])
        assert (code, output) == (0, '200A000000\n')

    def test_every_neighbor_is_encoded_in_order(self) -> None:
        code, output = _run(['--no-header', '-c', str(ETC / 'conf-confederation.conf')])
        assert code == 0
        lines = output.splitlines()
        assert len(lines) == 2
        assert lines[0] == '000000144001010040020602010000FDE94003040A0001FE180A0000'
        assert lines[1].startswith('000000184001010040020A02020000FDE')

    def test_a_configuration_which_does_not_load_is_refused(self, tmp_path: Path) -> None:
        conf = tmp_path / 'bad.conf'
        conf.write_text('neighbor 1.2.3.4 { garbage; }\n')
        code, output = _run(['-c', str(conf)])
        assert code == 1
        assert output.startswith(f'configuration error: {conf}:1:20: unknown keyword ')

    def test_a_configuration_without_neighbor_is_refused(self) -> None:
        code, output = _run(['-c', str(ETC / 'api-no-neighbor.conf')])
        assert (code, output) == (1, 'no neighbor defined in configuration\n')


class TestNeighborLoop:
    def test_a_disabled_rib_writes_nothing(self) -> None:
        def disabled(**kwargs: Any) -> Any:
            configuration = create_minimal_configuration(**kwargs)
            for neighbor in configuration.neighbors.values():
                neighbor.rib.enabled = False
            return configuration

        with patch.object(encode, 'create_minimal_configuration', disabled):
            assert _run([ROUTE]) == (0, '')

    def test_a_value_error_while_encoding_is_reported(self) -> None:
        def refuse(_neighbor: object) -> object:
            raise ValueError('cannot negotiate')

        with patch.object(encode, '_negotiated', refuse):
            assert _run([ROUTE]) == (1, 'configuration error: cannot negotiate\n')

    def test_a_value_error_after_output_keeps_what_was_written(self) -> None:
        calls: list[int] = []
        real = encode.UpdateCollection

        def failing(*args: Any) -> Any:
            calls.append(1)
            if len(calls) > 1:
                raise ValueError('second route')
            return real(*args)

        with patch.object(encode, 'UpdateCollection', failing):
            code, output = _run([ROUTE + ' split /25'])
        assert code == 1
        head = MARKER + '00310200000015400101004002004003040102030440050400000064190A0000'
        assert output == f'{head}00\nconfiguration error: second route\n'
