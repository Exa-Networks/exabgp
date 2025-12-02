"""announce/route_builder.py

Shared route building utilities for schema-driven announcement parsing.
Separated to avoid circular imports between announce modules.

Created for Phase 1-3 of schema-announce migration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from exabgp.rib.change import Change

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.validator import RouteBuilderValidator

if TYPE_CHECKING:
    from exabgp.configuration.core import Tokeniser
    from exabgp.configuration.schema import RouteBuilder


def _build_route(
    tokeniser: 'Tokeniser',
    schema: 'RouteBuilder',
    afi: AFI,
    safi: SAFI,
    check_func: Callable[[Change, AFI | None], bool] | None = None,
) -> list[Change]:
    """Build route Change objects using schema-driven validation.

    This replaces the custom ip(), ip_label(), ip_vpn(), etc. functions
    with a single schema-driven implementation.

    Args:
        tokeniser: Token stream from configuration parser
        schema: RouteBuilder schema defining the route syntax
        afi: Address family identifier
        safi: Subsequent address family identifier
        check_func: Optional validation function for the Change object

    Returns:
        List containing the built Change object

    Raises:
        ValueError: If route fails validation check
    """
    action_type = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW

    validator = RouteBuilderValidator(
        schema=schema,
        afi=afi,
        safi=safi,
        action_type=action_type,
    )

    changes = validator.validate(tokeniser)

    if check_func:
        for change in changes:
            if not check_func(change, afi):
                raise ValueError('invalid route announcement (check failed)')

    return changes
