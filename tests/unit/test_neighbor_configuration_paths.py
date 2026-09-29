"""The paths of NeighborTemplate.configuration which no other unit test reaches.

configuration() renders a neighbor as configuration text: `exabgp configuration validate`
logs it for every neighbor, and str(neighbor) is the same text without the routes.  Measured
with branch coverage on 2026-09-29, the unit tests which print a neighbor never render its
routes, a prefix-limit, a nexthop or add-path block, an api block, or a capability which is
required, so none of those loops or tests ran.  These tests pin what the method prints today,
byte for byte, before it is split into helpers (plan-large-function-decomposition).

What is pinned is the text as it is, including what looks untidy: a blank line before
`passive`, `listen` and `connect`, a `static {` with a trailing space, closed with the
neighbor on one `}}`, routes printed without the `route` keyword.  It is a display, not a
configuration which reads back (tests/unit/configuration/test_serialise.py says so), and a
split must not change a byte of it.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.neighbor.neighbor import NeighborTemplate
from exabgp.configuration.configuration import Configuration
from exabgp.rib import RIB

PROCESSES = 'process watcher { run /usr/bin/true; encoder json; } process logger { run /usr/bin/true; encoder text; }'

EVERY_STATEMENT = """
    description "every statement";
    local-address 192.0.2.2;
    rate-limit 10;
    listen 1790;
    connect 1791;
    route-target-filter true;
    md5-password "secret";
    outgoing-ttl 5;
    incoming-ttl 6;
    role { local provider; strict enable; }
    capability {
        asn4 require; route-refresh enable; graceful-restart 120; add-path send/receive;
        nexthop require; software-version require; operational require; aigp enable;
        extended-message require; link-local-nexthop require; multiple-labels 3;
    }
    family { ipv4 unicast prefix-limit 1; ipv6 unicast; }
    nexthop { ipv4 unicast ipv6; }
    add-path { ipv4 unicast limit 4; ipv6 unicast; }
    api {
        processes [ watcher ]; neighbor-changes; negotiated; fsm; signal;
        receive { packets; parsed; consolidate; notification; open; keepalive; update; refresh; operational; }
        send { packets; parsed; consolidate; notification; open; keepalive; update; refresh; operational; }
    }
    static { route 10.0.0.0/24 next-hop 192.0.2.2; route 10.0.1.0/24 next-hop 192.0.2.3; }
"""

EVERY_STATEMENT_RENDERED = """\
neighbor 192.0.2.1 {
  description "every statement";
  router-id 192.0.2.2;
  host-name ;
  domain-name ;
  local-address 192.0.2.2;
  source-interface ;
  local-as 65001;
  peer-as 65002;
  hold-time 180;
  rate-limit 10;
  manual-eor false;
  shutdown false;

  passive false;

  listen 1790;

  connect 1791;
  group-updates true;
  as-set withdraw;
  tunnel-encapsulation auto;
  route-target-filter true;
  enforce-first-as true;
  flow-validation disable;
  auto-flush true;
  adj-rib-in true;
  adj-rib-out true;
  md5-password "secret";
  md5-base64 false;
  md5-ip "192.0.2.2";
  outgoing-ttl 5;
  incoming-ttl 6;
  role {
    local provider;
    strict enable;
    add-meta enable;
  }
  capability {
    asn4 require;
    route-refresh enable;
    graceful-restart 120;
    software-version require;
    nexthop require;
    add-path send/receive;
    multi-session disable;
    operational require;
    aigp enable;
    extended-message require;
    link-local-nexthop require;
    multiple-labels 3;
  }
  family {
    ipv4 unicast prefix-limit 1;
    ipv6 unicast;
  }
  nexthop {
    ipv4 unicast ipv6;
  }
  add-path {
    ipv4 unicast limit 4;
    ipv6 unicast;
  }
  api {
    processes [ watcher ];
    neighbor-changes;
    negotiated;
    fsm;
    signal;
    receive {
      packets;
      parsed;
      consolidate;
      notification;
      open;
      keepalive;
      update;
      refresh;
      operational;
    }
    send {
      packets;
      parsed;
      consolidate;
      notification;
      open;
      keepalive;
      update;
      refresh;
      operational;
    }
  }
"""

EVERY_STATEMENT_ROUTES = '\nstatic { \n    10.0.0.0/24 next-hop 192.0.2.2\n    10.0.1.0/24 next-hop 192.0.2.3\n}}'

FLAGS_TURNED_OVER = """
    local-address 192.0.2.2;
    family { ipv4 unicast; }
    passive true; manual-eor true; shutdown true; group-updates false; auto-flush false;
    adj-rib-in false; adj-rib-out false; enforce-first-as false;
    md5-password "c2VjcmV0"; md5-base64 true;
    capability { asn4 disable; nexthop enable; software-version enable; operational enable; graceful-restart; }
    confederation { identifier 65000; members [ 65002 65003 ]; }
"""

FLAGS_TURNED_OVER_RENDERED = """\
neighbor 192.0.2.1 {
  description "";
  router-id 192.0.2.2;
  host-name ;
  domain-name ;
  local-address 192.0.2.2;
  source-interface ;
  local-as 65001;
  peer-as 65002;
  hold-time 180;
  rate-limit disable;
  manual-eor true;
  shutdown true;

  passive true;
  group-updates false;
  as-set withdraw;
  tunnel-encapsulation auto;
  route-target-filter false;
  enforce-first-as false;
  flow-validation disable;
  auto-flush false;
  adj-rib-in false;
  adj-rib-out false;
  md5-password "c2VjcmV0";
  md5-base64 true;
  md5-ip "192.0.2.2";
  confederation {
    identifier 65000;
    members [ 65002 65003 ];
  }
  capability {
    asn4 disable;
    route-refresh disable;
    graceful-restart 180;
    software-version enable;
    nexthop enable;
    add-path disable;
    multi-session disable;
    operational enable;
    aigp disable;
  }
  family {
    ipv4 unicast;
  }
  nexthop {
  }
  add-path {
  }
}"""

# The capability block of a neighbor which says nothing about its capabilities.
DEFAULT_CAPABILITIES = """\
  capability {
    asn4 enable;
    route-refresh disable;
    graceful-restart disable;
    software-version disable;
    nexthop disable;
    add-path disable;
    multi-session disable;
    operational disable;
    aigp disable;
  }
"""


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def parsed(body: str) -> Neighbor:
    text = f'{PROCESSES} neighbor 192.0.2.1 {{ router-id 192.0.2.2; local-as 65001; peer-as 65002; {body} }}'
    configuration = Configuration([text], text=True)
    assert configuration.reload(), str(configuration.error)
    assert len(configuration.neighbors) == 1
    neighbor: Neighbor = next(iter(configuration.neighbors.values()))
    return neighbor


def test_every_statement_renders_with_its_routes() -> None:
    # Configuration.reload() queues the static routes in the outgoing RIB, which is what is listed.
    assert NeighborTemplate.configuration(parsed(EVERY_STATEMENT)) == EVERY_STATEMENT_RENDERED + EVERY_STATEMENT_ROUTES


def test_without_routes_the_neighbor_closes_after_its_api_blocks() -> None:
    assert NeighborTemplate.configuration(parsed(EVERY_STATEMENT), False) == EVERY_STATEMENT_RENDERED + '}'


def test_str_is_the_configuration_without_routes() -> None:
    neighbor = parsed(EVERY_STATEMENT)
    assert str(neighbor) == NeighborTemplate.configuration(neighbor, False)


def test_a_neighbor_with_no_route_still_has_a_static_block() -> None:
    rendered = NeighborTemplate.configuration(parsed('local-address 192.0.2.2; family { ipv4 unicast; }'))
    assert rendered.endswith('  add-path {\n  }\n\nstatic { \n}}')


def test_routes_are_not_listed_while_the_rib_is_disabled() -> None:
    neighbor = parsed(EVERY_STATEMENT)
    neighbor.rib.outgoing.enabled = False
    assert NeighborTemplate.configuration(neighbor) == EVERY_STATEMENT_RENDERED + '\nstatic { \n}}'


def test_flags_turned_over_render_their_other_word() -> None:
    assert NeighborTemplate.configuration(parsed(FLAGS_TURNED_OVER), False) == FLAGS_TURNED_OVER_RENDERED


def test_a_neighbor_with_defaults_leaves_out_the_optional_lines() -> None:
    rendered = NeighborTemplate.configuration(parsed('local-address 192.0.2.2; family { ipv4 unicast; }'), False)
    assert '  rate-limit disable;\n' in rendered
    assert '  md5-base64 false;\n  md5-ip "192.0.2.2";\n' + DEFAULT_CAPABILITIES in rendered
    for absent in ('listen', 'connect', 'md5-password', 'outgoing-ttl', 'incoming-ttl', 'role', 'api', 'static'):
        assert f'  {absent} ' not in rendered
    assert rendered.endswith('  family {\n    ipv4 unicast;\n  }\n  nexthop {\n  }\n  add-path {\n  }\n}')


def test_local_address_auto_has_no_md5_ip() -> None:
    rendered = NeighborTemplate.configuration(parsed('local-address auto; family { ipv4 unicast; }'), False)
    assert '  local-address auto;\n' in rendered
    assert '  md5-base64 false;\n' + DEFAULT_CAPABILITIES in rendered
    assert 'md5-ip' not in rendered


def test_multi_session_enabled_is_said() -> None:
    rendered = NeighborTemplate.configuration(
        parsed('local-address 192.0.2.2; capability { multi-session enable; } family { ipv4 unicast; }'), False
    )
    assert '    multi-session enable;\n' in rendered


def test_each_process_has_an_api_block_with_only_its_own_flags() -> None:
    body = (
        'local-address 192.0.2.2; family { ipv4 unicast; } '
        'api { processes [ watcher ]; neighbor-changes; } api { processes [ logger ]; receive { update; } }'
    )
    rendered = NeighborTemplate.configuration(parsed(body), False)
    assert rendered.endswith(
        '  add-path {\n  }\n'
        '  api {\n    processes [ watcher ];\n    neighbor-changes;\n  }\n'
        '  api {\n    processes [ logger ];\n    receive {\n      update;\n    }\n  }\n'
        '}'
    )


def test_processes_sharing_an_api_block_are_rendered_one_block_each() -> None:
    body = 'local-address 192.0.2.2; family { ipv4 unicast; } api { processes [ watcher logger ]; send { packets; } }'
    rendered = NeighborTemplate.configuration(parsed(body), False)
    assert rendered.endswith(
        '  add-path {\n  }\n'
        '  api {\n    processes [ watcher ];\n    send {\n      packets;\n    }\n  }\n'
        '  api {\n    processes [ logger ];\n    send {\n      packets;\n    }\n  }\n'
        '}'
    )


def test_a_neighbor_with_an_empty_api_dictionary_has_no_api_block() -> None:
    neighbor = parsed(EVERY_STATEMENT)
    neighbor.api = {}
    rendered = NeighborTemplate.configuration(neighbor, False)
    assert 'api {' not in rendered
    assert rendered.endswith('  add-path {\n    ipv4 unicast limit 4;\n    ipv6 unicast;\n  }\n}')
