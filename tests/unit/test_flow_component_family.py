"""A flow component of one address family was accepted in a rule of the other.

Follow-up to issue #1188, which refused mixing IPv4 and IPv6 prefixes. The other components
have families too, and some of them mean something different, or nothing, in the other one:

- flow-label is type 13, which exists only for IPv6 (RFC 8956 3.7). In an IPv4 rule it is an
  unknown component type, which RFC 8955 4.2 makes the whole NLRI malformed.
- type 11 is the 6 bit DSCP in IPv4 (RFC 8955) and the 8 bit Traffic Class in IPv6 (RFC 8956
  3.6), so `dscp 46` in an IPv6 rule matched traffic class 46, not DSCP 46, and `traffic-class`
  in an IPv4 rule the reverse.
- IPv6 has no Don't Fragment bit (RFC 8956 3.6), so `fragment dont-fragment` in an IPv6 rule
  asks for a bit the family does not define.

`protocol` and `next-header` are both type 3 and mean the same in both families, and a fragment
component without dont-fragment encodes the same in both, so those are still accepted: refusing
them would break configurations which put the right bytes on the wire.

Checked whichever order the components arrive in, because the family of a rule written in a
match block is only known once a prefix has been read.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from exabgp.bgp.message.update.nlri.flow import (
    Flow,
    Flow4Destination,
    Flow6Destination,
)
from exabgp.bgp.message.update.nlri.settings import FlowSettings
from exabgp.configuration.core.parser import Tokeniser
from exabgp.configuration.flow.parser import dscp, flow_label, fragment, protocol, traffic_class
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPv4

ROOT = pathlib.Path(__file__).parent.parent.parent


def ipv4_destination() -> Flow4Destination:
    return Flow4Destination.make_prefix4(IPv4.pton('10.1.0.0'), 24)


def ipv6_destination() -> Flow6Destination:
    return Flow6Destination.make_prefix6(IP.pton('2001:db8::'), 32, 0)


def component(parser, text: str):
    (parsed,) = list(parser(Tokeniser().replenish(text.split())))
    return parsed


REFUSED = [
    ('flow-label in IPv4', ipv4_destination, flow_label, '2013'),
    ('traffic-class in IPv4', ipv4_destination, traffic_class, '101'),
    ('dscp in IPv6', ipv6_destination, dscp, '46'),
    ('dont-fragment in IPv6', ipv6_destination, fragment, 'dont-fragment'),
]

ACCEPTED = [
    ('protocol in IPv6, type 3 either way', ipv6_destination, protocol, 'tcp'),
    ('fragment without DF in IPv6', ipv6_destination, fragment, 'first-fragment'),
    ('dscp in IPv4', ipv4_destination, dscp, '46'),
    ('flow-label in IPv6', ipv6_destination, flow_label, '2013'),
]


@pytest.mark.parametrize('shape,prefix,parser,text', REFUSED, ids=[row[0] for row in REFUSED])
def test_a_component_of_the_other_family_is_refused_after_the_prefix(shape, prefix, parser, text) -> None:
    flow = Flow.make_flow()
    assert flow.add(prefix())
    other = component(parser, text)
    assert flow.add(other) is False
    assert other.NAME in flow.family_conflict(other)


@pytest.mark.parametrize('shape,prefix,parser,text', REFUSED, ids=[row[0] for row in REFUSED])
def test_a_component_of_the_other_family_is_refused_before_the_prefix(shape, prefix, parser, text) -> None:
    """In a match block the component may come first: the prefix is then the one refused."""
    flow = Flow.make_flow()
    assert flow.add(component(parser, text))
    assert flow.add(prefix()) is False


@pytest.mark.parametrize('shape,prefix,parser,text', ACCEPTED, ids=[row[0] for row in ACCEPTED])
def test_a_component_valid_on_the_wire_is_accepted(shape, prefix, parser, text) -> None:
    flow = Flow.make_flow()
    assert flow.add(prefix())
    assert flow.add(component(parser, text)), shape


def test_two_components_of_different_families_are_refused_without_a_prefix() -> None:
    flow = Flow.make_flow()
    assert flow.add(component(dscp, '46'))
    assert flow.add(component(flow_label, '2013')) is False


def test_an_ipv6_only_component_makes_the_rule_ipv6() -> None:
    """Without a prefix, a flow-label rule used to be packed as an IPv4 flow route."""
    flow = Flow.make_flow()
    assert flow.add(component(flow_label, '2013'))
    assert flow.afi == AFI.ipv6


def test_the_announced_family_is_checked_too() -> None:
    settings = FlowSettings(afi=AFI.ipv4, safi=SAFI.flow_ip)
    with pytest.raises(ValueError, match='flow-label'):
        settings.add_rule(component(flow_label, '2013'))


def test_the_configuration_refuses_it(tmp_path) -> None:
    conf = tmp_path / 'test.conf'
    conf.write_text(
        """
neighbor 127.0.0.1 {
  router-id 1.2.3.4; local-address 127.0.0.2; local-as 1; peer-as 1;
  family { ipv6 flow; }
  flow { route test { match { destination 2001:db8::/32; dscp 46; } then { discard; } } }
}
"""
    )
    environ = dict(os.environ)
    environ.pop('PYTHONPATH', None)
    result = subprocess.run(
        [str(ROOT / 'sbin' / 'exabgp'), 'configuration', 'validate', str(conf)],
        capture_output=True,
        text=True,
        env=environ,
        cwd=str(ROOT),
        timeout=180,
    )
    combined = result.stdout + result.stderr
    assert result.returncode != 0, combined[-1500:]
    assert 'dscp' in combined and 'line ' in combined, combined[-1500:]
