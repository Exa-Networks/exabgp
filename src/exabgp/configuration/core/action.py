"""action.py - Unified action dispatch for configuration parsing.

This module provides a single source of truth for action dispatch,
replacing the duplicated if/elif chains in Section.parse() and validators.

Created by Thomas Mangin on 2025-12-11.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from exabgp.configuration.schema import ActionTarget, ActionOperation, ActionKey

if TYPE_CHECKING:
    from exabgp.configuration.core.scope import Scope


def apply_action(
    target: ActionTarget,
    operation: ActionOperation,
    key: ActionKey,
    scope: 'Scope',
    name: str,
    command: str,
    value: Any,
    field_name: str | None = None,
) -> None:
    """Apply an action to store a parsed value.

    This is the single source of truth for action dispatch, replacing
    the duplicated if/elif chains throughout the configuration parsing code.

    Note: This function assumes settings mode is always active (Q2 decision).
    All route building uses Settings pattern for immutable NLRI construction.

    Args:
        target: Where to store the value (SCOPE, ATTRIBUTE, NLRI, NEXTHOP, ROUTE)
        operation: How to store (SET, APPEND, EXTEND, ADD, NOP)
        key: Which key to use (COMMAND, NAME, FIELD)
        scope: The current parsing scope
        name: The section name (e.g., neighbor name)
        command: The command name (e.g., 'next-hop', 'origin')
        value: The parsed value to store
        field_name: Explicit field name for ActionKey.FIELD

    Raises:
        RuntimeError: If settings mode is required but not active
    """
    if operation == ActionOperation.NOP:
        return

    # Resolve the actual key to use
    actual_key = _resolve_key(key, command, name, field_name)

    # Dispatch based on target
    if target == ActionTarget.SCOPE:
        _apply_to_scope(scope, actual_key, operation, value)
    elif target == ActionTarget.ATTRIBUTE:
        _apply_to_attribute(scope, name, value)
    elif target == ActionTarget.NLRI:
        _apply_to_nlri(scope, actual_key, operation, value, name, command)
    elif target == ActionTarget.NEXTHOP:
        _apply_to_nexthop(scope, value, name)
    elif target == ActionTarget.NEXTHOP_ATTRIBUTE:
        _apply_to_nexthop_attribute(scope, value, name)
    elif target == ActionTarget.ROUTE:
        _apply_to_route(scope, value)


def _resolve_key(
    key: ActionKey,
    command: str,
    name: str,
    field_name: str | None,
) -> str:
    """Resolve the actual key to use for storage.

    Args:
        key: The key type (COMMAND, NAME, FIELD)
        command: The command name
        name: The section name
        field_name: Explicit field name for FIELD key

    Returns:
        The resolved key string
    """
    if key == ActionKey.COMMAND:
        return command
    elif key == ActionKey.NAME:
        return name
    else:  # ActionKey.FIELD
        return field_name or command


def _apply_to_scope(
    scope: 'Scope',
    key: str,
    operation: ActionOperation,
    value: Any,
) -> None:
    """Apply action to scope dict (general configuration).

    Args:
        scope: The current parsing scope
        key: The storage key
        operation: The operation (SET, APPEND, EXTEND)
        value: The value to store
    """
    if operation == ActionOperation.SET:
        scope.set_value(key, value)
    elif operation == ActionOperation.APPEND:
        scope.append(key, value)
    elif operation == ActionOperation.EXTEND:
        scope.extend(key, value)
    elif operation == ActionOperation.ADD:
        # ADD for scope is treated as APPEND
        scope.append(key, value)


def _apply_to_attribute(
    scope: 'Scope',
    name: str,
    value: Any,
) -> None:
    """Apply action to BGP attributes collection.

    In settings mode, adds to the standalone attributes collection
    that will be combined with the NLRI at route creation time.

    Args:
        scope: The current parsing scope
        name: The section name (for tracking added attributes)
        value: The attribute to add
    """
    if scope.in_settings_mode():
        # Settings mode: add to standalone attributes collection
        attrs = scope.get_settings_attributes()
        if attrs is not None:
            attrs.add(value)
    else:
        # Legacy mode: add directly to route's attributes
        scope.attribute_add(name, value)


def _apply_to_nlri(
    scope: 'Scope',
    field: str,
    operation: ActionOperation,
    value: Any,
    name: str = '',
    command: str = '',
) -> None:
    """Apply action to NLRI fields.

    Behavior differs by operation:
    - SET (nlri-set): Checks settings mode, sets field on Settings or NLRI directly
    - APPEND (nlri-add): Always uses scope.nlri_add() (original behavior never checked settings mode)

    Args:
        scope: The current parsing scope
        field: The NLRI field name
        operation: The operation (SET or APPEND)
        value: The value to store
        name: Section name (for nlri_add signature compatibility)
        command: Command name (for nlri_add signature compatibility)
    """
    if operation == ActionOperation.SET:
        # nlri-set: check settings mode (matches original behavior)
        if scope.in_settings_mode():
            settings = scope.get_settings()
            if settings is not None:
                settings.set(field, value)
        else:
            # Direct mode: set directly via setattr
            route = scope.get_route()
            setattr(route.nlri, field, value)
    elif operation == ActionOperation.APPEND:
        # nlri-add: ALWAYS use scope.nlri_add() (original never checked settings mode)
        # This is critical - flow spec rules use this path
        if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
            for item in value:
                scope.nlri_add(name, command, item)
        else:
            scope.nlri_add(name, command, value)


def _apply_to_nexthop(
    scope: 'Scope',
    value: Any,
    name: str = '',
) -> None:
    """Apply action to set NLRI next-hop only.

    This is for 'nlri-nexthop' action which ONLY sets the nexthop on the
    NLRI/Settings. It does NOT add a NextHop BGP attribute.

    For routes that need both nexthop AND NextHop attribute (like IPv4 unicast),
    use 'nexthop-and-attribute' which handles tuples and creates attributes.

    Flow routes use this action - their nexthop goes in MP_REACH_NLRI,
    not in a separate NextHop attribute.

    Args:
        scope: The current parsing scope
        value: The next-hop value (IP address)
        name: Section name (unused, kept for API compatibility)
    """
    # Just set the nexthop - no attribute creation
    if value:
        if scope.in_settings_mode():
            settings = scope.get_settings()
            if settings is None:
                raise RuntimeError('No settings object - call set_settings() first')
            settings.nexthop = value
        else:
            # Legacy mode: replace route with updated nexthop
            route = scope.get_route()
            scope.replace_route(route.with_nexthop(value))


def _apply_to_nexthop_attribute(
    scope: 'Scope',
    value: Any,
    name: str = '',
) -> None:
    """Apply action to set NLRI next-hop AND add BGP attribute.

    This is for 'nexthop-and-attribute' action which handles tuples of
    (IP, Attribute) from validators like NextHopValidator.

    For static routes (IPv4 unicast), both the NLRI nexthop AND a NextHop
    BGP attribute are needed. For flow redirect/copy, the tuple contains
    (IP, ExtendedCommunities).

    Args:
        scope: The current parsing scope
        value: Tuple of (IP, Attribute) or (IP, ExtendedCommunities)
        name: Section name (for attribute_add)
    """
    # Unpack the tuple
    if not isinstance(value, tuple) or len(value) < 2:
        raise ValueError(f'nexthop-and-attribute expects (IP, Attribute) tuple, got {type(value)}')

    ip_value, attribute = value[0], value[1]

    # Set the nexthop
    if ip_value:
        if scope.in_settings_mode():
            settings = scope.get_settings()
            if settings is None:
                raise RuntimeError('No settings object - call set_settings() first')
            settings.nexthop = ip_value
        else:
            # Legacy mode: replace route with updated nexthop
            route = scope.get_route()
            scope.replace_route(route.with_nexthop(ip_value))

    # Add the attribute if present
    if attribute:
        if scope.in_settings_mode():
            attrs = scope.get_settings_attributes()
            if attrs is not None:
                attrs.add(attribute)
        else:
            scope.attribute_add(name, attribute)


def _apply_to_route(
    scope: 'Scope',
    value: Any,
) -> None:
    """Apply action to extend routes list.

    Used for complete route objects (e.g., from route expressions).

    Args:
        scope: The current parsing scope
        value: Route(s) to add - can be single route or list
    """
    if isinstance(value, list):
        scope.extend_routes(value)
    else:
        scope.append_route(value)


# =============================================================================
# Helper functions for validators (work with Settings/Route directly)
# =============================================================================


def apply_action_to_settings(
    target: ActionTarget,
    operation: ActionOperation,
    key: ActionKey,
    settings: Any,
    attributes: Any,
    command: str,
    value: Any,
    field_name: str | None = None,
    assign: dict[str, str] | None = None,
) -> None:
    """Apply an action to Settings object (for RouteBuilderValidator).

    This is a helper for validators that work with Settings objects
    instead of Scope. Handles attribute-add, nlri-set, nlri-add, nlri-nexthop.

    Args:
        target: Where to store (ATTRIBUTE, NLRI, NEXTHOP)
        operation: How to store (SET, APPEND, ADD, NOP)
        key: Which key (COMMAND, FIELD)
        settings: The Settings object
        attributes: The AttributeCollection
        command: The command name
        value: The parsed value
        field_name: Explicit field name (for FIELD key)
        assign: Command to field mapping dict
    """
    if operation == ActionOperation.NOP:
        return

    # Resolve actual field name
    if key == ActionKey.FIELD and assign:
        actual_field = assign.get(command, field_name or command)
    elif field_name:
        actual_field = field_name
    else:
        actual_field = command.replace('-', '_')

    if target == ActionTarget.ATTRIBUTE:
        attributes.add(value)
    elif target == ActionTarget.NLRI:
        if operation == ActionOperation.SET:
            settings.set(actual_field, value)
        elif operation == ActionOperation.APPEND:
            # nlri-add: iterate and add each item
            if hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):
                for item in value:
                    if hasattr(settings, 'add_rule'):
                        settings.add_rule(item)
                    elif hasattr(settings, 'rules'):
                        settings.rules.append(item)
            else:
                if hasattr(settings, 'add_rule'):
                    settings.add_rule(value)
                elif hasattr(settings, 'rules'):
                    settings.rules.append(value)
    elif target == ActionTarget.NEXTHOP:
        # Handle composite values (IP, Attribute) or single IP
        from exabgp.bgp.message.update.attribute import NextHop, NextHopSelf
        from exabgp.protocol.ip import IPSelf

        ip_value = value
        nh_attr = None
        if isinstance(value, tuple) and len(value) >= 2:
            ip_value, nh_attr = value[0], value[1]
        elif not isinstance(value, tuple):
            # Single IP value - create NextHop attribute from it
            if isinstance(value, IPSelf):
                nh_attr = NextHopSelf(value.afi)
            elif value is not None and hasattr(value, 'top'):
                nh_attr = NextHop.from_string(value.top())

        settings.nexthop = ip_value
        if nh_attr is not None:
            attributes.add(nh_attr)
    elif target == ActionTarget.SCOPE:
        # set-command: store on settings for later processing
        if operation == ActionOperation.SET:
            setattr(settings, actual_field, value)


def apply_action_to_route(
    target: ActionTarget,
    operation: ActionOperation,
    route: Any,  # Route object
    value: Any,
    afi: Any = None,
    used_afi: bool = False,
) -> Any:
    """Apply an action to Route object (for TypeSelectorValidator).

    This is a helper for validators that work with Route objects
    in factory mode. Handles attribute-add, nexthop-and-attribute.

    Args:
        target: Where to store (ATTRIBUTE, NEXTHOP)
        operation: How to store (ADD, SET, NOP)
        route: The Route object
        value: The parsed value
        afi: AFI enum (for IPv6 nexthop handling)
        used_afi: Whether validator used AFI-aware parsing

    Returns:
        The (possibly modified) Route
    """
    if operation == ActionOperation.NOP:
        return route

    if target == ActionTarget.ATTRIBUTE:
        route.attributes.add(value)
    elif target == ActionTarget.NEXTHOP:
        # Handle composite values (IP, Attribute) or single IP
        from exabgp.bgp.message.update.attribute import NextHop, NextHopSelf
        from exabgp.protocol.ip import IPSelf

        ip_value = value
        nh_attr = None
        if isinstance(value, tuple) and len(value) >= 2:
            ip_value, nh_attr = value[0], value[1]
        elif not isinstance(value, tuple):
            # Single IP value - create NextHop attribute from it
            if isinstance(value, IPSelf):
                nh_attr = NextHopSelf(value.afi)
            elif value is not None and hasattr(value, 'top'):
                nh_attr = NextHop.from_string(value.top())

        route = route.with_nexthop(ip_value)
        if nh_attr is not None:
            route.attributes.add(nh_attr)

    return route
