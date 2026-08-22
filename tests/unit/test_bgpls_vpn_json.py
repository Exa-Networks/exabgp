"""A BGP-LS VPN link rendered a line no JSON parser accepts.

RouteDistinguisher.json() returns a MEMBER, '"rd": "10.0.0.1:7"', not an object.  link.py
wrapped it in braces, splicing a nameless object into the middle of the one it was building:

    { ..., "link-identifiers": [  ], { "rd": "10.0.0.1:7" } }

Not a lost field, the whole line.  Same failure class as GHSA-jcrv-p53f-v5w5, which this
series opened on, in the one family neither branch's corpus covered.

node.py, prefixv4.py and prefixv6.py never had the braces, and only a link NLRI reaches
that line, so three families rendered correctly and the fourth did not.

Found by session 5.0 after the bgp-ls-vpn seed was added, which happened because comparing
the seed table against Family.size showed the family declared a route distinguisher and had
no seed.  A coverage check found a rendering bug: the family was uncovered BECAUSE it is the
only one which both carries a distinguisher and renders it through this path.
"""

from __future__ import annotations

import json as jsonlib
from struct import pack

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

DISTINGUISHER = bytes([0, 1]) + bytes([10, 0, 0, 1]) + bytes([0, 7])
IFACE_ADDRESS = pack('!HH', 259, 4) + bytes([192, 0, 2, 1])
IP_REACHABILITY = pack('!HH', 265, 4) + bytes([24, 192, 0, 2])

# name, NLRI type code, the descriptor which makes that type decodable
SHAPES = [
    ('link', 2, IFACE_ADDRESS),
    ('prefix v4', 3, IP_REACHABILITY),
    ('prefix v6', 4, IP_REACHABILITY),
]

IDS = [row[0] for row in SHAPES]


def decoded(code: int, descriptor: bytes, safi: SAFI, prefix: bytes) -> NLRI:
    body = bytes([3]) + bytes(8) + descriptor
    wire = pack('!HH', code, len(body) + len(prefix)) + prefix + body
    nlri, _ = NLRI.unpack_nlri(AFI.bgpls, safi, wire, Action.ANNOUNCE, None, None)
    return nlri


@pytest.mark.parametrize('name, code, descriptor', SHAPES, ids=IDS)
def test_a_vpn_nlri_renders_json_a_consumer_can_read(name: str, code: int, descriptor: bytes) -> None:
    """The whole line has to parse, which is what the braces broke."""
    rendered = decoded(code, descriptor, SAFI.bgp_ls_vpn, DISTINGUISHER).json()

    try:
        jsonlib.loads(rendered)
    except ValueError as exc:
        raise AssertionError(f'{name} with a route distinguisher renders unparseable JSON: {exc}') from None


@pytest.mark.parametrize('name, code, descriptor', SHAPES, ids=IDS)
def test_the_distinguisher_is_a_member_of_the_object(name: str, code: int, descriptor: bytes) -> None:
    """Parsing is not enough: it has to arrive as rd, not swallowed or renamed.

    A renderer which dropped the distinguisher entirely would satisfy the test above, which
    is the shape this whole series keeps finding.
    """
    document = jsonlib.loads(decoded(code, descriptor, SAFI.bgp_ls_vpn, DISTINGUISHER).json())

    assert document.get('rd') == '10.0.0.1:7', f'{name} lost its route distinguisher: {sorted(document)}'


@pytest.mark.parametrize('name, code, descriptor', SHAPES, ids=IDS)
def test_the_same_nlri_without_a_distinguisher_still_parses(name: str, code: int, descriptor: bytes) -> None:
    """The plain family must not have been changed by fixing the VPN one."""
    rendered = decoded(code, descriptor, SAFI.bgp_ls, b'').json()

    document = jsonlib.loads(rendered)
    assert 'rd' not in document, f'{name} without a distinguisher rendered one anyway'


def test_the_seed_reaches_the_renderer_which_was_broken() -> None:
    """Only a LINK NLRI reaches the line which had the braces.

    Without this, the parametrisation could lose its link row and the file would still
    report three green rows about two families which were never broken.
    """
    rendered = decoded(2, IFACE_ADDRESS, SAFI.bgp_ls_vpn, DISTINGUISHER).json()

    assert 'bgpls-link' in rendered, 'the link seed no longer decodes to a link NLRI'
    assert '"rd"' in rendered
