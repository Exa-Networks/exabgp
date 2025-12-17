"""schema_bridge.py

Bridge between configuration schema and CLI auto-complete.

Provides schema-driven value validation, syntax help, and completion suggestions
for the CLI REPL. Uses validators from configuration schema (validator.py) but
operates independently from config file parsing.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from exabgp.cli.completer import CompletionItem
    from exabgp.configuration.validator import Validator

from exabgp.configuration.schema import ValueType, VALUE_TYPE_HINTS
from exabgp.configuration.validator import get_validator


class ValidationState(Enum):
    """State of a partial value during validation"""

    VALID = 'valid'  # Complete and valid
    IN_PROGRESS = 'in_progress'  # Incomplete but could be valid
    INVALID = 'invalid'  # Invalid and cannot be fixed
    UNKNOWN = 'unknown'  # No validator available


@dataclass
class ValidationResult:
    """Result of validating a (possibly partial) value"""

    state: ValidationState
    message: str  # Empty for VALID, error description for INVALID
    suggestion: str | None = None  # Suggested correction if available


class ValueTypeCompletionEngine:
    """Schema-driven completion and validation for CLI values.

    Uses validators from configuration schema to provide:
    - Type-aware value validation (IP addresses, AS numbers, etc.)
    - Syntax help generation (e.g., '<ip>', 'IGP|EGP|INCOMPLETE')
    - Partial input validation (e.g., '192.168' is incomplete but valid prefix)
    - Completion suggestions for enumeration types

    Example:
        >>> engine = ValueTypeCompletionEngine()
        >>> result = engine.validate_value(ValueType.IP_ADDRESS, '192.168.1.1')
        >>> result.state
        ValidationState.VALID

        >>> result = engine.validate_value(ValueType.IP_ADDRESS, '999.999.999.999')
        >>> result.state
        ValidationState.INVALID
        >>> result.message
        'Invalid IP address: octet 999 out of range'

        >>> help_text = engine.get_syntax_help(ValueType.ORIGIN)
        >>> help_text
        'IGP|EGP|INCOMPLETE'
    """

    def __init__(self):
        """Initialize completion engine."""
        # Cache validators to avoid repeated creation
        self._validator_cache: dict[ValueType, Validator[Any] | None] = {}
        # Cache validation results (LRU with max 100 entries)
        self._validation_cache: dict[tuple[ValueType, str, bool], ValidationResult] = {}
        self._validation_cache_max_size = 100

    def _get_validator(self, value_type: ValueType) -> Validator[Any] | None:
        """Get validator for a value type (cached).

        Args:
            value_type: Type of value to validate

        Returns:
            Validator instance or None if unavailable
        """
        if value_type not in self._validator_cache:
            self._validator_cache[value_type] = get_validator(value_type)
        return self._validator_cache[value_type]

    def validate_value(self, value_type: ValueType, value: str, allow_partial: bool = False) -> ValidationResult:
        """Validate a value against its type.

        Args:
            value_type: Expected type of value
            value: String value to validate
            allow_partial: If True, accept incomplete but valid prefixes
                          (e.g., '192.168' for IP_ADDRESS)

        Returns:
            ValidationResult with state and error message

        Example:
            >>> validate_value(ValueType.PORT, '80')
            ValidationResult(VALID, '')

            >>> validate_value(ValueType.PORT, '99999')
            ValidationResult(INVALID, 'Port 99999 exceeds maximum 65535')

            >>> validate_value(ValueType.IP_ADDRESS, '192.168', allow_partial=True)
            ValidationResult(IN_PROGRESS, '')
        """
        # Check cache first
        cache_key = (value_type, value, allow_partial)
        if cache_key in self._validation_cache:
            return self._validation_cache[cache_key]

        validator = self._get_validator(value_type)

        if validator is None:
            result = ValidationResult(state=ValidationState.UNKNOWN, message='No validator available for this type')
            self._cache_validation_result(cache_key, result)
            return result

        # Try to validate
        try:
            validator.validate_string(value)
            result = ValidationResult(state=ValidationState.VALID, message='')
            self._cache_validation_result(cache_key, result)
            return result
        except (ValueError, TypeError) as e:
            error_msg = str(e)

            # Check if partial input might be valid
            if allow_partial and self._is_valid_prefix(value_type, value):
                result = ValidationResult(state=ValidationState.IN_PROGRESS, message='')
                self._cache_validation_result(cache_key, result)
                return result

            result = ValidationResult(state=ValidationState.INVALID, message=error_msg)
            self._cache_validation_result(cache_key, result)
            return result

    def _cache_validation_result(self, key: tuple[ValueType, str, bool], result: ValidationResult) -> None:
        """Cache a validation result with simple LRU eviction.

        Args:
            key: Cache key (value_type, value, allow_partial)
            result: ValidationResult to cache
        """
        # Simple LRU: if cache full, remove oldest entry
        if len(self._validation_cache) >= self._validation_cache_max_size:
            # Remove first (oldest) entry
            first_key = next(iter(self._validation_cache))
            del self._validation_cache[first_key]

        self._validation_cache[key] = result

    def _is_valid_prefix(self, value_type: ValueType, partial: str) -> bool:
        """Check if partial input could become valid with more characters.

        Args:
            value_type: Type being validated
            partial: Incomplete value

        Returns:
            True if partial could become valid

        Example:
            >>> _is_valid_prefix(ValueType.IP_ADDRESS, '192.168')
            True  # Could become 192.168.1.1

            >>> _is_valid_prefix(ValueType.IP_ADDRESS, '999.999')
            False  # 999 is invalid octet, cannot be fixed
        """
        if not partial:
            return True

        # Type-specific prefix validation
        if value_type in (ValueType.IP_ADDRESS, ValueType.IP_PREFIX, ValueType.NEXT_HOP):
            # Check if it's a valid partial IP (no octet > 255)
            parts = partial.split('.')
            try:
                for part in parts:
                    if part and int(part) > 255:
                        return False
                return True
            except ValueError:
                return False

        elif value_type == ValueType.ASN:
            # Check if it's a valid partial AS number
            try:
                if partial and int(partial) > 4294967295:  # Max 32-bit AS
                    return False
                return True
            except ValueError:
                return False

        elif value_type == ValueType.PORT:
            # Check if it's a valid partial port
            try:
                if partial and int(partial) > 65535:
                    return False
                return True
            except ValueError:
                return False

        elif value_type == ValueType.ORIGIN:
            # Check if it's a valid prefix of IGP/EGP/INCOMPLETE
            choices = ['igp', 'egp', 'incomplete']
            partial_lower = partial.lower()
            return any(c.startswith(partial_lower) for c in choices)

        elif value_type == ValueType.ENUMERATION:
            # Would need choices from validator, default to accepting
            return True

        # Unknown type: be lenient
        return True

    def suggest_values(self, value_type: ValueType, partial: str) -> list[str]:
        """Suggest valid values based on partial input.

        Currently only works for enumeration types (e.g., ORIGIN).
        For open-ended types (IP, ASN), returns empty list.

        Args:
            value_type: Type of value
            partial: Partial input to complete

        Returns:
            List of completion suggestions

        Example:
            >>> suggest_values(ValueType.ORIGIN, 'ig')
            ['igp']

            >>> suggest_values(ValueType.ORIGIN, '')
            ['igp', 'egp', 'incomplete']
        """
        validator = self._get_validator(value_type)

        if validator is None:
            return []

        # Only enumeration types have fixed choices
        if value_type == ValueType.ORIGIN:
            choices = ['igp', 'egp', 'incomplete']
        elif value_type == ValueType.BOOLEAN:
            choices = ['true', 'false', 'enable', 'disable', 'yes', 'no']
        else:
            # For open-ended types, cannot suggest values
            return []

        # Filter by partial input
        if not partial:
            return choices

        partial_lower = partial.lower()
        return [c for c in choices if c.startswith(partial_lower)]

    def get_syntax_help(self, value_type: ValueType, include_description: bool = True) -> str:
        """Get syntax help for a value type.

        Args:
            value_type: Type to get help for
            include_description: If True, include validator description

        Returns:
            Syntax hint string

        Example:
            >>> get_syntax_help(ValueType.IP_ADDRESS)
            '<ip>'

            >>> get_syntax_help(ValueType.ORIGIN)
            'IGP|EGP|INCOMPLETE'

            >>> get_syntax_help(ValueType.IP_ADDRESS, include_description=True)
            '<ip> - IPv4 or IPv6 address'
        """
        # Try to get hint from VALUE_TYPE_HINTS
        hint = VALUE_TYPE_HINTS.get(value_type, '<value>')

        if not include_description:
            return hint

        # Try to get description from validator
        validator = self._get_validator(value_type)
        if validator is not None:
            description = validator.describe()
            if description and description != value_type.value:
                return f'{hint} - {description}'

        return hint

    def get_example_value(self, value_type: ValueType) -> str | None:
        """Get an example value for a type.

        Args:
            value_type: Type to get example for

        Returns:
            Example value string or None

        Example:
            >>> get_example_value(ValueType.IP_ADDRESS)
            '192.0.2.1'

            >>> get_example_value(ValueType.ASN)
            '65000'
        """
        # Common examples for each type
        examples = {
            ValueType.IP_ADDRESS: '192.0.2.1',
            ValueType.IP_PREFIX: '192.0.2.0/24',
            ValueType.IP_RANGE: '192.0.2.1-192.0.2.10',
            ValueType.ASN: '65000',
            ValueType.PORT: '179',
            ValueType.COMMUNITY: '65000:100',
            ValueType.EXTENDED_COMMUNITY: 'target:65000:100',
            ValueType.LARGE_COMMUNITY: '65000:100:200',
            ValueType.RD: '65000:100',
            ValueType.RT: '65000:100',
            ValueType.NEXT_HOP: '192.0.2.1',
            ValueType.ORIGIN: 'igp',
            ValueType.MED: '100',
            ValueType.LOCAL_PREF: '100',
            ValueType.LABEL: '100',
            ValueType.AGGREGATOR: '65000:192.0.2.1',
            ValueType.AS_PATH: '[65000 65001]',
            ValueType.BANDWIDTH: '1000000',
        }

        return examples.get(value_type)

    def create_completion_item(
        self, value: str, value_type: ValueType | None = None, description: str | None = None
    ) -> CompletionItem:
        """Create a CompletionItem with metadata.

        Args:
            value: Completion value
            value_type: Optional type for generating description
            description: Optional custom description

        Returns:
            CompletionItem with value, description, and type

        Example:
            >>> item = create_completion_item('192.0.2.1', ValueType.IP_ADDRESS)
            >>> item.value
            '192.0.2.1'
            >>> item.description
            '<ip> - IPv4 or IPv6 address'
        """
        from exabgp.cli.completer import CompletionItem

        if description is None and value_type is not None:
            description = self.get_syntax_help(value_type, include_description=True)

        return CompletionItem(value=value, description=description, item_type='value')


# Convenience functions
def validate_ip_address(value: str, allow_partial: bool = False) -> ValidationResult:
    """Validate an IP address.

    Args:
        value: IP address string
        allow_partial: Accept incomplete addresses

    Returns:
        ValidationResult
    """
    engine = ValueTypeCompletionEngine()
    return engine.validate_value(ValueType.IP_ADDRESS, value, allow_partial=allow_partial)


def validate_asn(value: str, allow_partial: bool = False) -> ValidationResult:
    """Validate an AS number.

    Args:
        value: ASN string
        allow_partial: Accept incomplete numbers

    Returns:
        ValidationResult
    """
    engine = ValueTypeCompletionEngine()
    return engine.validate_value(ValueType.ASN, value, allow_partial=allow_partial)


def get_syntax_hint(value_type: ValueType) -> str:
    """Get syntax hint for a value type.

    Args:
        value_type: Type to get hint for

    Returns:
        Syntax hint string (e.g., '<ip>', 'IGP|EGP|INCOMPLETE')
    """
    engine = ValueTypeCompletionEngine()
    return engine.get_syntax_help(value_type, include_description=False)
