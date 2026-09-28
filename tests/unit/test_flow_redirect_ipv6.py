"""The IPv6 route-target redirect of a flow route could not be configured, and was mis-encoded.

Issue #927. RFC 8956 6.1 defines rt-redirect-ipv6, an IPv6-Address-Specific Extended Community
(attribute 25, twenty octets) "with the Type value always 0x000d". Four things were wrong:

- `redirect [2001:db8::1]:100;` was a syntax error. The tokeniser splits the line at the brackets,
  so redirect() read `[` as the whole target and never saw the address. The grammar's lexer
  splits it the same way, and REDIRECT reads the pieces back together.
- TrafficRedirectIPv6 wrote type 0x0002, the plain IPv6 route-target of RFC 5701, and registered
  0x800b, a pre-RFC draft value, for decoding: it could not read back what it wrote.
- the parser put the twenty octet community in ExtendedCommunities, attribute 16, where every
  community is eight octets.
- the route-target was also installed as the next-hop of the route, which a redirect to a VRF has
  none of, and the text form `redirect 2001:db8::1:100` cannot tell the number from the address.
"""

from __future__ import annotations

import os
import pathlib
import subprocess

import pytest

from exabgp.bgp.message.update.attribute.community.extended import (
    ExtendedCommunitiesIPv6,
    TrafficRedirectIPv6,
)
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunityIPv6
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.grammar.lexer import lex_text
from exabgp.configuration.grammar.types.flow import REDIRECT, REDIRECT_SIMPSON
from exabgp.configuration.grammar.words import Words
from exabgp.protocol.ip import IP

ROOT = pathlib.Path(__file__).parent.parent.parent

# attribute 25, optional transitive, 20 octets: type 0x00 0x0d, 2001:db8::1, local administrator 100
WIRE = 'C01914' + '000D' + '20010DB8000000000000000000000001' + '0064'

NEIGHBOUR = """
neighbor 127.0.0.1 {
  router-id 1.2.3.4;
  local-address 127.0.0.2;
  local-as 1;
  peer-as 1;
  family { ipv6 flow; }
  flow { route test { match { destination 2001:db8:1::/48; } then { %s } } }
}
"""


def tokens(*content: str) -> Words:
    statement = lex_text(' '.join(['redirect', *content, ';']))[0]
    return Words(tuple(statement.words[1:]), statement.tokens[-1], {})


def redirect(words: Words):
    return REDIRECT.parse(words)


def redirect_simpson(words: Words):
    return REDIRECT_SIMPSON.parse(words)


def validate(tmp_path, then):
    """The real validator as a subprocess, which is what an operator runs.

    Logging is forced back on: the encoded UPDATE is only printed in the log.
    """
    conf = tmp_path / 'test.conf'
    conf.write_text(NEIGHBOUR % then)
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


# -- the community -------------------------------------------------------------------------------


def test_the_community_is_type_0x000d() -> None:
    community = TrafficRedirectIPv6.make_traffic_redirect_ipv6('2001:db8::1', 100)
    packed = bytes(community.pack_attribute(None))
    assert len(packed) == 20
    assert packed[:2] == b'\x00\x0d'


def test_the_community_decodes_as_what_it_encoded() -> None:
    packed = bytes(TrafficRedirectIPv6.make_traffic_redirect_ipv6('2001:db8::1', 100).pack_attribute(None))
    decoded = ExtendedCommunityIPv6.unpack_attribute(packed, None)
    assert isinstance(decoded, TrafficRedirectIPv6)
    assert decoded.ip == '2001:db8::1'
    assert decoded.asn == 100


def test_the_text_form_brackets_the_address() -> None:
    assert str(TrafficRedirectIPv6.make_traffic_redirect_ipv6('2001:db8::1', 100)) == 'redirect [2001:db8::1]:100'


# -- the parser ----------------------------------------------------------------------------------


def test_the_parser_reads_the_split_tokens() -> None:
    """What the tokeniser hands over for `redirect [2001:db8::1]:100;`."""
    nexthop, communities = redirect(tokens('[', '2001:db8::1', ']', ':100'))
    assert nexthop is IP.NoNextHop
    assert isinstance(communities, ExtendedCommunitiesIPv6)
    (community,) = communities.communities
    assert str(community) == 'redirect [2001:db8::1]:100'


def test_a_bracketed_address_alone_redirects_to_that_address() -> None:
    """`redirect [2001:db8::1];` still means redirect to that address, in the IETF community.

    It used to mean it by setting the route's next hop, which RFC 8955 4 forbids while
    advertising a flow specification. draft-ietf-idr-flowspec-redirect-ip, which replaces
    draft-simpson-idr-flowspec-redirect-ip, carries the address in the community instead, so
    the target is unchanged and the MP_REACH_NLRI next hop is now empty. Sub-type 0x0c, not
    the 0x0d of the route-target above.
    """
    nexthop, communities = redirect(tokens('[', '2001:db8::1', ']'))

    assert str(nexthop) == 'no-nexthop'
    assert isinstance(communities, ExtendedCommunitiesIPv6), 'a twenty octet community needs attribute 25'
    packed = b''.join(bytes(community.pack()) for community in communities)
    assert packed[0:2] == bytes([0x00, 0x0C])
    assert packed[2:18] == IP.from_string('2001:db8::1').pack_ip()


def test_the_older_bracketed_next_hop_encoding_is_still_reachable() -> None:
    """`redirect-simpson [2001:db8::1];` for anyone who needs the address in MP_REACH_NLRI."""
    nexthop, communities = redirect_simpson(tokens('[', '2001:db8::1', ']'))

    assert str(nexthop) == '2001:db8::1'
    packed = b''.join(bytes(community.pack()) for community in communities)
    assert packed[0:2] == bytes([0x08, 0x00]), 'the Simpson community, which carries no address'


@pytest.mark.parametrize(
    'content,why',
    [
        (('[', '2001:db8::1', ']', ':65536'), 'Local administrator'),
        (('[', '2001:db8::1', ':100'), 'redirect'),
        (('[', '10.0.0.1', ']', ':100'), 'IPv6'),
    ],
)
def test_the_parser_refuses_a_malformed_target(content, why) -> None:
    with pytest.raises(ValueError, match=why):
        redirect(tokens(*content))


# -- the configuration file and the API ----------------------------------------------------------


def test_the_configuration_puts_it_in_attribute_25(tmp_path) -> None:
    """The defect: a syntax error. The check is on the bytes a peer would receive."""
    result = validate(tmp_path, 'redirect [2001:db8::1]:100;')

    combined = result.stdout + result.stderr
    assert result.returncode == 0, combined[-1500:]
    assert WIRE in combined.replace(' ', ''), combined[-1500:]


def test_the_api_accepts_it() -> None:
    configuration = Configuration([''], text=True)
    line = 'route destination 2001:db8:1::/48 redirect [2001:db8::1]:100'
    assert configuration.partial('flow', line, 'announce'), str(configuration.error)
    (route,) = configuration.pop_routes()
    assert 'redirect [2001:db8::1]:100' in str(route.attributes)
