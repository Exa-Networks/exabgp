"""prefix_limit.py

RFC 4486 4: the number of address prefixes a peer holds with us, per family, against the
`prefix-limit` configured for it.

Two paths put a received route into the adj-rib-in: the UPDATE handler, and the
revalidation of flow specifications (RFC 8955 6) which installs a flow held back once it
becomes feasible. Both count here, so the limit means the same whichever way a route
arrived, and both release here what leaves the adj-rib-in.

Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack
from typing import TYPE_CHECKING

from exabgp.bgp.message.notification import Notify

if TYPE_CHECKING:
    from exabgp.bgp.message.update.nlri.nlri import NLRI
    from exabgp.bgp.neighbor import Neighbor


def admit(neighbor: Neighbor, nlri: NLRI) -> None:
    """Count a route the peer now holds with us, past the family's limit end the session with Cease (6, 1)."""
    limits = neighbor.prefix_limit
    if not limits:
        return
    family = nlri.family().afi_safi()
    limit = limits.get(family)
    if limit is None:
        return
    count = neighbor.rib.incoming.count_prefix(nlri)
    # Not only one past: a reload applies a lower limit live, to a peer already over it
    if count <= limit:
        return
    raise Notify(
        *Notify.MAXIMUM_NUMBER_OF_PREFIXES_REACHED,
        f'more than {limit} routes received for {family[0]} {family[1]}',
        # the MAY of section 4: <AFI, SAFI> and the upper bound, as in its Figure 1
        data=pack('!HBI', family[0].value, family[1].value, limit),
    )


def release(neighbor: Neighbor, nlri: NLRI) -> None:
    """The route left the adj-rib-in: withdrawn, or a flow specification no longer feasible."""
    if neighbor.prefix_limit:
        neighbor.rib.incoming.uncount_prefix(nlri)
