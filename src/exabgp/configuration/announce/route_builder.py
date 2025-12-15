"""announce/route_builder.py

Shared route building utilities for schema-driven announcement parsing.
Separated to avoid circular imports between announce modules.

Created for Phase 1-3 of schema-announce migration.
Phase 4-5: Added TypeSelectorBuilder support for MUP/MVPN.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from exabgp.bgp.message import Action

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.configuration.validator import RouteBuilderValidator
from exabgp.configuration.validator import TypeSelectorValidator

if TYPE_CHECKING:
    from exabgp.rib.route import Route
    from exabgp.configuration.core import Tokeniser
    from exabgp.configuration.schema import RouteBuilder, TypeSelectorBuilder


def _build_route(
    tokeniser: 'Tokeniser',
    schema: 'RouteBuilder',
    afi: AFI,
    safi: SAFI,
) -> list['Route']:
    """Build route objects using schema-driven validation.

    Args:
        tokeniser: Token stream from configuration parser
        schema: RouteBuilder schema defining the route syntax
        afi: Address family identifier
        safi: Subsequent address family identifier

    Returns:
        List containing the built Route objects
    """
    action_type = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW

    validator = RouteBuilderValidator(
        schema=schema,
        afi=afi,
        safi=safi,
        action_type=action_type,
    )

    return validator.validate(tokeniser)


def _build_type_selector_route(
    tokeniser: 'Tokeniser',
    schema: 'TypeSelectorBuilder',
    afi: AFI,
    safi: SAFI,
) -> list['Route']:
    """Build Route objects using type-selector validation.

    First token selects the NLRI type/factory, then remaining tokens
    are parsed as attributes.

    Args:
        tokeniser: Token stream from configuration parser
        schema: TypeSelectorBuilder schema defining valid types and attributes
        afi: Address family identifier
        safi: Subsequent address family identifier

    Returns:
        List containing the built Route objects
    """
    action_type = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW

    validator = TypeSelectorValidator(
        schema=schema,
        afi=afi,
        safi=safi,
        action_type=action_type,
    )

    return validator.validate(tokeniser)
