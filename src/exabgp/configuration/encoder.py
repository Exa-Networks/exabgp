"""encoder.py

JSON encoder for ExaBGP configuration types.

Created for configuration export testing.
Copyright (c) 2009-2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import is_dataclass
from typing import Any

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.neighbor.capability import GracefulRestartConfig, NeighborCapability
from exabgp.bgp.neighbor.session import Session
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPRange, IPSelf
from exabgp.rib.route import Route
from exabgp.util.enumeration import TriState


def _serialize_ip(obj: IP) -> dict[str, Any]:
    """Convert an IP, IPSelf or IPRange, tagged with its type."""
    # check IPSelf and IPRange before IP (subclass order matters)
    if isinstance(obj, IPSelf):
        return {'_type': 'IPSelf', 'afi': obj.afi.name()}

    if isinstance(obj, IPRange):
        return {'_type': 'IPRange', 'ip': obj.top(), 'mask': int(obj.mask)}

    # Check for NoNextHop sentinel
    if obj is IP.NoNextHop:
        return {'_type': 'IP', 'value': 'no-nexthop'}
    return {'_type': 'IP', 'value': obj.top()}


# The int subclasses json.dumps would write as a bare number, see _serialize_int_subclass
_INT_SUBCLASSES = (TriState, RoleValue, HoldTime, ASN, AFI, SAFI)


def _serialize_int_subclass(obj: int) -> dict[str, Any] | str:
    """Convert one of _INT_SUBCLASSES, tagged with its type (a RoleValue as its string)."""
    # TriState - IntEnum subclass
    if isinstance(obj, TriState):
        return {'_type': 'TriState', 'value': obj.name}

    if isinstance(obj, RoleValue):
        return str(obj)

    if isinstance(obj, HoldTime):
        return {'_type': 'HoldTime', 'value': int(obj)}

    if isinstance(obj, ASN):
        return {'_type': 'ASN', 'value': int(obj)}

    if isinstance(obj, AFI):
        return {'_type': 'AFI', 'value': obj.name()}

    assert isinstance(obj, SAFI), 'called only for the types of _INT_SUBCLASSES'
    return {'_type': 'SAFI', 'value': obj.name()}


# bytes and the containers _serialize_container recurses into (a Counter is a dict)
_CONTAINERS = (bytes, deque, dict, list, tuple)


def _serialize_container(obj: bytes | deque[Any] | dict[Any, Any] | list[Any] | tuple[Any, ...]) -> Any:
    """Convert bytes to hex, and a container to a list or dict of converted items."""
    # bytes - encode as hex string
    if isinstance(obj, bytes):
        return {'_type': 'bytes', 'hex': obj.hex()}

    # deque - convert to list and recurse
    if isinstance(obj, deque):
        return [_serialize_value(item) for item in obj]

    # Counter - convert to dict
    if isinstance(obj, Counter):
        return dict(obj)

    # dict - recurse into values
    if isinstance(obj, dict):
        return {k: _serialize_value(v) for k, v in obj.items()}

    # list/tuple - recurse into items
    assert isinstance(obj, (list, tuple)), 'called only for the types of _CONTAINERS'
    return [_serialize_value(item) for item in obj]


def _serialize_capability(obj: NeighborCapability) -> dict[str, Any]:
    """Convert a NeighborCapability, each TriState by its name."""
    return {
        '_type': 'NeighborCapability',
        'asn4': obj.asn4.name,
        'extended_message': obj.extended_message.name,
        'graceful_restart': _serialize_value(obj.graceful_restart),
        'multi_session': obj.multi_session.name,
        'operational': obj.operational.name,
        'add_path': obj.add_path,
        'route_refresh': obj.route_refresh.name,
        'enhanced_route_refresh': obj.enhanced_route_refresh.name,
        'nexthop': obj.nexthop.name,
        'aigp': obj.aigp.name,
        'software_version': obj.software_version,
    }


def _serialize_session(obj: Session) -> dict[str, Any]:
    """Convert a Session, falsy optional fields as None, the role only when one is set."""
    result = {
        '_type': 'Session',
        'peer_address': _serialize_value(obj.peer_address),
        'local_address': _serialize_value(obj.local_address),
        'local_as': _serialize_value(obj.local_as),
        'peer_as': _serialize_value(obj.peer_as),
        'router_id': _serialize_value(obj.router_id) if obj.router_id else None,
        'md5_password': obj.md5_password if obj.md5_password else None,
        'md5_base64': obj.md5_base64,
        'md5_ip': _serialize_value(obj.md5_ip) if obj.md5_ip else None,
        'connect': obj.connect,
        'listen': obj.listen,
        'passive': obj.passive,
        'source_interface': obj.source_interface if obj.source_interface else None,
        'outgoing_ttl': obj.outgoing_ttl,
        'incoming_ttl': obj.incoming_ttl,
    }
    if obj.role != RoleValue.NO_ROLE:
        result.update(role=str(obj.role), role_strict=obj.role_strict, role_add_meta=obj.role_add_meta)
    return result


def _serialize_value(obj: Any) -> Any:
    """Recursively convert ExaBGP types to JSON-serializable form.

    This function must be called before json.dumps() because types like
    ASN, AFI, SAFI, HoldTime that subclass int are serialized directly
    by JSON without calling the encoder's default() method.
    """
    # Handle None
    if obj is None:
        return None

    # IP addresses
    if isinstance(obj, IP):
        return _serialize_ip(obj)

    # TriState, RoleValue, HoldTime, ASN, AFI, SAFI - check before generic int
    if isinstance(obj, _INT_SUBCLASSES):
        return _serialize_int_subclass(obj)

    # GracefulRestartConfig
    if isinstance(obj, GracefulRestartConfig):
        return {
            '_type': 'GracefulRestartConfig',
            'state': obj.state.name,
            'time': obj.time,
        }

    # NeighborCapability
    if isinstance(obj, NeighborCapability):
        return _serialize_capability(obj)

    # Session
    if isinstance(obj, Session):
        return _serialize_session(obj)

    # Route (route with attributes)
    if isinstance(obj, Route):
        return {
            '_type': 'Route',
            'nlri': str(obj.nlri),
            'attributes': str(obj.attributes),
        }

    # bytes, deque, Counter, dict, list, tuple
    if isinstance(obj, _CONTAINERS):
        return _serialize_container(obj)

    # Generic dataclass handling (fallback)
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize_value(v) for k, v in obj.__dict__.items()}

    # Primitive types (str, int, float, bool) - return as-is
    return obj


class ConfigEncoder(json.JSONEncoder):
    """JSON encoder for ExaBGP configuration types.

    Note: For types that subclass int (ASN, AFI, SAFI, HoldTime, TriState),
    use config_to_json() which preprocesses data before encoding.
    Direct use of json.dumps(..., cls=ConfigEncoder) won't work for these types.

    Handles serialization of:
    - IP addresses (IP, IPv4, IPv6, IPRange)
    - ASN (Autonomous System Numbers)
    - AFI/SAFI (Address Family Identifiers)
    - HoldTime
    - TriState (capability states)
    - GracefulRestartConfig
    - NeighborCapability
    - Session
    - Change (NLRI + Attributes)
    - bytes (encoded as hex)
    - deque/Counter (converted to list/dict)
    """

    def default(self, obj: Any) -> Any:
        # Use the shared serialization function
        result = _serialize_value(obj)
        if result is not obj:
            return result
        # Let the default encoder raise TypeError for unknown types
        return super().default(obj)


def config_to_json(data: Any, indent: int = 2) -> str:
    """Convert configuration data to JSON string.

    This function preprocesses the data to handle types that subclass int
    (ASN, AFI, SAFI, HoldTime, TriState) which JSON's encoder cannot
    intercept with the default() method.

    Args:
        data: Configuration data to serialize
        indent: JSON indentation level (default: 2)

    Returns:
        JSON string representation
    """
    # Preprocess to convert all ExaBGP types
    serialized = _serialize_value(data)
    return json.dumps(serialized, sort_keys=True, indent=indent)
