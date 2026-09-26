"""RT membership (RFC 4684, AFI 1 SAFI 132) can be configured and announced.

Issue #1109. ExaBGP could decode an RTC route but nothing could make one: `ipv4 rtc` was not a
family the configuration accepted, and there was no announce syntax. The syntax is

    announce ipv4 rtc origin-as <asn> route-target <route-target> next-hop <ip|self> [attributes]
    announce ipv4 rtc default next-hop <ip|self> [attributes]

`origin-as` rather than `origin`, because every RTC UPDATE also carries the ORIGIN attribute
(RFC 4760 section 3), and `origin igp` stays what it is on every other route. `default` is the
zero-length prefix RFC 4684 section 4 calls the default route target: send me every VPN route.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.configuration.configuration import Configuration

ROOT = pathlib.Path(__file__).parent.parent.parent

ORIGIN_65001 = '0000FDE9'
TARGET_65001_100 = '0002FDE900000064'
FULL = '60' + ORIGIN_65001 + TARGET_65001_100

NEIGHBOUR = """
neighbor 127.0.0.1 {
  router-id 1.2.3.4;
  local-address 127.0.0.2;
  local-as 65001;
  peer-as 65001;
  family { ipv4 rtc; }
  %s
}
"""


def api(line: str, action: str = 'announce') -> tuple[bool, str, list]:
    """Parse one API line the way reactor/api/__init__.py does for `announce ipv4 ...`."""
    configuration = Configuration([''], text=True)
    if not configuration.partial('ipv4', line, action):
        return False, str(configuration.error), []
    configuration.scope.to_context()
    return True, '', configuration.scope.pop_routes()


def wire(route) -> str:
    return bytes(route.nlri.pack_nlri(Negotiated.UNSET)).hex().upper()


def validate(tmp_path, body):
    """The real validator as a subprocess, with logging on: the encoded UPDATE is in the log."""
    conf = tmp_path / 'test.conf'
    conf.write_text(NEIGHBOUR % body)
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    environ.pop('exabgp_log_enable', None)
    return subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'configuration', 'validate', '-nrv', str(conf)],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )


# -- the API -------------------------------------------------------------------------------------


def test_a_membership_route_is_announced() -> None:
    ok, error, routes = api('rtc origin-as 65001 route-target 65001:100 next-hop 192.0.2.1')
    assert ok, error
    (route,) = routes
    assert wire(route) == FULL
    assert str(route.nexthop) == '192.0.2.1'
    assert route.nlri.json() == '{ "origin": 65001, "route-target": "target:65001:100" }'


@pytest.mark.parametrize(
    'target,encoded',
    [
        ('65001:100', '0002FDE900000064'),  # two octet AS
        ('192.0.2.1:100', '0102C00002010064'),  # IPv4 address
        ('4200000000:100', '0202FA56EA000064'),  # four octet AS
        ('target:65001:100', '0002FDE900000064'),  # the extended-community spelling
    ],
)
def test_each_route_target_form(target, encoded) -> None:
    ok, error, routes = api(f'rtc origin-as 65001 route-target {target} next-hop 192.0.2.1')
    assert ok, error
    assert wire(routes[0]) == '60' + ORIGIN_65001 + encoded


def test_the_default_route_target_is_the_zero_length_prefix() -> None:
    ok, error, routes = api('rtc default next-hop 192.0.2.1')
    assert ok, error
    assert wire(routes[0]) == '00'


def test_the_origin_attribute_is_still_the_origin_attribute() -> None:
    """`origin-as` is the NLRI, `origin` is the path attribute every RTC UPDATE carries."""
    ok, error, routes = api(
        'rtc origin-as 65001 route-target 65001:100 next-hop 192.0.2.1 origin egp community 65001:1'
    )
    assert ok, error
    attributes = str(routes[0].attributes)
    assert 'origin egp' in attributes
    assert 'community 65001:1' in attributes


def test_a_membership_route_is_withdrawn() -> None:
    ok, error, routes = api('rtc origin-as 65001 route-target 65001:100 next-hop 192.0.2.1', 'withdraw')
    assert ok, error
    assert wire(routes[0]) == FULL


@pytest.mark.parametrize(
    'line,why',
    [
        ('rtc origin-as 65001 next-hop 192.0.2.1', 'route-target'),
        ('rtc route-target 65001:100 next-hop 192.0.2.1', 'origin-as'),
        ('rtc default origin-as 65001 next-hop 192.0.2.1', 'default'),
        ('rtc origin-as 65001 route-target origin:65001:100 next-hop 192.0.2.1', 'route target'),
        ('rtc origin-as 4294967296 route-target 65001:100 next-hop 192.0.2.1', 'ASN'),
    ],
)
def test_a_malformed_membership_route_is_refused(line, why) -> None:
    ok, error, _ = api(line)
    assert not ok
    assert why in error, error


# -- the configuration file ----------------------------------------------------------------------


def test_the_family_and_the_announce_block(tmp_path) -> None:
    """The defect: `ipv4 rtc` was refused, so none of this could be written down."""
    body = """announce {
    ipv4 {
      rtc origin-as 65001 route-target 65001:100 next-hop 192.0.2.1;
      rtc default next-hop 192.0.2.1;
    }
  }"""
    result = validate(tmp_path, body)

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined[-2000:]
    hexes = combined.replace(' ', '')
    # MP_REACH_NLRI for 1/132, next-hop 192.0.2.1, then the NLRI
    assert '000184' + '04C0000201' + '00' + FULL in hexes, combined[-2000:]
    assert '000184' + '04C0000201' + '00' + '00' in hexes, combined[-2000:]
    # RFC 4760 3: an UPDATE whose only NLRI is in MP_REACH_NLRI SHOULD NOT carry NEXT_HOP
    assert '400304C0000201' not in hexes, combined[-2000:]


def test_the_static_section(tmp_path) -> None:
    result = validate(tmp_path, 'static { rtc origin-as 65001 route-target 65001:100 next-hop 192.0.2.1; }')

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined[-2000:]
    assert FULL in combined.replace(' ', ''), combined[-2000:]
