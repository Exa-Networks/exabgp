"""The flow redirect-to-IP actions send the IETF community, and the older one on request.

draft-ietf-idr-flowspec-redirect-ip, which is in the RFC Editor queue, formally replaces
draft-simpson-idr-flowspec-redirect-ip. The two differ in where the target address goes:

  IETF     the address is in the extended community, and MP_REACH_NLRI carries no next hop
  Simpson  the community carries no address, and the target IS the MP_REACH_NLRI next hop

RFC 8955 section 4 says "the Length of the Next-Hop Network Address MUST be set to 0" when
advertising flow specifications, so only the first form is conformant. exabgp sent the
Simpson one for `redirect <ip>`, `copy <ip>` and `redirect-to-nexthop`.

`redirect-to-nexthop` can be moved without breaking anything, because the two forms are
told apart by whether an address follows: the dispatcher drops the terminating `;` before
the leaf parser runs, so `peek()` is empty for the bare form. `redirect <ip>` and
`copy <ip>` always carried an address, so nothing distinguishes old from new and they
change what they send; `redirect-simpson` and `copy-simpson` are how to ask for the old
bytes, and one warning per process says so.
"""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.lexer import lex_text
from exabgp.configuration.grammar.types import flow as flow_types
from exabgp.configuration.grammar.types.flow import COPY as copy
from exabgp.configuration.grammar.types.flow import COPY_SIMPSON as copy_simpson
from exabgp.configuration.grammar.types.flow import REDIRECT as redirect
from exabgp.configuration.grammar.types.flow import REDIRECT_SIMPSON as redirect_simpson
from exabgp.configuration.grammar.types.flow import REDIRECT_TO_NEXTHOP as redirect_next_hop
from exabgp.configuration.grammar.types.flow import REDIRECT_TO_NEXTHOP_IETF as redirect_next_hop_ietf
from exabgp.configuration.grammar.types.flow import REDIRECT_TO_NEXTHOP_SIMPSON as redirect_next_hop_simpson
from exabgp.configuration.grammar.words import Words

# draft-ietf-idr-flowspec-redirect-ip: IPv4-address-specific transitive, sub-type 0x0c
IETF_IPV4 = bytes([0x01, 0x0C])
# and 0x000c for the IPv6-address-specific one
IETF_IPV6 = bytes([0x00, 0x0C])
# draft-simpson-idr-flowspec-redirect-ip
SIMPSON = bytes([0x08, 0x00])

# the C bit lives in the low bit of the two octet Local Administrator field
COPY_BIT = 0x01


def parsed(operation, *words):
    """Read one flow value the way the grammar does: the words after its keyword, before the `;`."""
    statement = lex_text(' '.join([operation.name, *words, ';']))[0]
    outcome = operation.parse(Words(tuple(statement.words[1:]), statement.tokens[-1], {}))
    if isinstance(outcome, tuple):
        nexthop, communities = outcome
    else:
        nexthop, communities = None, outcome
    packed = b''.join(bytes(community.pack()) for community in communities)
    return nexthop, packed


def test_redirect_to_nexthop_without_an_address_is_unchanged():
    """The whole point of the dispatch: every configuration written before it still works."""
    _, packed = parsed(redirect_next_hop)

    assert packed[0:2] == SIMPSON
    assert packed == bytes([0x08, 0x00]) + bytes(6), 'the Simpson community carries no address'


def test_redirect_to_nexthop_with_an_address_is_the_ietf_form():
    _, packed = parsed(redirect_next_hop, '1.2.3.4')

    assert packed[0:2] == IETF_IPV4
    assert packed[2:6] == bytes([1, 2, 3, 4]), 'the address belongs in the community'
    assert not packed[7] & COPY_BIT, 'a redirect is not a copy'


def test_the_ietf_keyword_and_the_dispatched_form_agree():
    """`redirect-to-nexthop-ietf <ip>` is kept, so it must encode identically."""
    _, dispatched = parsed(redirect_next_hop, '1.2.3.4')
    _, explicit = parsed(redirect_next_hop_ietf, '1.2.3.4')

    assert dispatched == explicit


def test_the_simpson_keyword_and_the_bare_form_agree():
    _, bare = parsed(redirect_next_hop)
    _, explicit = parsed(redirect_next_hop_simpson)

    assert bare == explicit


@pytest.mark.parametrize(
    'address,expected_type',
    [('1.2.3.4', IETF_IPV4), ('2001:db8::1', IETF_IPV6)],
    ids=['ipv4', 'ipv6'],
)
def test_redirect_to_an_address_sends_the_ietf_community_and_no_next_hop(address, expected_type):
    nexthop, packed = parsed(redirect, address)

    assert packed[0:2] == expected_type
    assert str(nexthop) == 'no-nexthop', 'RFC 8955 4 wants the MP_REACH next hop empty'


def test_copy_sets_the_copy_bit_and_no_next_hop():
    nexthop, packed = parsed(copy, '1.2.3.4')

    assert packed[0:2] == IETF_IPV4
    assert packed[2:6] == bytes([1, 2, 3, 4])
    assert packed[7] & COPY_BIT, 'the C bit is what tells a copy from a redirect'
    assert str(nexthop) == 'no-nexthop'


def test_the_older_encodings_stay_reachable():
    """Whoever depends on the address being in MP_REACH_NLRI can still ask for it."""
    redirect_nexthop, redirect_packed = parsed(redirect_simpson, '1.2.3.4')
    copy_nexthop, copy_packed = parsed(copy_simpson, '1.2.3.4')

    assert redirect_packed[0:2] == SIMPSON
    assert str(redirect_nexthop) == '1.2.3.4', 'the Simpson target is the next hop'
    assert copy_packed[0:2] == SIMPSON
    assert copy_packed[7] & COPY_BIT
    assert str(copy_nexthop) == '1.2.3.4'


def test_a_route_target_redirect_is_untouched():
    """`redirect <asn>:<nn>` is RFC 8955 7.4 and was always conformant."""
    nexthop, packed = parsed(redirect, '65500:12345')

    assert packed[0:2] == bytes([0x80, 0x08]), 'rt-redirect, sub-type 0x08'
    assert str(nexthop) == 'no-nexthop'


def test_an_ipv6_route_target_redirect_is_untouched():
    """`redirect [<ipv6>]:<nn>` is the RFC 8956 6.1 form."""
    nexthop, packed = parsed(redirect, '[', '2001:db8::1', ']', ':100')

    assert packed[0:2] == bytes([0x00, 0x0D]), 'the IPv6 route-target, not 0x000c'
    assert str(nexthop) == 'no-nexthop'


def test_the_change_of_meaning_is_said_once(monkeypatch):
    """One line per process, not one per route.

    A flow table reloaded on a timer would otherwise write the same warning forever, which
    is how a warning stops being read. The two keywords whose bytes changed share the flag:
    an operator needs to be told that this release encodes them differently, once.
    """
    said: list[str] = []
    monkeypatch.setattr(flow_types, '_TOLD_ABOUT_THE_IETF_DEFAULT', [False])
    monkeypatch.setattr(flow_types.log, 'warning', lambda message, source='': said.append(message()))

    parsed(redirect, '1.2.3.4')
    parsed(copy, '1.2.3.4')
    parsed(redirect, '5.6.7.8')

    assert len(said) == 1, f'three changed actions produced {len(said)} warnings'
    assert 'redirect-simpson' in said[0], 'the warning does not say how to keep the old bytes'
    assert 'draft-ietf-idr-flowspec-redirect-ip' in said[0], 'the warning does not name the document'


def test_asking_for_the_older_form_says_nothing(monkeypatch):
    """An operator who wrote -simpson has already chosen; there is nothing to warn about."""
    said: list[str] = []
    monkeypatch.setattr(flow_types, '_TOLD_ABOUT_THE_IETF_DEFAULT', [False])
    monkeypatch.setattr(flow_types.log, 'warning', lambda message, source='': said.append(message()))

    parsed(redirect_simpson, '1.2.3.4')
    parsed(copy_simpson, '1.2.3.4')
    parsed(redirect_next_hop)
    parsed(redirect_next_hop_simpson)
    parsed(redirect, '65500:12345')

    assert said == [], f'the unchanged forms warned: {said}'


@pytest.mark.parametrize(
    'target',
    ['65001:100', '1.2.3.4:5678', '[2001:db8::1]:100'],
    ids=['asn-rt', 'ipv4-rt', 'ipv6-rt'],
)
def test_the_older_form_refuses_a_route_target_with_a_reason(target):
    """A route-target redirect is conformant already, so it has no -simpson form.

    Asserting on the message rather than only on the refusal, because the easy way to
    write this check is `IP.toafi(target)`, and that answers ipv6 for anything holding a
    colon. A route-target passes it, reaches IP.from_string, and the operator is shown
    "illegal IP address string passed to inet_pton" instead of a reason.
    """
    words = ['[', target[1:].split(']:')[0], ']', ':' + target.split(']:')[-1]] if target.startswith('[') else [target]

    with pytest.raises(ValueError) as raised:
        parsed(redirect_simpson, *words)

    message = str(raised.value)
    assert 'inet_pton' not in message, 'the operator is shown the exception rather than the reason'
    assert 'redirect-simpson takes an address' in message
    assert 'no -simpson form' in message
    assert f'write "redirect {target}"' in message
