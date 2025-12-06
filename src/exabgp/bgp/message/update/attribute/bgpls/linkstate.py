"""Copyright (c) 2016 Evelio Vila <eveliovila@gmail.com>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import binascii
import itertools
import json
from struct import unpack
from typing import Any, Callable, Protocol, TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.util import hexstring


class LSClass(Protocol):
    """Protocol for BGP-LS classes that can unpack from bytes."""

    TLV: int
    MERGE: bool

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> BaseLS: ...


@Attribute.register()
class LinkState(Attribute):
    ID = Attribute.CODE.BGP_LS
    FLAG = Attribute.Flag.OPTIONAL
    TLV = -1

    # Registered subclasses we know how to decode
    registered_lsids: dict[int, type] = dict()

    # what this implementation knows as LS attributes
    node_lsids: list[int] = []
    link_lsids: list[int] = []
    prefix_lsids: list[int] = []

    def __init__(self, ls_attrs: list[BaseLS]) -> None:
        self.ls_attrs = ls_attrs

    @classmethod
    def register_lsid(cls, lsid: int | None = None) -> Callable[[type], type]:
        """Register BGP-LS subclass by TLV code (different from Attribute.register)."""

        def register_class(klass: type) -> type:
            if klass.TLV in cls.registered_lsids:
                raise RuntimeError('only one class can be registered per BGP link state attribute type')
            cls.registered_lsids[klass.TLV] = klass
            return klass

        def register_lsid_inner(klass: type) -> type:
            if not lsid:
                return register_class(klass)

            kls = type('%s_%d' % (klass.__name__, lsid), klass.__bases__, dict(klass.__dict__))
            setattr(kls, 'TLV', lsid)
            return register_class(kls)

        return register_lsid_inner

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
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> LinkState:
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

            if not instance.MERGE:
                ls_attrs.append(instance)
                continue

            for k in ls_attrs:
                if k.TLV == instance.TLV:
                    k.merge(instance)
                    break
            else:
                ls_attrs.append(instance)

        return cls(ls_attrs=ls_attrs)

    def json(self, compact: bool = False) -> str:
        content = ', '.join(d.json() for d in self.ls_attrs)
        return f'{{ {content} }}'

    def __str__(self) -> str:
        return ', '.join(str(d) for d in self.ls_attrs)


class BaseLS:
    TLV: int = -1
    JSON: str = 'json-name-unset'
    REPR: str = 'repr name unset'
    LEN: int = 0
    MERGE: bool = False

    BGPLS_SUBTLV_HEADER_SIZE: int = 4  # Sub-TLV header is 4 bytes (Type 2 + Length 2)

    def __init__(self, packed: bytes) -> None:
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
    def check_length(cls, data: bytes, length: int) -> None:
        if length and len(data) != length:
            raise Notify(3, 5, f'Unable to decode attribute, wrong size for {cls.REPR}')

    @classmethod
    def check(cls, data: bytes) -> None:
        return cls.check_length(data, cls.LEN)

    def merge(self, other: BaseLS) -> None:
        if not self.MERGE:
            raise Notify(3, 5, f'Invalid merge, issue decoding {self.REPR}')
        self.content.extend(other.content)


class GenericLSID(BaseLS):
    TLV: int = 0
    MERGE: bool = True

    def __init__(self, packed: bytes) -> None:
        """Initialize with packed wire-format bytes.

        Args:
            packed: Raw TLV payload bytes
        """
        self._packed = packed
        # For merge support, content is a list of packed bytes
        self._content_list: list[bytes] = [packed]

    @property
    def content(self) -> list[bytes]:
        """Return list of packed bytes (for merge support)."""
        return self._content_list

    def __repr__(self) -> str:
        return 'Attribute with code [ {} ] not implemented'.format(self.TLV)

    def json(self, compact: bool = False) -> str:
        merged = ', '.join([f'"{hexstring(_)}"' for _ in self.content])
        return f'"generic-lsid-{self.TLV}": [{merged}]'

    def merge(self, other: GenericLSID) -> None:
        """Merge another GenericLSID's content into this one."""
        self._content_list.extend(other.content)

    @classmethod
    def unpack_bgpls(cls, data: bytes) -> GenericLSID:
        return cls(data)


class FlagLS(BaseLS):
    # Subclasses define FLAGS as a list of flag names, e.g. ['R', 'N', 'P', 'E', 'V', 'L', 'RSV', 'RSV']
    FLAGS: list[str] = []

    def __init__(self, packed: bytes) -> None:
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
    def unpack_flags(cls, data: bytes) -> dict[str, int]:
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
    def unpack_bgpls(cls, data: bytes) -> FlagLS:
        cls.check(data)
        # We only support IS-IS for now.
        return cls(data)
