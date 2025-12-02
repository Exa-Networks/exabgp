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
from exabgp.bgp.neighbor.capability import GracefulRestartConfig, NeighborCapability
from exabgp.bgp.neighbor.session import Session
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPRange, IPSelf
from exabgp.rib.change import Change
from exabgp.util.enumeration import TriState


def _serialize_value(obj: Any) -> Any:
    """Recursively convert ExaBGP types to JSON-serializable form.

    This function must be called before json.dumps() because types like
    ASN, AFI, SAFI, HoldTime that subclass int are serialized directly
    by JSON without calling the encoder's default() method.
    """
    # Handle None
    if obj is None:
        return None

    # IP addresses - check IPSelf and IPRange before IP (subclass order matters)
    if isinstance(obj, IPSelf):
        return {'_type': 'IPSelf', 'afi': obj.afi.name()}

    if isinstance(obj, IPRange):
        return {'_type': 'IPRange', 'ip': obj.top(), 'mask': int(obj.mask)}

    if isinstance(obj, IP):
        # Check for NoNextHop sentinel
        if obj is IP.NoNextHop:
            return {'_type': 'IP', 'value': 'no-nexthop'}
        return {'_type': 'IP', 'value': obj.top()}

    # TriState - check before generic int (IntEnum subclass)
    if isinstance(obj, TriState):
        return {'_type': 'TriState', 'value': obj.name}

    # HoldTime - check before generic int
    if isinstance(obj, HoldTime):
        return {'_type': 'HoldTime', 'value': int(obj)}

    # ASN - check before generic int
    if isinstance(obj, ASN):
        return {'_type': 'ASN', 'value': int(obj)}

    # AFI/SAFI - check before generic int
    if isinstance(obj, AFI):
        return {'_type': 'AFI', 'value': obj.name()}

    if isinstance(obj, SAFI):
        return {'_type': 'SAFI', 'value': obj.name()}

    # GracefulRestartConfig
    if isinstance(obj, GracefulRestartConfig):
        return {
            '_type': 'GracefulRestartConfig',
            'state': obj.state.name,
            'time': obj.time,
        }

    # NeighborCapability
    if isinstance(obj, NeighborCapability):
        return {
            '_type': 'NeighborCapability',
            'asn4': obj.asn4.name,
            'extended_message': obj.extended_message.name,
            'graceful_restart': _serialize_value(obj.graceful_restart),
            'multi_session': obj.multi_session.name,
            'operational': obj.operational.name,
            'add_path': obj.add_path,
            'route_refresh': obj.route_refresh,
            'nexthop': obj.nexthop.name,
            'aigp': obj.aigp.name,
            'software_version': obj.software_version,
        }

    # Session
    if isinstance(obj, Session):
        return {
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

    # Change (route with attributes)
    if isinstance(obj, Change):
        return {
            '_type': 'Change',
            'nlri': str(obj.nlri),
            'attributes': str(obj.attributes),
        }

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
    if isinstance(obj, (list, tuple)):
        return [_serialize_value(item) for item in obj]

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
