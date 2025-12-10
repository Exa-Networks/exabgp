"""validator.py

YANG-inspired type validators for configuration values.

This module provides composable validators that parse string input and return
typed values. Validators can be chained with .then() for additional transformations,
configured with type-specific methods, and exported to JSON Schema.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import re
from abc import abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.asn import ASN
    from exabgp.bgp.message.update.attribute import MED, LocalPreference, NextHop, NextHopSelf, Origin
    from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
    from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher
    from exabgp.configuration.core.parser import Tokeniser
    from exabgp.configuration.schema import ValueType
    from exabgp.protocol.ip import IP, IPRange, IPSelf
    from exabgp.rib.route import Route

T = TypeVar('T')


# =============================================================================
# Base Validator Class
# =============================================================================


@dataclass
class Validator(Generic[T]):
    """Base class for composable validators.

    Validators parse string input and return typed values. They can be:
    - Chained with .then() for additional transformations
    - Configured with type-specific methods (.in_range(), .with_choices())
    - Exported to JSON Schema with .to_schema()

    Example:
        >>> v = IntegerValidator().in_range(0, 100)
        >>> v.validate_string('50')
        50
        >>> v.validate_string('150')
        ValueError: 150 exceeds maximum 100
    """

    name: str = ''
    _chain: list[Callable[[Any], Any]] = field(default_factory=list)

    @abstractmethod
    def _parse(self, value: str) -> T:
        """Parse string to target type. Override in subclasses."""
        raise NotImplementedError

    def validate_string(self, value: str) -> T:
        """Parse string and apply validation chain."""
        result = self._parse(value)
        for step in self._chain:
            result = step(result)
        return result

    def validate(self, tokeniser: 'Tokeniser') -> T:
        """Parse from tokeniser and validate."""
        value = tokeniser()
        return self.validate_string(value)

    def then(self, step: Callable[[T], T]) -> 'Validator[T]':
        """Chain an additional transformation/validation step.

        Returns a new validator with the step appended.

        Example:
            >>> v = IntegerValidator().then(lambda x: x * 2)
            >>> v.validate_string('5')
            10
        """
        new = deepcopy(self)
        new._chain.append(step)
        return new

    def to_schema(self) -> dict[str, Any]:
        """Export validator constraints as JSON Schema dict.

        Override in subclasses to add type-specific constraints.
        """
        return {'type': self.name}

    def describe(self) -> str:
        """Human-readable description of valid values."""
        return self.name


# =============================================================================
# Basic Type Validators
# =============================================================================


@dataclass
class StringValidator(Validator[str]):
    """Validates string values with optional length and pattern constraints."""

    name: str = 'string'
    min_length: int | None = None
    max_length: int | None = None
    pattern: str | None = None

    def _parse(self, value: str) -> str:
        if self.min_length is not None and len(value) < self.min_length:
            raise ValueError(f"'{value}' is too short (minimum {self.min_length} characters)")
        if self.max_length is not None and len(value) > self.max_length:
            raise ValueError(f"'{value}' is too long (maximum {self.max_length} characters)")
        if self.pattern is not None:
            if not re.match(self.pattern, value):
                raise ValueError(f"'{value}' does not match required pattern")
        return value

    def with_length(self, min_len: int | None = None, max_len: int | None = None) -> 'StringValidator':
        """Return new validator with length constraints."""
        new = deepcopy(self)
        new.min_length = min_len
        new.max_length = max_len
        return new

    def with_pattern(self, pattern: str) -> 'StringValidator':
        """Return new validator with regex pattern constraint."""
        new = deepcopy(self)
        new.pattern = pattern
        return new

    def to_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {'type': 'string'}
        if self.min_length is not None:
            schema['minLength'] = self.min_length
        if self.max_length is not None:
            schema['maxLength'] = self.max_length
        if self.pattern is not None:
            schema['pattern'] = self.pattern
        return schema


@dataclass
class IntegerValidator(Validator[int]):
    """Validates integer values with optional range constraints."""

    name: str = 'integer'
    min_value: int | None = None
    max_value: int | None = None

    def _parse(self, value: str) -> int:
        try:
            num = int(value)
        except ValueError:
            raise ValueError(f"'{value}' is not a valid integer") from None

        if self.min_value is not None and num < self.min_value:
            raise ValueError(f'{num} is below minimum {self.min_value}')
        if self.max_value is not None and num > self.max_value:
            raise ValueError(f'{num} exceeds maximum {self.max_value}')
        return num

    def in_range(self, min_val: int, max_val: int) -> 'IntegerValidator':
        """Return new validator with range constraint.

        Example:
            >>> v = IntegerValidator().in_range(0, 65535)
            >>> v.validate_string('1000')
            1000
        """
        new = deepcopy(self)
        new.min_value = min_val
        new.max_value = max_val
        return new

    def positive(self) -> 'IntegerValidator':
        """Return new validator requiring non-negative values (>= 0)."""
        new = deepcopy(self)
        new.min_value = 0
        return new

    def to_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {'type': 'integer'}
        if self.min_value is not None:
            schema['minimum'] = self.min_value
        if self.max_value is not None:
            schema['maximum'] = self.max_value
        return schema

    def describe(self) -> str:
        if self.min_value is not None and self.max_value is not None:
            return f'integer ({self.min_value}-{self.max_value})'
        if self.min_value is not None:
            return f'integer (>= {self.min_value})'
        if self.max_value is not None:
            return f'integer (<= {self.max_value})'
        return 'integer'


@dataclass
class BooleanValidator(Validator[bool]):
    """Validates boolean values with multiple accepted formats."""

    name: str = 'boolean'
    default: bool | None = None

    TRUE_VALUES = ('true', 'enable', 'enabled', 'yes', '1')
    FALSE_VALUES = ('false', 'disable', 'disabled', 'no', '0')

    def _parse(self, value: str) -> bool:
        lower = value.lower()
        if lower in self.TRUE_VALUES:
            return True
        if lower in self.FALSE_VALUES:
            return False
        if not lower and self.default is not None:
            return self.default
        raise ValueError(
            f"'{value}' is not a valid boolean\n"
            f'  Valid options: true, false, enable, disable, enabled, disabled, yes, no'
        )

    def with_default(self, default: bool) -> 'BooleanValidator':
        """Return new validator with default value for empty input."""
        new = deepcopy(self)
        new.default = default
        return new

    def to_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {'type': 'boolean'}
        if self.default is not None:
            schema['default'] = self.default
        return schema


@dataclass
class FlagValidator(Validator[bool]):
    """Validates presence-only flags that don't require a value.

    This is used for BGP attributes like atomic-aggregate that are
    specified by mere presence (e.g., 'atomic-aggregate;') without a value.

    Unlike BooleanValidator, this always returns True and accepts:
    - Empty string (most common for presence flags)
    - 'true' (for explicit confirmation)

    Example:
        >>> v = FlagValidator()
        >>> v.validate_string('')  # Presence alone
        True
        >>> v.validate_string('true')  # Explicit
        True
    """

    name: str = 'flag'

    def _parse(self, value: str) -> bool:
        """Parse flag - presence means True."""
        if not value or value.lower() in ('', 'true'):
            return True
        raise ValueError(
            f"'{value}' is not valid for a presence flag\n  Flags are set by presence alone (no value needed)"
        )

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'boolean', 'const': True, 'description': 'Presence flag - no value required'}

    def describe(self) -> str:
        return 'flag (presence-only, no value)'


@dataclass
class EnumerationValidator(Validator[str]):
    """Validates against a list of allowed choices."""

    name: str = 'enumeration'
    choices: list[str] = field(default_factory=list)
    case_sensitive: bool = False

    def _parse(self, value: str) -> str:
        if not self.choices:
            return value

        check = value if self.case_sensitive else value.lower()
        valid = self.choices if self.case_sensitive else [c.lower() for c in self.choices]

        if check not in valid:
            raise ValueError(f"'{value}' is not a valid choice\n  Valid options: {', '.join(self.choices)}")

        # Return canonical form
        if not self.case_sensitive:
            return self.choices[valid.index(check)]
        return value

    def with_choices(self, choices: list[str]) -> 'EnumerationValidator':
        """Return new validator with specified choices."""
        new = deepcopy(self)
        new.choices = choices
        return new

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'string', 'enum': self.choices}

    def describe(self) -> str:
        if self.choices:
            return f'one of: {", ".join(self.choices)}'
        return 'enumeration'


# =============================================================================
# Network Type Validators
# =============================================================================


@dataclass
class PortValidator(Validator[int]):
    """Validates TCP/UDP port numbers (1-65535)."""

    name: str = 'port'

    def _parse(self, value: str) -> int:
        try:
            port_num = int(value)
        except ValueError:
            raise ValueError(f"'{value}' is not a valid port number (must be 1-65535)") from None
        if port_num < 1 or port_num > 65535:
            raise ValueError(f'port {port_num} is invalid (must be 1-65535)')
        return port_num

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'integer', 'minimum': 1, 'maximum': 65535}

    def describe(self) -> str:
        return 'port (1-65535)'


@dataclass
class IPAddressValidator(Validator['IP']):
    """Validates IPv4 and/or IPv6 addresses."""

    name: str = 'ip-address'
    allow_v4: bool = True
    allow_v6: bool = True

    def _parse(self, value: str) -> 'IP':
        from exabgp.protocol.family import AFI
        from exabgp.protocol.ip import IP

        try:
            ip_obj = IP.from_string(value)
        except (OSError, IndexError, ValueError):
            raise ValueError(f"'{value}' is not a valid IP address") from None

        if ip_obj.afi == AFI.ipv4 and not self.allow_v4:
            raise ValueError(f"'{value}' - IPv4 not allowed, IPv6 required")
        if ip_obj.afi == AFI.ipv6 and not self.allow_v6:
            raise ValueError(f"'{value}' - IPv6 not allowed, IPv4 required")

        return ip_obj

    def ipv4_only(self) -> 'IPAddressValidator':
        """Return validator accepting only IPv4."""
        new = deepcopy(self)
        new.allow_v6 = False
        return new

    def ipv6_only(self) -> 'IPAddressValidator':
        """Return validator accepting only IPv6."""
        new = deepcopy(self)
        new.allow_v4 = False
        return new

    def to_schema(self) -> dict[str, Any]:
        if self.allow_v4 and self.allow_v6:
            return {'type': 'string', 'format': 'ip-address'}
        if self.allow_v4:
            return {'type': 'string', 'format': 'ipv4'}
        return {'type': 'string', 'format': 'ipv6'}

    def describe(self) -> str:
        if self.allow_v4 and self.allow_v6:
            return 'IP address (IPv4 or IPv6)'
        if self.allow_v4:
            return 'IPv4 address'
        return 'IPv6 address'


@dataclass
class IPPrefixValidator(Validator['IPRange']):
    """Validates IP prefix in CIDR notation with host bits validation."""

    name: str = 'ip-prefix'

    def _parse(self, value: str) -> 'IPRange':
        from exabgp.protocol.ip import IP, IPRange

        try:
            if '/' in value:
                ip_str, mask_str = value.split('/', 1)
                mask = int(mask_str)
            else:
                ip_str = value
                mask = 128 if ':' in value else 32

            iprange = IPRange(IP.pton(ip_str), mask)

            # Validate host bits are zero
            if iprange.address() & iprange.mask.hostmask() != 0:
                raise ValueError(
                    f"'{value}' is not a valid network\n  Host bits must be zero for the given prefix length"
                )

            return iprange
        except (OSError, IndexError, ValueError) as e:
            if 'Host bits' in str(e):
                raise
            raise ValueError(
                f"'{value}' is not a valid IP prefix\n  Format: <ip>/<length> (e.g., 192.0.2.0/24)"
            ) from None

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'string', 'format': 'ip-prefix'}

    def describe(self) -> str:
        return 'IP prefix (CIDR notation)'


@dataclass
class IPRangeValidator(Validator['IPRange']):
    """Validates IP address or IP/prefix range (for peer-address)."""

    name: str = 'ip-range'

    def _parse(self, value: str) -> 'IPRange':
        from exabgp.protocol.ip import IP, IPRange

        try:
            if '/' in value:
                ip_str, mask_str = value.split('/', 1)
                mask = int(mask_str)
            else:
                ip_str = value
                mask = 128 if ':' in value else 32

            return IPRange(IP.pton(ip_str), mask)
        except (OSError, IndexError, ValueError):
            raise ValueError(
                f"'{value}' is not a valid IP address or range\n"
                f'  Format: <ip> or <ip>/<prefix> (e.g., 192.0.2.1 or 192.0.2.0/24)'
            ) from None

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'string', 'format': 'ip-range'}

    def describe(self) -> str:
        return 'IP address or range'


@dataclass
class ASNValidator(Validator['ASN | None']):
    """Validates AS numbers in plain or dotted notation."""

    name: str = 'as-number'
    allow_auto: bool = False

    def _parse(self, value: str) -> 'ASN | None':
        from exabgp.bgp.message.open.asn import ASN

        if self.allow_auto and value.lower() == 'auto':
            return None

        try:
            if '.' in value:
                high, low = value.split('.', 1)
                as_number = (int(high) << 16) + int(low)
            else:
                as_number = int(value)
            return ASN(as_number)
        except ValueError:
            expected = 'ASN (e.g., 65001 or 1.1)'
            if self.allow_auto:
                expected += " or 'auto'"
            raise ValueError(f"'{value}' is not a valid {expected}") from None

    def with_auto(self) -> 'ASNValidator':
        """Return validator that also accepts 'auto' keyword."""
        new = deepcopy(self)
        new.allow_auto = True
        return new

    def to_schema(self) -> dict[str, Any]:
        schema: dict[str, Any] = {'type': 'string', 'pattern': r'^\d+(\.\d+)?$'}
        if self.allow_auto:
            schema['pattern'] = r'^(\d+(\.\d+)?|auto)$'
        return schema

    def describe(self) -> str:
        if self.allow_auto:
            return "AS number or 'auto'"
        return 'AS number'


# =============================================================================
# BGP-Specific Validators
# =============================================================================


@dataclass
class RouteDistinguisherValidator(Validator['RouteDistinguisher']):
    """Validates Route Distinguisher values (RFC 4364).

    Supports three formats:
    - Type 0: ASN:nn (2-byte AS + 4-byte number, e.g., "65000:100")
    - Type 1: IP:nn (IPv4 address + 2-byte number, e.g., "192.0.2.1:100")
    - Type 2: ASN:nn (4-byte AS + 2-byte number, e.g., "4200000000:100")
    """

    name: str = 'route-distinguisher'

    def _parse(self, value: str) -> 'RouteDistinguisher':
        from struct import pack

        from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher

        separator = value.find(':')
        if separator <= 0:
            raise ValueError(
                f"'{value}' is not a valid route-distinguisher\n"
                f"  Expected format: ASN:nn or IP:nn (e.g., '65000:100' or '192.0.2.1:100')"
            )

        prefix = value[:separator]
        try:
            suffix = int(value[separator + 1 :])
        except ValueError:
            raise ValueError(f"'{value}' is not a valid route-distinguisher\n  Suffix must be a number") from None

        # Type 1: IPv4:nn (IPv4 address administrator)
        if '.' in prefix:
            if suffix >= pow(2, 16):
                raise ValueError(f'Suffix {suffix} too large for IPv4 RD (max 65535)')
            try:
                data_list: list[bytes] = [bytes([0, 1])]
                data_list.extend([bytes([int(_)]) for _ in prefix.split('.')])
                data_list.extend([bytes([suffix >> 8]), bytes([suffix & 0xFF])])
                rtd = b''.join(data_list)
                return RouteDistinguisher(rtd)
            except (ValueError, IndexError):
                raise ValueError(f"'{value}' is not a valid route-distinguisher (invalid IPv4 address)") from None

        # Type 0 or Type 2: ASN:nn
        try:
            number = int(prefix)
        except ValueError:
            raise ValueError(f"'{value}' is not a valid route-distinguisher (prefix must be ASN or IPv4)") from None

        # Type 0: 2-byte ASN + 4-byte number
        if number < pow(2, 16) and suffix < pow(2, 32):
            rtd = bytes([0, 0]) + pack('!H', number) + pack('!L', suffix)
        # Type 2: 4-byte ASN + 2-byte number
        elif number < pow(2, 32) and suffix < pow(2, 16):
            rtd = bytes([0, 2]) + pack('!L', number) + pack('!H', suffix)
        else:
            raise ValueError(
                f"'{value}' is not a valid route-distinguisher\n  ASN and suffix out of range for RD formats"
            )

        return RouteDistinguisher(rtd)

    def to_schema(self) -> dict[str, Any]:
        return {
            'type': 'string',
            'pattern': r'^(\d+:\d+|\d+\.\d+\.\d+\.\d+:\d+)$',
            'examples': ['65000:100', '192.0.2.1:100', '4200000000:100'],
        }

    def describe(self) -> str:
        return 'route-distinguisher (ASN:nn or IP:nn)'


@dataclass
class RouteTargetValidator(Validator['ExtendedCommunity']):
    """Validates Route Target extended community values.

    Supports three formats:
    - target:ASN:nn (2-byte AS, e.g., "target:65000:100" or "65000:100")
    - target:IP:nn (IPv4 address, e.g., "target:192.0.2.1:100" or "192.0.2.1:100")
    - target:ASN:nn (4-byte AS, e.g., "target:4200000000:100" or "4200000000:100")

    The "target:" prefix is optional - if omitted, it's assumed.
    """

    name: str = 'route-target'

    def _parse(self, value: str) -> 'ExtendedCommunity':
        from struct import pack

        from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

        # Strip optional 'target:' prefix
        if value.startswith('target:'):
            value = value[7:]

        parts = value.split(':')
        if len(parts) != 2:
            raise ValueError(
                f"'{value}' is not a valid route-target\n"
                f"  Expected format: ASN:nn or IP:nn (e.g., '65000:100' or '192.0.2.1:100')\n"
                f"  Optional 'target:' prefix is supported"
            )

        prefix, suffix_str = parts
        try:
            suffix = int(suffix_str)
        except ValueError:
            raise ValueError(f"'{value}' is not a valid route-target (suffix must be a number)") from None

        # IPv4:nn format (Type 1)
        if '.' in prefix:
            from exabgp.protocol.ip import IPv4

            if suffix >= pow(2, 16):
                raise ValueError(f'Suffix {suffix} too large for IPv4 route-target (max 65535)')
            try:
                community_bytes = pack('!2s4sH', bytes([0x01, 0x02]), IPv4.pton(prefix), suffix)
                return ExtendedCommunity.unpack_attribute(community_bytes, None)
            except (ValueError, OSError):
                raise ValueError(f"'{value}' is not a valid route-target (invalid IPv4 address)") from None

        # ASN:nn format (Type 0 or Type 2)
        try:
            asn = int(prefix)
        except ValueError:
            raise ValueError(f"'{value}' is not a valid route-target (prefix must be ASN or IPv4)") from None

        # Type 0: 2-byte ASN + 4-byte number
        if asn < pow(2, 16) and suffix < pow(2, 32):
            community_bytes = pack('!2sHL', bytes([0x00, 0x02]), asn, suffix)
        # Type 2: 4-byte ASN + 2-byte number
        elif asn < pow(2, 32) and suffix < pow(2, 16):
            community_bytes = pack('!2sLH', bytes([0x02, 0x02]), asn, suffix)
        else:
            raise ValueError(
                f"'{value}' is not a valid route-target\n  ASN and suffix out of range for route-target formats"
            )

        return ExtendedCommunity.unpack_attribute(community_bytes, None)

    def to_schema(self) -> dict[str, Any]:
        return {
            'type': 'string',
            'pattern': r'^(target:)?(\d+:\d+|\d+\.\d+\.\d+\.\d+:\d+)$',
            'examples': ['target:65000:100', '65000:100', '192.0.2.1:100', 'target:4200000000:100'],
        }

    def describe(self) -> str:
        return 'route-target (ASN:nn or IP:nn)'


@dataclass
class OriginValidator(Validator['Origin']):
    """Validates BGP origin attribute (igp, egp, incomplete)."""

    name: str = 'origin'

    def _parse(self, value: str) -> 'Origin':
        from exabgp.bgp.message.update.attribute import Origin

        lower = value.lower()
        if lower == 'igp':
            return Origin.from_int(Origin.IGP)
        if lower == 'egp':
            return Origin.from_int(Origin.EGP)
        if lower == 'incomplete':
            return Origin.from_int(Origin.INCOMPLETE)
        raise ValueError(f"'{value}' is not a valid origin\n  Valid options: igp, egp, incomplete")

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'string', 'enum': ['igp', 'egp', 'incomplete']}

    def describe(self) -> str:
        return 'origin (igp, egp, incomplete)'


@dataclass
class MEDValidator(Validator['MED']):
    """Validates Multi-Exit Discriminator (MED) values."""

    name: str = 'med'

    def _parse(self, value: str) -> 'MED':
        from exabgp.bgp.message.update.attribute import MED

        if not value.isdigit():
            raise ValueError(f"'{value}' is not a valid MED\n  Must be a non-negative integer")
        num = int(value)
        if num > 4294967295:
            raise ValueError(f'{num} exceeds maximum MED value (4294967295)')
        return MED.from_int(num)

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'integer', 'minimum': 0, 'maximum': 4294967295}

    def describe(self) -> str:
        return 'MED (0-4294967295)'


@dataclass
class LocalPrefValidator(Validator['LocalPreference']):
    """Validates local preference values."""

    name: str = 'local-pref'

    def _parse(self, value: str) -> 'LocalPreference':
        from exabgp.bgp.message.update.attribute import LocalPreference

        if not value.isdigit():
            raise ValueError(f"'{value}' is not a valid local-preference\n  Must be a non-negative integer")
        num = int(value)
        if num > 4294967295:
            raise ValueError(f'{num} exceeds maximum local-preference value (4294967295)')
        return LocalPreference.from_int(num)

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'integer', 'minimum': 0, 'maximum': 4294967295}

    def describe(self) -> str:
        return 'local-preference (0-4294967295)'


@dataclass
class NextHopValidator(Validator[tuple['IP | IPSelf', 'NextHop | NextHopSelf']]):
    """Validates next-hop (IP address or 'self')."""

    name: str = 'next-hop'

    def _parse(self, value: str) -> tuple['IP | IPSelf', 'NextHop | NextHopSelf']:
        from exabgp.bgp.message.update.attribute import NextHop, NextHopSelf
        from exabgp.protocol.family import AFI
        from exabgp.protocol.ip import IP, IPSelf

        if value.lower() == 'self':
            # Default to IPv4 when AFI context not available
            return IPSelf(AFI.ipv4), NextHopSelf(AFI.ipv4)

        try:
            ip_obj = IP.from_string(value)
            return ip_obj, NextHop.from_string(ip_obj.top())
        except (OSError, IndexError, ValueError):
            raise ValueError(
                f"'{value}' is not a valid next-hop\n  Format: <ip> or 'self' (e.g., 192.0.2.1 or self)"
            ) from None

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'string', 'format': 'next-hop'}

    def describe(self) -> str:
        return "next-hop (IP or 'self')"


# =============================================================================
# Legacy Parser Wrapper
# =============================================================================


@dataclass
class LegacyParserValidator(Validator[Any]):
    """Wraps an existing tokeniser-based parser function.

    Use this to integrate complex parsers (community, as-path, etc.)
    that require multi-token parsing or have complex logic.

    Example:
        >>> from exabgp.configuration.static.parser import community
        >>> v = LegacyParserValidator(parser_func=community, name='community')

    For parsers that need AFI (like next_hop):
        >>> v = LegacyParserValidator(parser_func=next_hop, name='next-hop', accepts_afi=True)
    """

    parser_func: Callable[..., Any] | None = None
    name: str = 'legacy'
    accepts_default: bool = False
    default_value: Any = None
    accepts_afi: bool = False  # If True, validate_with_afi passes AFI to parser

    def _parse(self, value: str) -> Any:
        """Not used directly - legacy parsers work with tokeniser."""
        raise NotImplementedError('LegacyParserValidator uses validate() directly')

    def validate(self, tokeniser: 'Tokeniser') -> Any:
        """Call the wrapped parser function with tokeniser."""
        if self.parser_func is None:
            raise ValueError('No parser function configured')
        if self.accepts_default and self.default_value is not None:
            return self.parser_func(tokeniser, self.default_value)
        return self.parser_func(tokeniser)

    def validate_with_afi(self, tokeniser: 'Tokeniser', afi: Any) -> Any:
        """Call the wrapped parser function with tokeniser and AFI.

        Used for parsers like next_hop that need AFI context for proper handling
        (e.g., converting IPv4 to IPv4-mapped IPv6 for IPv6 AFI).
        """
        if self.parser_func is None:
            raise ValueError('No parser function configured')
        if self.accepts_afi:
            return self.parser_func(tokeniser, afi)
        return self.parser_func(tokeniser)

    def validate_string(self, value: str) -> Any:
        """Create a simple tokeniser for single-value validation."""
        from exabgp.configuration.core.parser import Tokeniser

        tokeniser = Tokeniser()
        tokeniser.replenish([value])
        return self.validate(tokeniser)

    def with_default(self, default: Any) -> 'LegacyParserValidator':
        """Return validator that passes default to parser."""
        new = deepcopy(self)
        new.accepts_default = True
        new.default_value = default
        return new

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'string', 'format': self.name}


# =============================================================================
# Extended Validators for Complex Objects
# =============================================================================


@dataclass
class TupleValidator(Validator[tuple[Any, ...]]):
    """Converts SAFI strings to (AFI, SAFI) or (AFI, SAFI, AFI) tuples.

    Used by TupleLeaf for family/nexthop sections.

    Example:
        >>> v = TupleValidator(
        ...     conversion_map={'ipv4': {'unicast': (AFI.ipv4, SAFI.unicast)}},
        ...     afi_context='ipv4',
        ... )
        >>> v.validate_string('unicast')
        (AFI.ipv4, SAFI.unicast)
    """

    name: str = 'tuple'
    conversion_map: dict[str, dict[str, tuple[Any, ...]]] = field(default_factory=dict)
    afi_context: str = ''

    def _parse(self, value: str) -> tuple[Any, ...]:
        if not self.conversion_map:
            raise ValueError('No conversion map configured')

        safi_map = self.conversion_map.get(self.afi_context)
        if not safi_map:
            raise ValueError(f"Unknown AFI context: '{self.afi_context}'")

        result = safi_map.get(value.lower())
        if not result:
            valid = ', '.join(sorted(safi_map.keys()))
            raise ValueError(f"'{value}' is not valid for {self.afi_context}\n  Valid options: {valid}")

        return result

    def with_context(self, afi: str, conversion_map: dict[str, dict[str, tuple[Any, ...]]]) -> 'TupleValidator':
        """Return validator configured for specific AFI context."""
        new = deepcopy(self)
        new.afi_context = afi
        new.conversion_map = conversion_map
        return new

    def to_schema(self) -> dict[str, Any]:
        if self.afi_context and self.conversion_map:
            safi_map = self.conversion_map.get(self.afi_context, {})
            return {'type': 'string', 'enum': list(safi_map.keys())}
        return {'type': 'string'}


@dataclass
class NextHopTupleValidator(Validator[tuple[Any, Any, Any]]):
    """Validates nexthop configuration returning (AFI, SAFI, NextHop-AFI) tuples.

    Parses two tokens: SAFI then NextHop-AFI, and returns a 3-tuple.
    Used for nexthop section where alternate next-hop AFI is specified.

    Example:
        >>> v = NextHopTupleValidator(
        ...     afi='ipv4',
        ...     valid_safis=['unicast', 'multicast'],
        ...     valid_nhafis=['ipv6'],
        ... )
        >>> v.validate(tokeniser)  # tokens: "unicast ipv6"
        (AFI.ipv4, SAFI.unicast, AFI.ipv6)
    """

    name: str = 'nexthop-tuple'
    afi: str = ''
    valid_safis: list[str] = field(default_factory=list)
    valid_nhafis: list[str] = field(default_factory=list)

    def _parse(self, value: str) -> tuple[Any, Any, Any]:
        """Not used directly - uses validate() with tokeniser for 2-token parsing."""
        raise NotImplementedError('NextHopTupleValidator uses validate() directly')

    def validate(self, tokeniser: 'Tokeniser') -> tuple[Any, Any, Any]:
        """Parse SAFI and NextHop-AFI tokens, return 3-tuple."""
        from exabgp.protocol.family import AFI as AFIEnum
        from exabgp.protocol.family import SAFI as SAFIEnum

        safi = tokeniser().lower()
        if safi not in self.valid_safis:
            valid = ', '.join(self.valid_safis)
            raise ValueError(f"'{safi}' is not a valid SAFI for {self.afi}\n  Valid options: {valid}")

        nhafi = tokeniser().lower()
        if nhafi not in self.valid_nhafis:
            valid = ', '.join(self.valid_nhafis)
            raise ValueError(f"'{nhafi}' is not a valid next-hop AFI\n  Valid options: {valid}")

        return (AFIEnum.from_string(self.afi), SAFIEnum.from_string(safi), AFIEnum.from_string(nhafi))

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'string', 'format': 'nexthop-tuple'}


@dataclass
class StatefulValidator(Validator[T]):
    """Wraps another validator with deduplication tracking.

    Used by ParseFamily and ParseNextHop to prevent duplicate AFI/SAFI entries.
    The `seen` set is a reference to the section's _seen attribute, allowing
    state to persist across multiple parse calls.

    Example:
        >>> seen = set()
        >>> inner = TupleValidator(...)
        >>> v = StatefulValidator(inner=inner, seen=seen)
        >>> v.validate(tokeniser)  # First call succeeds
        >>> v.validate(tokeniser)  # Second call with same value raises ValueError
    """

    name: str = 'stateful'
    inner: Validator[T] | None = None
    seen: set[T] = field(default_factory=set)

    def _parse(self, value: str) -> T:
        """Not used directly - delegates to inner validator."""
        if self.inner is None:
            raise ValueError('No inner validator configured')
        return self.inner._parse(value)

    def validate(self, tokeniser: 'Tokeniser') -> T:
        """Validate and check for duplicates."""
        if self.inner is None:
            raise ValueError('No inner validator configured')

        result = self.inner.validate(tokeniser)

        if result in self.seen:
            raise ValueError(f'Duplicate entry: {result}')

        self.seen.add(result)
        return result

    def validate_string(self, value: str) -> T:
        """Validate string and check for duplicates."""
        if self.inner is None:
            raise ValueError('No inner validator configured')

        result = self.inner.validate_string(value)

        if result in self.seen:
            raise ValueError(f'Duplicate entry: {result}')

        self.seen.add(result)
        return result

    def to_schema(self) -> dict[str, Any]:
        if self.inner:
            return self.inner.to_schema()
        return {'type': 'string'}


@dataclass
class CompositeValidator(Validator[Any]):
    """Parses key-value pairs and constructs objects.

    Used by CompositeLeaf for operational messages that parse patterns like:
        asm afi 1 safi 1 advisory "message"

    Example:
        >>> v = CompositeValidator(
        ...     parameters=['afi', 'safi', 'advisory'],
        ...     factory=Advisory.ASM,
        ...     converters={'afi': AFI.value, 'safi': SAFI.value},
        ... )
    """

    name: str = 'composite'
    parameters: list[str] = field(default_factory=list)
    factory: Callable[..., Any] | None = None
    converters: dict[str, Callable[[str], Any]] = field(default_factory=dict)

    def _parse(self, value: str) -> Any:
        """Not used directly - uses validate() with tokeniser."""
        raise NotImplementedError('CompositeValidator uses validate() directly')

    def validate(self, tokeniser: 'Tokeniser') -> Any:
        """Parse key-value pairs and construct object."""
        if not self.parameters:
            raise ValueError('No parameters configured')

        data: dict[str, Any] = {}
        for param in self.parameters:
            key = tokeniser()
            if key.lower() != param:
                raise ValueError(f"Expected '{param}', got '{key}'")

            value = tokeniser()
            converter = self.converters.get(param)
            if converter:
                try:
                    data[param] = converter(value)
                except (ValueError, KeyError) as e:
                    raise ValueError(f'Invalid value for {param}: {value}') from e
            else:
                data[param] = value

        if self.factory:
            return self.factory(**data)
        return data

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'object', 'format': self.name}


@dataclass
class RouteBuilderValidator(Validator[list[Any]]):
    """Builds Change objects from route syntax.

    Used by RouteBuilder to replace custom ip() and vpls() functions.
    Implements the token loop that builds NLRI + Attributes from sub-commands.

    This validator is typically created by the Section when processing
    a RouteBuilder schema, configured with the AFI/SAFI context.

    Supports two modes:
    1. Legacy mode (nlri_factory only): Creates NLRI immediately, mutates via assign()
    2. Settings mode (nlri_class + settings_class): Collects values into Settings,
       creates immutable NLRI via from_settings() at end

    For prefix-based routes (IP), prefix_parser parses the prefix and nlri_factory
    is called with (afi, safi, action_type).

    For non-prefix routes (VPLS), prefix_parser is None and nlri_factory is called
    with no arguments - it should return a pre-constructed NLRI with defaults.
    """

    name: str = 'route-builder'
    schema: Any = None  # RouteBuilder instance
    afi: Any = None  # AFI enum
    safi: Any = None  # SAFI enum
    action_type: Any = None  # Action.ANNOUNCE or Action.WITHDRAW

    def _parse(self, value: str) -> list[Any]:
        """Not used directly - uses validate() with tokeniser."""
        raise NotImplementedError('RouteBuilderValidator uses validate() directly')

    def validate(self, tokeniser: 'Tokeniser') -> list[Any]:
        """Build Route objects from route syntax."""
        if self.schema is None:
            raise ValueError('No schema configured')

        # Settings mode is required - NLRI are immutable
        if self.schema.settings_class is None or self.schema.nlri_class is None:
            raise ValueError(
                f'Schema must define settings_class and nlri_class - NLRI are immutable. Schema: {self.schema}'
            )
        return self._validate_with_settings(tokeniser)

    def _validate_with_settings(self, tokeniser: 'Tokeniser') -> list[Any]:
        """Build Route using Settings pattern (deferred NLRI construction).

        Creates a Settings object, collects values during parsing, then
        creates immutable NLRI via from_settings() at the end.
        """
        from exabgp.bgp.message.update.attribute import AttributeCollection
        from exabgp.bgp.message.update.nlri.cidr import CIDR
        from exabgp.configuration.schema import Leaf, LeafList
        from exabgp.rib.route import Route

        # Create settings instance
        settings = self.schema.settings_class()
        settings.action = self.action_type
        settings.afi = self.afi
        settings.safi = self.safi
        attributes = AttributeCollection()

        # Parse prefix if present (for INET-family routes)
        if self.schema.prefix_parser:
            ipmask = self.schema.prefix_parser(tokeniser)
            settings.cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)
            settings.afi = self.afi
            settings.safi = self.safi

        # Process sub-commands from schema - collect into settings
        while True:
            command = tokeniser()
            if not command:
                break

            child = self.schema.children.get(command)
            if child is None:
                valid = ', '.join(sorted(self.schema.children.keys()))
                raise ValueError(f"Unknown command '{command}'\n  Valid options: {valid}")

            # Get validator and parse value
            if isinstance(child, (Leaf, LeafList)):
                validator = child.get_validator()
                if validator is None:
                    raise ValueError(f"No validator for '{command}'")
                value = validator.validate(tokeniser)
                action = child.action

                # Apply action - collect into settings or attributes
                self._apply_settings_action(settings, attributes, command, action, value)

        # Create immutable NLRI from validated settings
        nlri = self.schema.nlri_class.from_settings(settings)

        return [Route(nlri, attributes, self.action_type, nexthop=settings.nexthop)]

    def _apply_settings_action(self, settings: Any, attributes: Any, command: str, action: str, value: Any) -> None:
        """Apply parsed value to Settings object based on action."""
        if action == 'attribute-add':
            attributes.add(value)
        elif action == 'nexthop-and-attribute':
            ip, attribute = value
            if ip:
                settings.nexthop = ip
            if attribute:
                attributes.add(attribute)
        elif action == 'nlri-set':
            field_name = self.schema.assign.get(command, command)
            settings.set(field_name, value)
        elif action == 'nlri-add':
            # For FlowSpec: value is a list/tuple/generator of components to add
            # Use hasattr to check for __iter__ to handle generators
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
        elif action == 'nlri-nexthop':
            settings.nexthop = value
        elif action == 'nop':
            pass  # Intentionally do nothing (e.g., FlowSpec 'accept')
        elif action == 'set-command':
            # Store on settings for later processing
            setattr(settings, command.replace('-', '_'), value)
        else:
            raise ValueError(f"Unknown action '{action}' for command '{command}'")

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'array', 'items': {'type': 'object'}}


@dataclass
class TypeSelectorValidator(Validator[list[Any]]):
    """Builds Route objects from type-selector route syntax.

    Used by TypeSelectorBuilder for MUP and MVPN routes where the first token
    selects the NLRI type/factory, which parses NLRI-specific fields,
    then common attributes follow.

    Example token stream:
        mup-isd <nlri fields parsed by factory> next-hop 1.2.3.4 extended-community ...

    The factory function creates the NLRI and parses its specific fields.
    Then this validator processes remaining tokens as attributes.

    Note: Unlike RouteBuilderValidator, TypeSelector uses factory mode where
    the NLRI is fully constructed by the factory. Post-factory attributes
    (next-hop, extended-community) are then applied. This pattern does not
    require deferred construction since factories create complete NLRIs.
    """

    name: str = 'type-selector'
    schema: Any = None  # TypeSelectorBuilder instance
    afi: Any = None  # AFI enum
    safi: Any = None  # SAFI enum
    action_type: Any = None  # Action.ANNOUNCE or Action.WITHDRAW

    def _parse(self, value: str) -> list[Any]:
        """Not used directly - uses validate() with tokeniser."""
        raise NotImplementedError('TypeSelectorValidator uses validate() directly')

    def validate(self, tokeniser: 'Tokeniser') -> list[Any]:
        """Build Route objects from type-selector route syntax."""
        if self.schema is None:
            raise ValueError('No schema configured')

        from exabgp.bgp.message.update.attribute import AttributeCollection
        from exabgp.rib.route import Route

        # First token selects the type/factory
        route_type = tokeniser()
        if not route_type:
            valid = ', '.join(sorted(self.schema.type_factories.keys()))
            raise ValueError(f'Missing route type. Valid options: {valid}')

        factory = self.schema.type_factories.get(route_type)
        if factory is None:
            valid = ', '.join(sorted(self.schema.type_factories.keys()))
            raise ValueError(f"Unknown route type '{route_type}'\n  Valid options: {valid}")

        # Call factory to create NLRI (factory parses NLRI-specific fields)
        if self.schema.factory_needs_action:
            nlri = factory(tokeniser, self.afi, self.action_type)
        else:
            nlri = factory(tokeniser, self.afi)

        # Set action on Route (nlri.action set for backward compat, will be removed)
        nlri.action = self.action_type

        # Create Route with explicit nexthop from nlri; will be updated via with_nexthop() if parsed
        route = Route(nlri, AttributeCollection(), self.action_type, nexthop=nlri.nexthop)

        # Process remaining tokens as attributes
        from exabgp.configuration.schema import Leaf, LeafList

        while True:
            command = tokeniser()
            if not command:
                break

            child = self.schema.children.get(command)
            if child is None:
                valid = ', '.join(sorted(self.schema.children.keys()))
                raise ValueError(f"Unknown command '{command}'\n  Valid options: {valid}")

            # Get validator and parse value
            if isinstance(child, (Leaf, LeafList)):
                validator = child.get_validator()
                if validator is None:
                    raise ValueError(f"No validator for '{command}'")

                action = child.action

                # For nexthop-and-attribute, use validate_with_afi if validator wants AFI
                used_afi = False
                accepts_afi = getattr(validator, 'accepts_afi', False)
                if action == 'nexthop-and-attribute' and accepts_afi:
                    value = validator.validate_with_afi(tokeniser, self.afi)
                    used_afi = True
                else:
                    value = validator.validate(tokeniser)

                # Apply action
                route = self._apply_action(route, command, action, value, used_afi)

        return [route]

    def _apply_action(self, route: Route, command: str, action: str, value: Any, used_afi: bool = False) -> Route:
        """Apply parsed value to Route object based on action.

        Note: 'nlri-set' action is not supported for TypeSelector - factories
        should create complete NLRIs. Use Settings pattern with RouteBuilder
        for types that need deferred NLRI construction.

        Returns the (possibly modified) Route.
        """
        from exabgp.protocol.family import AFI

        if action == 'attribute-add':
            route.attributes.add(value)
        elif action == 'nexthop-and-attribute':
            ip, attribute = value
            if ip:
                route = route.with_nexthop(ip)
            # Only skip NextHop attribute when:
            # 1. The validator used AFI (accepts_afi=True), AND
            # 2. The AFI is IPv6 (next-hop goes in MP_REACH_NLRI only)
            # For validators that don't use AFI (e.g., MVPN), always add the attribute
            if attribute:
                if used_afi and self.afi == AFI.ipv6:
                    pass  # Skip NextHop attr for AFI-aware validators with IPv6
                else:
                    route.attributes.add(attribute)
        elif action == 'nop':
            pass
        else:
            raise ValueError(f"Unknown action '{action}' for command '{command}'")
        return route

    def to_schema(self) -> dict[str, Any]:
        return {'type': 'array', 'items': {'type': 'object'}}


# =============================================================================
# ValueType → Validator Registry
# =============================================================================


def _get_community_parser() -> Callable[..., Any]:
    from exabgp.configuration.static.parser import community

    return community


def _get_large_community_parser() -> Callable[..., Any]:
    from exabgp.configuration.static.parser import large_community

    return large_community


def _get_extended_community_parser() -> Callable[..., Any]:
    from exabgp.configuration.static.parser import extended_community

    return extended_community


def _get_as_path_parser() -> Callable[..., Any]:
    from exabgp.configuration.static.parser import as_path

    return as_path


def _get_aggregator_parser() -> Callable[..., Any]:
    from exabgp.configuration.static.parser import aggregator

    return aggregator


def _build_validator_factories() -> dict['ValueType', Callable[[], Validator[Any]]]:
    """Build the validator factory registry.

    This is called lazily to avoid import issues.
    """
    from exabgp.configuration.schema import ValueType

    return {
        # Basic types
        ValueType.STRING: lambda: StringValidator(),
        ValueType.INTEGER: lambda: IntegerValidator(),
        ValueType.BOOLEAN: lambda: BooleanValidator(),
        ValueType.ENUMERATION: lambda: EnumerationValidator(),
        ValueType.HEX_STRING: lambda: StringValidator(pattern=r'^0x[0-9a-fA-F]+$'),
        # Network types
        ValueType.PORT: lambda: PortValidator(),
        ValueType.IP_ADDRESS: lambda: IPAddressValidator(),
        ValueType.IP_PREFIX: lambda: IPPrefixValidator(),
        ValueType.IP_RANGE: lambda: IPRangeValidator(),
        ValueType.ASN: lambda: ASNValidator(),
        # BGP-specific types with dedicated validators
        ValueType.ORIGIN: lambda: OriginValidator(),
        ValueType.MED: lambda: MEDValidator(),
        ValueType.LOCAL_PREF: lambda: LocalPrefValidator(),
        ValueType.NEXT_HOP: lambda: NextHopValidator(),
        # Types with range constraints
        ValueType.LABEL: lambda: IntegerValidator().in_range(0, 1048575),
        ValueType.BANDWIDTH: lambda: IntegerValidator().positive(),
        # Complex types using legacy parser wrapper
        ValueType.COMMUNITY: lambda: LegacyParserValidator(parser_func=_get_community_parser(), name='community'),
        ValueType.LARGE_COMMUNITY: lambda: LegacyParserValidator(
            parser_func=_get_large_community_parser(), name='large-community'
        ),
        ValueType.EXTENDED_COMMUNITY: lambda: LegacyParserValidator(
            parser_func=_get_extended_community_parser(), name='extended-community'
        ),
        ValueType.AS_PATH: lambda: LegacyParserValidator(parser_func=_get_as_path_parser(), name='as-path'),
        ValueType.AGGREGATOR: lambda: LegacyParserValidator(parser_func=_get_aggregator_parser(), name='aggregator'),
        # Route Distinguisher and Route Target with dedicated validators
        ValueType.RD: lambda: RouteDistinguisherValidator(),
        ValueType.RT: lambda: RouteTargetValidator(),
        # Atomic-aggregate is a presence flag (no value needed)
        ValueType.ATOMIC_AGGREGATE: lambda: FlagValidator(),
    }


# Lazy-initialized registry
_VALIDATOR_FACTORIES: dict['ValueType', Callable[[], Validator[Any]]] | None = None


def get_validator(value_type: 'ValueType') -> Validator[Any] | None:
    """Get a fresh validator instance for a ValueType.

    Args:
        value_type: The ValueType enum to get validator for

    Returns:
        New Validator instance, or None if no validator registered
    """
    global _VALIDATOR_FACTORIES
    if _VALIDATOR_FACTORIES is None:
        _VALIDATOR_FACTORIES = _build_validator_factories()

    factory = _VALIDATOR_FACTORIES.get(value_type)
    if factory is None:
        return None
    return factory()
