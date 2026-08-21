"""A family we can decode must have a next-hop encoding we can read.

MPRNLRI.unpack refuses any family missing from Family.size, so a family which is registered
as an NLRI decoder but absent from that table is one a peer can announce to us and have its
session torn down for. ipv6/multicast and bgp-ls/bgp-ls-vpn were both in that position.

The assertion is that the list is EMPTY, deliberately. A test which pins the known-missing
list keeps the gap forever and reports green while doing it: it passes while broken and
fails when fixed, which is the wrong way round.

Found by the session working the 5.0 branch, sweeping the adj-rib-out.
"""

from __future__ import annotations

import exabgp.bgp.message.update.attribute  # noqa: F401  registers every decoder
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import Family


def test_every_registered_family_has_a_next_hop_encoding() -> None:
    missing = sorted(f'{afi}/{safi}' for afi, safi in NLRI.known_families() if (afi, safi) not in Family.size)
    assert not missing, f'these families decode an NLRI but MPRNLRI cannot read their next-hop: {missing}'


def test_every_sized_family_has_a_decoder() -> None:
    """The other direction: a next-hop encoding for a family nothing decodes is dead weight.

    Not a defect, but it is how the table drifts out of step with the registry, which is
    what produced the gap above.
    """
    registered = set(NLRI.known_families())
    orphan = sorted(f'{afi}/{safi}' for afi, safi in Family.size if (afi, safi) not in registered)
    assert not orphan, f'Family.size describes families with no registered decoder: {orphan}'
