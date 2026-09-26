"""A flow route mixing IPv4 and IPv6 prefixes was accepted, and came out as a different rule.

Issue #1188. RFC 8955 carries IPv4 flow routes and RFC 8956 IPv6 ones, each under its own AFI, so
the source and destination prefixes of one rule share one address family. ExaBGP had three ways in,
and none of them refused the mix:

- the `match { }` block and `flow route ...` over the API went through Flow.add(), which returned
  False on a mix, and both callers ignored it. `source 10.0.0.0/24; destination 2001:db8::/32;`
  loaded as `source 10.0.0.0/24` alone: the IPv6 destination vanished, and a mitigation rule became
  one matching every destination.
- Flow.add() only compared a source with a destination, so `destination 10.1.0.0/24;
  destination 2001:db8::/32;` went through as one rule holding both.
- `announce ipv4 flow ...` went through FlowSettings.add_rule(), which checked nothing, and built
  `destination-ipv6 2001:db8::/32 source-ipv4 10.0.0.0/24` inside an IPv4 flow NLRI.

Each now refuses the rule, saying which prefix clashes with which.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from exabgp.bgp.message.update.nlri.flow import Flow, Flow4Destination, Flow4Source, Flow6Destination
from exabgp.bgp.message.update.nlri.settings import FlowSettings
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPv4

ROOT = pathlib.Path(__file__).parent.parent.parent

NEIGHBOUR = """
neighbor 127.0.0.1 {
  router-id 1.2.3.4;
  local-address 127.0.0.2;
  local-as 1;
  peer-as 1;
  family { ipv4 flow; ipv6 flow; }
  flow { route test { match { %s } then { discard; } } }
}
"""

MIXED_PAIR = NEIGHBOUR % 'source 10.0.0.0/24; destination 2001:db8::/32;'
MIXED_DESTINATIONS = NEIGHBOUR % 'destination 10.1.0.0/24; destination 2001:db8::/32;'
IPV4_ONLY = NEIGHBOUR % 'source 10.0.0.0/24; destination 10.1.0.0/24;'
IPV6_ONLY = NEIGHBOUR % 'source 2001:db8:1::/48; destination 2001:db8::/32;'


def ipv4_destination() -> Flow4Destination:
    return Flow4Destination.make_prefix4(IPv4.pton('10.1.0.0'), 24)


def ipv4_source() -> Flow4Source:
    return Flow4Source.make_prefix4(IPv4.pton('10.0.0.0'), 24)


def ipv6_destination() -> Flow6Destination:
    return Flow6Destination.make_prefix6(IP.pton('2001:db8::'), 32, 0)


def validate(tmp_path, text):
    """The real validator as a subprocess, which is what an operator runs."""
    conf = tmp_path / 'test.conf'
    conf.write_text(text)
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    return subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'configuration', 'validate', '-nrv', str(conf)],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )


def api(section: str, line: str) -> tuple[bool, str, list[str]]:
    """Parse one API line the way reactor/api/__init__.py does, returning (ok, error, nlri)."""
    configuration = Configuration([''], text=True)
    configuration.flow.clear()
    if not configuration.partial(section, line, 'announce'):
        return False, str(configuration.error), []
    configuration.scope.to_context()
    return True, '', [str(route.nlri) for route in configuration.scope.pop_routes()]


# -- Flow.add, used by the match block and by `flow route` ---------------------------------------


def test_add_refuses_a_second_destination_of_the_other_family() -> None:
    """It used to compare a source with a destination only, so this pair went through."""
    flow = Flow.make_flow()
    assert flow.add(ipv4_destination()) is True
    assert flow.add(ipv6_destination()) is False
    assert len(flow.rules[Flow4Destination.ID]) == 1


def test_the_refusal_names_both_prefixes() -> None:
    flow = Flow.make_flow()
    flow.add(ipv4_source())
    reason = flow.family_conflict(ipv6_destination())
    assert '2001:db8::/32' in reason
    assert '10.0.0.0/24' in reason


def test_add_keeps_prefixes_of_one_family() -> None:
    flow = Flow.make_flow()
    assert flow.add(ipv4_source()) is True
    assert flow.add(ipv4_destination()) is True
    assert flow.family_conflict(ipv4_destination()) == ''


# -- FlowSettings.add_rule, used by `announce ipv4 flow` -----------------------------------------


def test_settings_refuse_a_prefix_of_the_other_family() -> None:
    settings = FlowSettings(afi=AFI.ipv4, safi=SAFI.flow_ip)
    with pytest.raises(ValueError, match='2001:db8::/32'):
        settings.add_rule(ipv6_destination())
    assert settings.rules == {}


def test_settings_keep_a_prefix_of_their_family() -> None:
    settings = FlowSettings(afi=AFI.ipv4, safi=SAFI.flow_ip)
    settings.add_rule(ipv4_source())
    settings.add_rule(ipv4_destination())
    assert len(settings.rules) == 2


# -- the configuration file ----------------------------------------------------------------------


@pytest.mark.parametrize(
    'text,shape', [(MIXED_PAIR, 'source and destination'), (MIXED_DESTINATIONS, 'two destinations')]
)
def test_the_configuration_refuses_the_mix(tmp_path, text, shape) -> None:
    """The defect: this loaded, and announced a rule without the IPv6 prefix."""
    result = validate(tmp_path, text)

    combined = result.stdout + result.stderr
    assert result.returncode != 0, f'mixed {shape} was accepted'
    assert '2001:db8::/32' in combined, combined[-1500:]
    assert 'line ' in combined
    assert 'Traceback' not in combined


@pytest.mark.parametrize('text,shape', [(IPV4_ONLY, 'IPv4'), (IPV6_ONLY, 'IPv6')])
def test_one_family_still_loads(tmp_path, text, shape) -> None:
    """The control: a refusal which refuses everything is not a fix."""
    result = validate(tmp_path, text)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, f'an {shape} only rule stopped loading: {combined[-1500:]}'


# -- the API -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    'section,line',
    [
        ('flow', 'route source 10.0.0.0/24 destination 2001:db8::/32 discard'),
        ('flow', 'route destination 10.1.0.0/24 destination 2001:db8::/32 discard'),
        ('ipv4', 'flow source 10.0.0.0/24 destination 2001:db8::/32 discard'),
        ('ipv4', 'flow destination 2001:db8::/32 discard'),
        ('ipv6', 'flow destination 10.1.0.0/24 discard'),
    ],
)
def test_the_api_refuses_the_mix(section, line) -> None:
    ok, error, nlri = api(section, line)
    assert not ok, f'{line!r} was accepted as {nlri}'
    assert 'family' in error, error


@pytest.mark.parametrize(
    'section,line,expected',
    [
        ('flow', 'route source 10.0.0.0/24 destination 10.1.0.0/24 discard', 'source-ipv4 10.0.0.0/24'),
        ('ipv4', 'flow source 10.0.0.0/24 destination 10.1.0.0/24 discard', 'source-ipv4 10.0.0.0/24'),
        ('ipv6', 'flow destination 2001:db8::/32 discard', 'destination-ipv6 2001:db8::/32'),
    ],
)
def test_the_api_keeps_one_family(section, line, expected) -> None:
    ok, error, nlri = api(section, line)
    assert ok, error
    assert len(nlri) == 1
    assert expected in nlri[0]
