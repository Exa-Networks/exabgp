"""BGP-LS (Link-State) attribute implementation (RFC 7752, RFC 9085).

BGP-LS distributes link-state and traffic engineering topology information
via BGP UPDATE messages. This module implements the BGP-LS attribute and
its TLV-encoded sub-attributes.

Key classes:
    LinkState: Main BGP-LS attribute (parses TLVs on demand)
    BaseLS: Base class for all BGP-LS TLV types
    FlagLS: Base class for flag-based TLVs (SR flags, etc.)
    GenericLSID: Fallback for unknown TLV types

TLV format: [type(2)][length(2)][value(variable)]

Copyright (c) 2016 Evelio Vila <eveliovila@gmail.com>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import binascii
import itertools
import json
from struct import unpack
from typing import TYPE_CHECKING, Any, Callable, Protocol

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.util import hexstring
from exabgp.util.types import Buffer


class LSClass(Protocol):
    """Protocol for BGP-LS classes that can unpack from bytes."""

    TLV: int
    MERGE: bool

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> BaseLS: ...


@Attribute.register()
class LinkState(Attribute):
    """BGP-LS attribute containing link-state TLVs (RFC 7752).

    Stores raw bytes and parses TLVs on demand via ls_attrs property.
    Uses registry pattern for TLV type dispatch.
    """

    ID = Attribute.CODE.BGP_LS
    FLAG = Attribute.Flag.OPTIONAL
    TLV = -1

    # Registered subclasses we know how to decode
    registered_lsids: dict[int, type] = dict()

    # what this implementation knows as LS attributes
    node_lsids: list[int] = []
    link_lsids: list[int] = []
    prefix_lsids: list[int] = []

    def __init__(self, packed: Buffer) -> None:
        """Initialize with raw attribute bytes (stores, parses on demand)."""
        self._packed = packed

    @property
    def ls_attrs(self) -> list[BaseLS]:
        """Parse TLVs on demand from stored packed bytes."""
        return self._parse_tlvs(self._packed)

    @classmethod
    def _parse_tlvs(cls, data: Buffer) -> list[BaseLS]:
        """Parse TLVs from raw bytes."""
        ls_attrs: list[BaseLS] = []

        while data:
            if len(data) < 4:
                raise Notify(3, 5, f'BGP-LS: TLV header too short, need 4 bytes, got {len(data)}')
            scode, length = unpack('!HH', data[:4])
            if len(data) < length + 4:
                raise Notify(
                    3, 5, f'BGP-LS: TLV data too short for type {scode}, need {length + 4} bytes, got {len(data)}'
                )
            payload = data[4 : length + 4]
            BaseLS.check_length(payload, length)

            data = data[length + 4 :]
            klass = cls.get_ls_class(scode)
            instance = klass.unpack_bgpls(payload)
            ls_attrs.append(instance)

        return ls_attrs

    @classmethod
    def register_lsid(
        cls, tlv: int, json_key: str, repr_name: str = '', *, alias_tlv: int | None = None
    ) -> Callable[[type[BaseLS]], type[BaseLS]]:
        """Register BGP-LS subclass by TLV code (different from Attribute.register).

        Args:
            tlv: TLV type code
            json_key: JSON output key name
            repr_name: Human-readable name (defaults to json_key if not provided)
            alias_tlv: Optional additional TLV code to register for same class
                      (e.g., LocalRouterId uses 1028 for IPv4, 1029 for IPv6)
        """

        def decorator(klass: type[BaseLS]) -> type[BaseLS]:
            # Set class attributes via decorator
            klass.TLV = tlv
            klass.JSON = json_key
            if repr_name:
                klass.REPR = repr_name
            # Register primary TLV
            if tlv in cls.registered_lsids:
                raise RuntimeError('only one class can be registered per BGP link state attribute type')
            cls.registered_lsids[tlv] = klass
            # Register alias TLV if provided (same class, different TLV code)
            if alias_tlv is not None:
                if alias_tlv in cls.registered_lsids:
                    raise RuntimeError('only one class can be registered per BGP link state attribute type')
                # Create alias class with different TLV but same JSON/REPR
                alias_klass = type(f'{klass.__name__}_{alias_tlv}', klass.__bases__, dict(klass.__dict__))
                setattr(alias_klass, 'TLV', alias_tlv)
                cls.registered_lsids[alias_tlv] = alias_klass
            return klass

        return decorator

    @classmethod
    def get_ls_class(cls, code: int) -> type[LSClass]:
        """Get BGP-LS subclass by TLV code (different from Attribute.klass)."""
        klass = cls.registered_lsids.get(code, None)
        if klass is not None:
            return klass
        unknown = type('GenericLSID_%d' % code, GenericLSID.__bases__, dict(GenericLSID.__dict__))
        setattr(unknown, 'TLV', code)
        cls.registered_lsids[code] = unknown
        return unknown

    @classmethod
    def is_lsid_registered(cls, lsid: int) -> bool:
        """Check if BGP-LS TLV code is registered (different from Attribute.registered)."""
        return lsid in cls.registered_lsids

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        """Store raw bytes - parsing happens on demand via ls_attrs property."""
        return cls(data)

    def json(self, compact: bool = False) -> str:
        """Output JSON for all TLVs. MERGE classes are grouped into arrays."""
        from collections import defaultdict

        # Group by TLV type
        by_type: dict[int, list[BaseLS]] = defaultdict(list)
        for attr in self.ls_attrs:
            by_type[attr.TLV].append(attr)

        parts = []
        for tlv, attrs in by_type.items():
            if getattr(attrs[0], 'MERGE', False):
                # MERGE classes: group into array
                key = attrs[0].JSON
                contents = [a.content for a in attrs]
                parts.append(f'"{key}": {json.dumps(contents)}')
            else:
                # Non-MERGE: output individually (may have duplicate keys)
                for attr in attrs:
                    parts.append(attr.json(compact))

        return '{ ' + ', '.join(parts) + ' }'

    def __str__(self) -> str:
        return ', '.join(str(d) for d in self.ls_attrs)


class BaseLS:
    """Base class for BGP-LS TLV types.

    Stores packed bytes and unpacks content on demand via properties.
    Subclasses define TLV code, JSON key, and content unpacking.

    Class attributes (set by decorator):
        TLV: TLV type code (2 bytes)
        JSON: Key name for JSON output
        REPR: Human-readable name
        LEN: Expected length (0 = variable)
        MERGE: If True, multiple TLVs of same type are merged into array
    """

    TLV: int = -1
    JSON: str = 'unset'
    REPR: str = 'repr name unset'
    LEN: int = 0
    MERGE: bool = False

    BGPLS_SUBTLV_HEADER_SIZE: int = 4  # Sub-TLV header is 4 bytes (Type 2 + Length 2)

    def __init__(self, packed: Buffer) -> None:
        """Initialize with packed wire-format bytes.

        Args:
            packed: Raw TLV payload bytes (after type/length header)
        """
        self._packed = packed

    @property
    def content(self) -> Any:
        """Unpack and return content from packed bytes.

        Subclasses should override this to provide proper unpacking.
        Default implementation returns raw bytes.
        """
        return self._packed

    def json(self, compact: bool = False) -> str:
        try:
            return f'"{self.JSON}": {json.dumps(self.content)}'
        except TypeError:
            # not a basic type
            return f'"{self.JSON}": "{self.content.decode("utf-8")}"'

    def __repr__(self) -> str:
        return '{}: {}'.format(self.REPR, self.content)

    @classmethod
    def check_length(cls, data: Buffer, length: int) -> None:
        if length and len(data) != length:
            raise Notify(3, 5, f'Unable to decode attribute, wrong size for {cls.REPR}')

    @classmethod
    def check(cls, data: Buffer) -> None:
        return cls.check_length(data, cls.LEN)

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> BaseLS:
        """Unpack TLV data into instance. Override in subclasses for custom unpacking."""
        return cls(data)

    def merge(self, other: BaseLS) -> None:
        if not self.MERGE:
            raise Notify(3, 5, f'Invalid merge, issue decoding {self.REPR}')
        self.content.extend(other.content)


class GenericLSID(BaseLS):
    """Fallback handler for unknown/unimplemented BGP-LS TLV types.

    Returns raw bytes as hex string. Dynamically sets JSON key from TLV code.
    """

    TLV: int = 0

    def __init__(self, packed: Buffer) -> None:
        """Initialize with packed wire-format bytes.

        Args:
            packed: Raw TLV payload bytes
        """
        self._packed = packed

    @property
    def content(self) -> str:
        """Return hex string of packed bytes."""
        return hexstring(self._packed)

    def __repr__(self) -> str:
        return 'Attribute with code [ {} ] not implemented'.format(self.TLV)

    def json(self, compact: bool = False) -> str:
        # Always output as array for backward compatibility
        # Compute JSON key inline to avoid overriding class attribute with property
        json_key = f'generic-lsid-{self.TLV}'
        return f'"{json_key}": ["{self.content}"]'

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> GenericLSID:
        return cls(data)


class FlagLS(BaseLS):
    """Base class for flag-based BGP-LS TLVs (SR flags, etc.).

    Subclasses define FLAGS as ordered list of flag names.
    'RSV' entries are reserved/padding bits.
    """

    # Subclasses define FLAGS as a list of flag names, e.g. ['R', 'N', 'P', 'E', 'V', 'L', 'RSV', 'RSV']
    FLAGS: list[str] = []

    def __init__(self, packed: Buffer) -> None:
        """Initialize with packed wire-format bytes.

        Args:
            packed: Raw TLV payload bytes containing flags
        """
        self._packed = packed

    @property
    def flags(self) -> dict[str, int]:
        """Unpack and return flags from packed bytes."""
        return self.unpack_flags(self._packed[0:1])

    def __repr__(self) -> str:
        return '{}: {}'.format(self.REPR, self.flags)

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.flags)}'

    @classmethod
    def unpack_flags(cls, data: Buffer) -> dict[str, int]:
        if not data:
            raise Notify(3, 5, 'BGP-LS: empty data for flag unpacking')
        pad = cls.FLAGS.count('RSV')
        repeat = len(cls.FLAGS) - pad
        hex_rep = int(binascii.b2a_hex(data), 16)
        bits = f'{hex_rep:08b}'
        valid_flags = [''.join(item) + '0' * pad for item in itertools.product('01', repeat=repeat)]
        valid_flags.append('0000')
        if bits in valid_flags:
            flags = dict(
                zip(
                    cls.FLAGS,
                    [
                        0,
                    ]
                    * len(cls.FLAGS),
                ),
            )
            flags.update(dict((k, int(v)) for k, v in zip(cls.FLAGS, bits)))
        else:
            raise Notify(3, 5, 'Invalid SR flags mask')
        return flags

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> FlagLS:
        cls.check(data)
        # We only support IS-IS for now.
        return cls(data)
