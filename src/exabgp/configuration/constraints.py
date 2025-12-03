"""Configuration constraints.

Centralized location for all configuration value constraints (min/max, lengths, etc.).
This ensures consistency across the codebase and makes it easy to update limits.

Created on 2025-12-03.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass


# =============================================================================
# BGP Protocol Constraints (RFC 4271)
# =============================================================================

# Hold time constraints (seconds)
HOLD_TIME_MIN = 0  # 0 = disabled
HOLD_TIME_MAX = 65535

# BGP Identifier (router-id) constraints
BGP_IDENTIFIER_MIN = 0
BGP_IDENTIFIER_MAX = 4294967295

# AS Number constraints
ASN_MIN = 0
ASN_MAX = 4294967295  # 4-byte ASN (RFC 6793)
ASN_2BYTE_MAX = 65535  # Legacy 2-byte ASN

# Port constraints
PORT_MIN = 1
PORT_MAX = 65535

# TTL constraints
TTL_MIN = 1
TTL_MAX = 255

# MD5 password length (RFC 2385)
MD5_PASSWORD_MIN_LENGTH = 1
MD5_PASSWORD_MAX_LENGTH = 80

# =============================================================================
# BGP Message Constraints
# =============================================================================

# Multi-Exit Discriminator (MED)
MED_MIN = 0
MED_MAX = 4294967295

# Local Preference
LOCAL_PREF_MIN = 0
LOCAL_PREF_MAX = 4294967295

# MPLS Label
LABEL_MIN = 0
LABEL_MAX = 1048575  # 20-bit label

# Route Distinguisher
RD_MIN = 0
RD_MAX = 2**64 - 1

# =============================================================================
# Network Constraints
# =============================================================================

# IPv4 prefix length
IPV4_PREFIX_MIN = 0
IPV4_PREFIX_MAX = 32

# IPv6 prefix length
IPV6_PREFIX_MIN = 0
IPV6_PREFIX_MAX = 128

# Hostname/Domain constraints
HOSTNAME_MAX_LENGTH = 255
DOMAIN_NAME_MAX_LENGTH = 255

# =============================================================================
# ExaBGP-Specific Constraints
# =============================================================================

# Rate limiting (updates per second)
RATE_LIMIT_MIN = 0
RATE_LIMIT_MAX = 10000

# Connection attempts
CONNECTION_ATTEMPTS_MIN = 1
CONNECTION_ATTEMPTS_MAX = 100

# API buffer size
API_BUFFER_MIN = 1024
API_BUFFER_MAX = 1048576  # 1MB

# =============================================================================
# FlowSpec Constraints
# =============================================================================

# Packet length
PACKET_LENGTH_MIN = 0
PACKET_LENGTH_MAX = 65535

# DSCP value
DSCP_MIN = 0
DSCP_MAX = 63

# Fragment type
FRAGMENT_MIN = 0
FRAGMENT_MAX = 7

# TCP flags
TCP_FLAGS_MIN = 0
TCP_FLAGS_MAX = 63

# ICMP type/code
ICMP_TYPE_MIN = 0
ICMP_TYPE_MAX = 255
ICMP_CODE_MIN = 0
ICMP_CODE_MAX = 255

# =============================================================================
# Constraint Validators
# =============================================================================


@dataclass
class NumericConstraint:
    """Numeric constraint with min/max bounds.

    Example:
        hold_time = NumericConstraint(0, 65535, 'hold-time', 'seconds')
        hold_time.validate(180)  # Returns True
        hold_time.validate(70000)  # Returns False
    """

    min_val: int
    max_val: int
    field_name: str
    unit: str = ''

    def validate(self, value: int) -> bool:
        """Check if value is within bounds.

        Args:
            value: Value to validate

        Returns:
            True if valid, False otherwise
        """
        return self.min_val <= value <= self.max_val

    def error_message(self, value: int) -> str:
        """Generate error message for invalid value.

        Args:
            value: Invalid value

        Returns:
            Error message string
        """
        unit_str = f' {self.unit}' if self.unit else ''
        return (
            f'{self.field_name} value {value}{unit_str} is out of range '
            f'(must be {self.min_val}-{self.max_val}{unit_str})'
        )


@dataclass
class StringConstraint:
    """String constraint with length bounds.

    Example:
        hostname = StringConstraint(1, 255, 'hostname')
        hostname.validate('localhost')  # Returns True
        hostname.validate('')  # Returns False
    """

    min_length: int
    max_length: int
    field_name: str

    def validate(self, value: str) -> bool:
        """Check if string length is within bounds.

        Args:
            value: String to validate

        Returns:
            True if valid, False otherwise
        """
        return self.min_length <= len(value) <= self.max_length

    def error_message(self, value: str) -> str:
        """Generate error message for invalid string.

        Args:
            value: Invalid string

        Returns:
            Error message string
        """
        return (
            f'{self.field_name} length {len(value)} is out of range '
            f'(must be {self.min_length}-{self.max_length} characters)'
        )


# =============================================================================
# Common Constraint Instances
# =============================================================================

# Pre-defined constraint validators for common fields
CONSTRAINTS = {
    'hold-time': NumericConstraint(HOLD_TIME_MIN, HOLD_TIME_MAX, 'hold-time', 'seconds'),
    'local-as': NumericConstraint(ASN_MIN, ASN_MAX, 'local-as'),
    'peer-as': NumericConstraint(ASN_MIN, ASN_MAX, 'peer-as'),
    'port': NumericConstraint(PORT_MIN, PORT_MAX, 'port'),
    'ttl': NumericConstraint(TTL_MIN, TTL_MAX, 'ttl'),
    'med': NumericConstraint(MED_MIN, MED_MAX, 'med'),
    'local-preference': NumericConstraint(LOCAL_PREF_MIN, LOCAL_PREF_MAX, 'local-preference'),
    'label': NumericConstraint(LABEL_MIN, LABEL_MAX, 'label'),
    'rate-limit': NumericConstraint(RATE_LIMIT_MIN, RATE_LIMIT_MAX, 'rate-limit', 'updates/sec'),
    'hostname': StringConstraint(1, HOSTNAME_MAX_LENGTH, 'hostname'),
    'domain-name': StringConstraint(1, DOMAIN_NAME_MAX_LENGTH, 'domain-name'),
}
