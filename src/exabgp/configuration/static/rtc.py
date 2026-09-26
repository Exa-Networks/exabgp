"""configuration/static/rtc.py

Parser functions for RTC (Route Target Constraint, RFC 4684) NLRI fields.

  rtc origin-as <asn> route-target <route-target> next-hop <ip|self> [attributes]
  rtc default next-hop <ip|self> [attributes]

Created for issue #1109.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.community.extended import RouteTarget
from exabgp.configuration.static.parser import _extended_community

if TYPE_CHECKING:
    from exabgp.configuration.core.parser import Tokeniser


def rtc_origin_as(tokeniser: 'Tokeniser') -> ASN:
    """The AS originating the membership, plain or dotted."""
    return ASN.from_string(tokeniser())


def rtc_route_target(tokeniser: 'Tokeniser') -> RouteTarget:
    """A route target as `asn:number`, `ip:number` or `target:...`, the extended-community forms."""
    value = tokeniser()
    kind, _, rest = value.partition(':')
    if kind != 'target' and rest.count(':'):
        raise ValueError(f"'{value}' is not a route target\n  Format: <asn>:<number> or <ip>:<number>")
    community = _extended_community(value if kind == 'target' else f'target:{value}')
    if not isinstance(community, RouteTarget):
        raise ValueError(f"'{value}' is not a route target\n  Format: <asn>:<number> or <ip>:<number>")
    return community


def rtc_default(tokeniser: 'Tokeniser') -> bool:
    """The default route target, the zero-length prefix: it takes no value."""
    return True
