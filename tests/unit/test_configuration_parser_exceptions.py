"""Unit tests for configuration parser exception handling."""

from __future__ import annotations

import os

import pytest

from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.configuration.configuration import Configuration
from exabgp.rib.route import Route
from exabgp.util import program as program_module


NEIGHBOR = """\
neighbor 127.0.0.1 {
    router-id 1.2.3.4;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65001;
    %s
}
"""


def neighbor_error(statement: str) -> str:
    """The error reading a neighbor with one more statement, which must be refused."""
    configuration = Configuration([NEIGHBOR % statement], text=True)
    assert not configuration.reload(), f'{statement!r} was accepted'
    return str(configuration.error)


def command_error(section: str, command: str) -> str:
    """The error reading an API route command, which must be refused."""
    configuration = Configuration([])
    assert not configuration.partial(section, command), f'{command!r} was accepted'
    return str(configuration.error)


def command_route(section: str, command: str) -> Route:
    """The one route an API route command reads."""
    configuration = Configuration([])
    assert configuration.partial(section, command), str(configuration.error)
    (route,) = configuration.pop_routes()
    return route


def rd_error(rd: str) -> str:
    return command_error('static', f'route 10.0.0.0/24 next-hop 1.2.3.4 rd {rd} label 100')


def rd_route(rd: str) -> Route:
    return command_route('static', f'route 10.0.0.0/24 next-hop 1.2.3.4 rd {rd} label 100')


class TestNeighborParserExceptions:
    """A neighbor value which does not parse is a configuration error, not a traceback."""

    def test_local_address_raises_value_error_for_invalid_ip(self):
        """An invalid local-address is refused, naming the value."""
        assert 'is not a valid IP address' in neighbor_error('local-address not-an-ip;')

    def test_router_id_raises_value_error_for_invalid_id(self):
        """An invalid router-id is refused, naming the value."""
        assert 'is not a valid router-id' in neighbor_error('router-id invalid;')

    def test_hold_time_raises_value_error_for_invalid_time(self):
        """An invalid hold-time is refused, naming the value."""
        assert 'is not a valid hold-time' in neighbor_error('hold-time not-a-number;')


class TestFlowParserExceptions:
    """Test flow/parser.py exception handling patterns."""

    def test_redirect_ipv6_without_brackets_raises_os_error(self):
        """Test that IP.from_string() raises OSError for invalid IP addresses.

        The flow/parser.py redirect function catches this and converts to ValueError
        with a helpful message about IPv6 bracket notation.
        """
        from exabgp.protocol.ip import IP

        # IP.create raises OSError for invalid IPs (inet_pton failure)
        with pytest.raises(OSError):
            IP.from_string('2001:db8::1:invalid')


class TestAFISAFIParsingExceptions:
    """Test AFI/SAFI parsing exception handling.

    Note: AFI.from_string() and SAFI.from_string() do NOT raise exceptions
    for invalid input - they return default values ('undefined', 'unknown safi 0').
    The except Exception blocks in peer.py are defensive but currently ineffective.
    """

    def test_afi_from_string_returns_undefined_for_invalid(self):
        """Test that AFI.from_string() returns undefined for invalid AFI (no exception)."""
        from exabgp.protocol.family import AFI

        result = AFI.from_string('invalid-afi')
        # Returns AFI.undefined instead of raising
        assert str(result) == 'undefined'

    def test_safi_from_string_returns_undefined_for_invalid(self):
        """Test that SAFI.from_string() returns undefined for invalid SAFI (no exception)."""
        from exabgp.protocol.family import SAFI

        result = SAFI.from_string('invalid-safi')
        # Returns SAFI.undefined instead of raising
        assert str(result) == 'undefined'


class TestStaticPrefixParserExceptions:
    """Test the static route prefix exception handling.

    prefix() built an IPRange straight from IP.pton(ip), which calls
    socket.inet_pton and raises a bare OSError on malformed input such as
    999.999.999.999 - nothing caught it, so it reached the operator as a
    raw traceback instead of a configuration ValueError.
    """

    def test_an_unparseable_prefix_address_is_a_configuration_error(self) -> None:
        assert '999.999.999.999' in command_error('static', 'route 999.999.999.999/24 next-hop 1.2.3.4')

    def test_a_prefix_with_a_non_numeric_afi_marker_is_a_configuration_error(self) -> None:
        """IP.toafi() also runs before pton() and can itself raise ValueError."""
        assert 'not-an-ip' in command_error('static', 'route not-an-ip next-hop 1.2.3.4')


class TestMplsRouteDistinguisherExceptions:
    """Test the route-distinguisher exception handling.

    route_distinguisher() only assigned prefix/suffix when the token
    contained a ':' at index > 0; 'rd 12345' (no colon) left both
    unassigned, so the next line ('.' in prefix) raised UnboundLocalError
    instead of a configuration ValueError.
    """

    def test_route_distinguisher_without_a_colon_is_a_configuration_error(self) -> None:
        assert '12345' in rd_error('12345')

    def test_route_distinguisher_with_a_leading_colon_is_a_configuration_error(self) -> None:
        """separator == 0 also skipped the assignment ('find' returns 0, not > 0)."""
        assert ':100' in rd_error(':100')

    def test_mvpn_sharedjoin_propagates_the_route_distinguisher_fix(self) -> None:
        """mvpn_sharedjoin (and mvpn_sourcejoin/sourcead, srv6_mup_*) share
        route_distinguisher() with no wrapping of their own - confirm the fix
        in the shared function actually reaches this caller rather than assuming it.
        """
        command = 'mcast-vpn shared-join rp 1.2.3.4 group 5.6.7.8 rd 12345 source-as 100 next-hop 1.2.3.4'
        assert '12345' in command_error('ipv4', command)

    def test_srv6_mup_isd_propagates_the_route_distinguisher_fix(self) -> None:
        assert '12345' in command_error('ipv4', 'mup mup-isd 10.0.0.0/24 rd 12345 next-hop 2001::1')

    def test_route_distinguisher_with_a_non_numeric_asn_prefix_is_a_configuration_error(self) -> None:
        """int(prefix) on a non-numeric ASN raised a bare, unlabelled ValueError
        naming only the fragment 'abc' rather than the full RD token.
        """
        assert 'abc:100' in rd_error('abc:100')

    def test_route_distinguisher_with_an_out_of_range_ipv4_octet_is_a_configuration_error(self) -> None:
        """bytes([int(_)]) on an out-of-range octet (400) raised a bare
        'bytes must be in range(0, 256)' with no token at all.
        """
        assert '1.2.3.400:100' in rd_error('1.2.3.400:100')

    def test_route_distinguisher_with_a_non_numeric_ipv4_octet_is_a_configuration_error(self) -> None:
        assert '1.2.3.abc:100' in rd_error('1.2.3.abc:100')

    @pytest.mark.parametrize('token', ['1.2.3:100', '1.2.3.4.5:100', '1.2:100'])
    def test_route_distinguisher_rejects_a_wrong_ipv4_octet_count(self, token: str) -> None:
        """A type 1 route-distinguisher is two octets of type, four of IPv4 administrator
        and two of suffix. Nothing counted the octets, so a short address packed a seven
        byte value and a long one nine bytes, and both reach the wire as a
        route-distinguisher no receiver can read.
        """
        assert token in rd_error(token)

    def test_route_distinguisher_ipv4_form_packs_exactly_eight_bytes(self) -> None:
        """Negative-space check: the accepted form is the one which is eight bytes."""
        route = rd_route('192.0.2.1:100')

        assert route.nlri.rd.pack_rd() == bytes([0, 1, 192, 0, 2, 1, 0, 100])

    @pytest.mark.parametrize('token', ['-1:1', '1:-1', '192.0.2.1:-1'])
    def test_route_distinguisher_rejects_negative_fields(self, token: str) -> None:
        assert token in rd_error(token)

    def test_route_distinguisher_accepts_a_legitimate_two_byte_asn_form(self) -> None:
        """Negative-space check: a well-formed Type 0 ASN:nn RD must still parse."""
        rd = rd_route('65000:100').nlri.rd
        assert isinstance(rd, RouteDistinguisher)
        assert len(rd.rd) == RouteDistinguisher.LENGTH

    def test_route_distinguisher_accepts_a_legitimate_ipv4_form(self) -> None:
        """Negative-space check: a well-formed Type 1 IP:nn RD must still parse."""
        rd = rd_route('192.0.2.1:100').nlri.rd
        assert isinstance(rd, RouteDistinguisher)
        assert len(rd.rd) == RouteDistinguisher.LENGTH

    def test_route_distinguisher_accepts_a_legitimate_four_byte_asn_form(self) -> None:
        """Negative-space check: a well-formed Type 2 4-byte-ASN:nn RD must still parse."""
        rd = rd_route('4200000000:100').nlri.rd
        assert isinstance(rd, RouteDistinguisher)
        assert len(rd.rd) == RouteDistinguisher.LENGTH


class TestMplsPrefixSidExceptions:
    """Test the bgp-prefix-sid exception handling.

    prefix_sid() only assigned label_sid inside the 'if value == "[":'
    branch; 'bgp-prefix-sid 300' (no leading '[') left label_sid unassigned,
    and int(label_sid) - outside the try/except - raised UnboundLocalError
    instead of a configuration ValueError.
    """

    def test_prefix_sid_without_an_opening_bracket_is_a_configuration_error(self) -> None:
        error = command_error('static', 'route 10.0.0.0/24 next-hop 1.2.3.4 label 100 bgp-prefix-sid 300')
        assert 'bgp-prefix-sid' in error


class TestEnvironmentSetupExceptions:
    """Test environment/config.py Environment.setup() exception handling.

    The integer/real/umask readers in environment/parsing.py raise
    ValueError (int()/float() on bad text), but Environment.setup() only
    caught TypeError around opt.parse(conf), so exabgp_tcp_attempts=abc
    reached the operator as a raw ValueError traceback with no mention of
    which setting was wrong.
    """

    def test_setup_wraps_a_bad_integer_value_in_a_contextful_value_error(self, monkeypatch) -> None:
        from exabgp.environment.config import Environment

        monkeypatch.setenv('exabgp_tcp_attempts', 'abc')

        saved_instance = Environment._instance
        saved_setup_done = Environment._setup_done
        Environment._instance = None
        Environment._setup_done = False
        try:
            with pytest.raises(ValueError, match='tcp.attempts'):
                Environment.setup()
        finally:
            Environment._instance = saved_instance
            Environment._setup_done = saved_setup_done


class TestProcessParserRunExceptions:
    """Test the process run exception handling.

    run() indexed prg[0] to check for a leading '/' with no emptiness
    check first; a bare 'run;' with no program argument left prg == '',
    and prg[0] raised IndexError ('string index out of range') instead of
    a configuration ValueError.
    """

    def test_run_without_a_program_argument_is_a_configuration_error(self) -> None:
        configuration = Configuration(['process helper {\n    run;\n}\n'], text=True)

        assert not configuration.reload()
        assert 'requires a program path' in str(configuration.error)


class TestExecutableDescriptorValidation:
    @pytest.mark.parametrize('parent_is_file', [False, True])
    def test_open_failure_preserves_the_program_error(self, tmp_path, parent_is_file) -> None:
        parent = tmp_path / 'parent'
        if parent_is_file:
            parent.touch()
        program = parent / 'program'

        with pytest.raises(ValueError) as failure:
            program_module.validate_executable(str(program))

        assert str(program) in str(failure.value)

    def test_checks_the_opened_object_when_the_path_changes(self, monkeypatch, tmp_path) -> None:
        program = tmp_path / 'program'
        program.write_text('#!/bin/sh\n')
        program.chmod(0o700)
        real_open = os.open
        opened: list[int] = []

        def open_then_replace(path: str, flags: int) -> int:
            fd = real_open(path, flags)
            opened.append(fd)
            program.unlink()
            program.mkdir()
            return fd

        monkeypatch.setattr(program_module.os, 'open', open_then_replace)

        program_module.validate_executable(str(program))

        with pytest.raises(OSError):
            os.fstat(opened[0])

    def test_closes_the_descriptor_when_validation_fails(self, monkeypatch, tmp_path) -> None:
        program = tmp_path / 'program'
        program.write_text('#!/bin/sh\n')
        program.chmod(0o600)
        real_open = os.open
        opened: list[int] = []

        def record_open(path: str, flags: int) -> int:
            fd = real_open(path, flags)
            opened.append(fd)
            return fd

        monkeypatch.setattr(program_module.os, 'open', record_open)

        with pytest.raises(ValueError, match='will not be able to run'):
            program_module.validate_executable(str(program))

        with pytest.raises(OSError):
            os.fstat(opened[0])

    def test_a_program_which_cannot_run_is_a_configuration_error(self, tmp_path) -> None:
        """The check is made when a configuration is read, and names the program."""
        program = tmp_path / 'program'
        program.write_text('#!/bin/sh\n')
        program.chmod(0o600)
        configuration = Configuration([f'process helper {{\n    run {program};\n}}\n'], text=True)

        assert not configuration.reload()
        assert 'will not be able to run' in str(configuration.error)


class TestResolveRelativeProgramPrecedence:
    """Test util/program.py resolve_program() candidate ordering.

    `options` is built most-specific-first: [/etc/exabgp/<prg>, the config
    file's own directory/<prg>, then each $PATH entry in order]. The loop
    returns on the FIRST existing candidate, so a more specific location
    always wins over a less specific later one. Before the run()/mpls.py
    extraction in the prior fix round, the equivalent inline loop had no
    return/break and kept overwriting `prg` on every match, so the LAST
    existing candidate won instead - inverting the list's intended
    most-specific-first ordering. These tests pin the current (first-match)
    behaviour explicitly so it cannot silently regress back to last-match.
    """

    def test_prefers_etc_exabgp_over_a_path_entry(self, monkeypatch, tmp_path) -> None:
        prg_name = 'myscript'
        etc_candidate = os.path.abspath(os.path.join('/etc/exabgp', prg_name))

        # A same-named "executable" also sits on $PATH - it must still lose
        # to /etc/exabgp, the more specific candidate.
        path_dir = tmp_path / 'pathdir'
        path_dir.mkdir()
        (path_dir / prg_name).write_text('#!/bin/sh\n')
        monkeypatch.setenv('PATH', str(path_dir))

        configuration_file = str(tmp_path / 'unrelated.conf')  # its directory has no match

        # Simulate /etc/exabgp/<prg> existing without writing to the real
        # /etc/exabgp: this machine has none, and even where one exists a
        # test must not depend on, or mutate, real system state.
        real_exists = os.path.exists

        def fake_exists(path: str) -> bool:
            if path == etc_candidate:
                return True
            return real_exists(path)

        monkeypatch.setattr('exabgp.util.program.os.path.exists', fake_exists)

        assert program_module.resolve_program(prg_name, configuration_file) == etc_candidate

    def test_prefers_an_earlier_path_entry_over_a_later_one(self, monkeypatch, tmp_path) -> None:
        prg_name = 'myscript'
        etc_candidate = os.path.abspath(os.path.join('/etc/exabgp', prg_name))
        assert not os.path.exists(etc_candidate), 'test assumes no real /etc/exabgp on this machine'

        first_dir = tmp_path / 'first'
        second_dir = tmp_path / 'second'
        first_dir.mkdir()
        second_dir.mkdir()
        (first_dir / prg_name).write_text('#!/bin/sh\n')
        (second_dir / prg_name).write_text('#!/bin/sh\n')
        monkeypatch.setenv('PATH', f'{first_dir}:{second_dir}')

        configuration_file = str(tmp_path / 'unrelated.conf')  # its directory has no match

        result = program_module.resolve_program(prg_name, configuration_file)
        assert result == str(first_dir / prg_name)

    def test_single_candidate_resolves_the_same_regardless_of_match_order(self, monkeypatch, tmp_path) -> None:
        """Control case: only one candidate exists, so first-match and
        last-match agree - proves the two tests above are genuinely
        exercising the multi-candidate ordering, not a coincidence.
        """
        prg_name = 'myscript'
        etc_candidate = os.path.abspath(os.path.join('/etc/exabgp', prg_name))
        assert not os.path.exists(etc_candidate), 'test assumes no real /etc/exabgp on this machine'

        config_dir = tmp_path / 'confdir'
        config_dir.mkdir()
        (config_dir / prg_name).write_text('#!/bin/sh\n')
        monkeypatch.setenv('PATH', str(tmp_path / 'no-such-path-dir'))

        result = program_module.resolve_program(prg_name, str(config_dir / 'my.conf'))
        assert result == str(config_dir / prg_name)

    def test_returns_prg_unchanged_when_no_candidate_exists(self, monkeypatch, tmp_path) -> None:
        prg_name = 'no-such-program-anywhere'
        etc_candidate = os.path.abspath(os.path.join('/etc/exabgp', prg_name))
        assert not os.path.exists(etc_candidate), 'test assumes no real /etc/exabgp on this machine'

        monkeypatch.setenv('PATH', str(tmp_path / 'no-such-path-dir'))

        result = program_module.resolve_program(prg_name, str(tmp_path / 'unrelated.conf'))
        assert result == prg_name

    def test_a_configuration_runs_the_program_next_to_it(self, monkeypatch, tmp_path) -> None:
        """A relative `run` in a configuration file is looked up the same way, by the grammar."""
        prg_name = 'myscript'
        etc_candidate = os.path.abspath(os.path.join('/etc/exabgp', prg_name))
        assert not os.path.exists(etc_candidate), 'test assumes no real /etc/exabgp on this machine'

        (tmp_path / prg_name).write_text('#!/bin/sh\n')
        (tmp_path / prg_name).chmod(0o700)
        monkeypatch.setenv('PATH', str(tmp_path / 'no-such-path-dir'))
        configuration_file = tmp_path / 'my.conf'
        configuration_file.write_text(f'process helper {{\n    run {prg_name};\n}}\n')
        configuration = Configuration([str(configuration_file)])

        assert configuration.reload(), str(configuration.error)
        assert configuration.processes['helper']['run'] == [str(tmp_path / prg_name)]
