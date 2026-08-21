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
from struct import error as struct_error, unpack
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Protocol

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
    # RFC 7752 section 5.3 and RFC 9552 section 7.2.1: a malformed BGP-LS attribute is
    # discarded, the session is not reset. AttributeCollection.parse honours this flag.
    DISCARD: ClassVar[bool] = True

    # Registered subclasses we know how to decode
    registered_lsids: dict[int, type] = dict()

    # what this implementation knows as LS attributes
    node_lsids: list[int] = []
    link_lsids: list[int] = []
    prefix_lsids: list[int] = []

    def __init__(self, packed: Buffer) -> None:
        """Initialize with raw attribute bytes (stores, parses on first access)."""
        self._packed = packed
        self._ls_attrs: list[BaseLS] | None = None

    @property
    def ls_attrs(self) -> list[BaseLS]:
        """The TLVs this attribute holds, parsed once by the decoder.

        unpack_attribute parses before returning, so a malformed TLV is a Notify raised
        from the decode path, where the reactor answers it with a NOTIFICATION.  Parsing
        here on every access instead meant json() and __str__() raised, from the API
        writer, long after the UPDATE had been accepted.
        """
        if self._ls_attrs is None:
            self._ls_attrs = self._parse_tlvs(self._packed)
        return self._ls_attrs

    @classmethod
    def _parse_tlvs(cls, data: Buffer) -> list[BaseLS]:
        """Parse TLVs from raw bytes."""
        ls_attrs: list[BaseLS] = []
        seen: set[int] = set()

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
            cls._check_not_repeated(klass, scode, seen)
            ls_attrs.append(cls._decode_tlv(klass, scode, payload))

        return ls_attrs

    @classmethod
    def _check_not_repeated(cls, klass: type[LSClass], scode: int, seen: set[int]) -> None:
        """RFC 9552 5.3.2: a TLV which may not repeat, repeated, makes the attribute malformed.

        The RFC calls for the attribute discard approach, and DISCARD is set on this class,
        so AttributeCollection.parse drops the BGP-LS attribute and keeps the route.

        MERGE is already this implementation's marker for "may appear more than once", so
        it is the marker used here rather than a second list which could disagree with it.
        A repeated TLV without it rendered its JSON key twice, and every parser resolves
        that by keeping one of them, so the other was lost silently: the peer chose which
        of its own values the API consumer saw.

        A code nothing has registered is not held to this.  get_ls_class synthesises a
        GenericLSID for it, and we cannot claim a TLV we do not implement may not repeat:
        refusing it would drop the attribute of a deployment using an extension we simply
        have not caught up with.  It renders under a code specific name, so two of them do
        not collide either.
        """
        if getattr(klass, 'MERGE', False) or getattr(klass, 'GENERIC', False):
            return
        if scode in seen:
            raise Notify(3, 5, f'BGP-LS: TLV {scode} appears more than once and may not repeat')
        seen.add(scode)

    @staticmethod
    def _decode_tlv(klass: type[LSClass], scode: int, payload: Buffer) -> BaseLS:
        """Decode one TLV, turning a short read into a Notify the peer can be told about.

        This used to render the TLV here as well, to prove it could be rendered, because
        the TLV classes unpack in properties and several of them read past their payload
        the first time json() touched it.  They check their own reads now, and rendering
        twice cost 31x on the decode path: 312us for an eleven TLV attribute against 9us,
        which is half a minute of CPU for a hundred thousand object table, inside the
        reactor.  The registry wide property tests are what hold the renders now.
        """
        try:
            instance = klass.unpack_bgpls(payload)
            if isinstance(instance, FlagLS):
                # these unpack their flags in a property, and nine of the thirteen override
                # unpack_bgpls, so the read goes here where every one of them passes. A bit
                # pattern we do not know is the peer's error and belongs to the decoder;
                # leaving it to the first render put the Notify in the API writer. The
                # instance caches it, so the render does not pay for it again.
                instance.flags
        except Notify:
            raise
        except (IndexError, struct_error) as exc:
            # only the shapes a short read takes. TypeError and AttributeError out of a
            # property are our bug, and converting them would blame the peer for it and
            # tear down a session carrying perfectly valid traffic: the missing
            # GenericSRId.pack_tlv in this same series was found precisely because its
            # AttributeError escaped loudly rather than being renamed a protocol error.
            raise Notify(3, 5, f'BGP-LS: TLV {scode} could not be decoded: {exc}') from None
        return instance

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
        # the JSON name has to be set here as well as the TLV.  GenericLSID merges, and
        # the merge groups by name, so leaving every synthesised class on the inherited
        # default would collapse every unknown code the peer sent into one member
        setattr(unknown, 'JSON', f'generic-lsid-{code}')
        cls.registered_lsids[code] = unknown
        return unknown

    @classmethod
    def is_lsid_registered(cls, lsid: int) -> bool:
        """Check if BGP-LS TLV code is registered (different from Attribute.registered)."""
        return lsid in cls.registered_lsids

    @classmethod
    def unpack_attribute(cls, data: Buffer, negotiated: Negotiated) -> Attribute:
        """Decode the TLVs, so malformed ones are refused here rather than in json()."""
        instance = cls(data)
        # a statement, never an assertion: -O deletes an assert, and with it the whole
        # boundary this commit exists to create (TIGER_STYLE.md 1.2, nothing may depend on
        # an assertion running). Reading the property is what parses.
        instance.ls_attrs
        return instance

    def json(self, compact: bool = False) -> str:
        """Output JSON for all TLVs. MERGE classes are grouped into arrays by JSON key."""
        from collections import defaultdict

        # Separate MERGE and non-MERGE attributes
        # MERGE: group by JSON key (so alias TLVs like 1028/1029 merge together)
        # Non-MERGE: preserve order, output individually
        merge_groups: dict[str, list[BaseLS]] = defaultdict(list)
        non_merge: list[BaseLS] = []

        for attr in self.ls_attrs:
            if getattr(attr, 'MERGE', False):
                merge_groups[attr.JSON].append(attr)
            else:
                non_merge.append(attr)

        parts = []
        # Output MERGE groups as arrays
        for key, attrs in merge_groups.items():
            contents = [jsonable(a.content) for a in attrs]
            parts.append(f'"{key}": {json.dumps(contents)}')
        # Output non-MERGE individually
        for attr in non_merge:
            parts.append(attr.json(compact))

        return '{ ' + ', '.join(parts) + ' }'

    def __str__(self) -> str:
        return ', '.join(str(d) for d in self.ls_attrs)


def jsonable(content: Any) -> Any:
    """Turn what a TLV holds into something json.dumps will accept.

    A TLV whose content is raw bytes used to fall out of json.dumps with a TypeError,
    and the fallback interpolated `content.decode("utf-8")` into the output unescaped.
    That is the CWE-116 of GHSA-jcrv-p53f-v5w5, reachable through TLV 1097 and 1157 by
    a peer attaching attribute 29 to a plain IPv4 unicast UPDATE: no BGP-LS session
    needed, since the attribute is dispatched by code with no family gate.

    Bytes the peer chose are not guaranteed to be text, so they are decoded with
    'replace' rather than raising UnicodeDecodeError out of the API writer.
    """
    if isinstance(content, (bytes, bytearray, memoryview)):
        return bytes(content).decode('utf-8', 'replace')
    if isinstance(content, dict):
        return {str(jsonable(key)): jsonable(value) for key, value in content.items()}
    if isinstance(content, (list, tuple)):
        return [jsonable(item) for item in content]
    if isinstance(content, (str, int, float, bool)) or content is None:
        return content
    return str(content)


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
        return f'"{self.JSON}": {json.dumps(jsonable(self.content))}'

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
    def check_multiple(cls, data: Buffer, size_bytes: int) -> None:
        """A TLV built of fixed size elements holds a whole number of them.

        check_length() cannot say this: a variable length TLV has LEN 0, and zero is
        falsy, so `if length and ...` checks nothing at all.  A TLV which unpacks its
        elements in a loop needs this instead, or the last read runs off the end.
        """
        assert size_bytes > 0, 'an element has a size'
        # an empty TLV is a whole number of elements, none of them, and renders as an empty
        # list: RFC 7752 says one or more, but this release accepts it and refusing it now
        # would drop a route on upgrade
        if len(data) % size_bytes:
            raise Notify(
                3,
                5,
                f'Unable to decode attribute, {cls.REPR} holds {len(data)} bytes '
                f'which is not a whole number of {size_bytes} byte elements',
            )

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

    # get_ls_class builds each unknown code its own class from GenericLSID.__bases__, so
    # the result is a SIBLING of this class and not a subclass: issubclass says no.  The
    # flag is copied with the rest of __dict__ and does say yes, which is what callers
    # need to ask.  Session 5.0 hit the same identity trap in register_lsid, where two
    # aliases of one class never compared equal to each other.
    GENERIC: ClassVar[bool] = True

    # we do not know whether a TLV we have not implemented may repeat, so it is neither
    # refused nor collapsed: it merges, and both values reach the API under one key.  Two
    # of the same unknown code otherwise emitted that key twice, and every JSON parser
    # resolves a duplicate key by keeping one of them
    MERGE = True

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
        # the key is computed rather than read from JSON, so an instance built directly
        # rather than through get_ls_class still names its own code.  get_ls_class sets
        # JSON to the same string, so the merge groups by the same name this renders.
        # Always an array, which is what the merge produces when the peer sends the same
        # unknown code twice, so the member keeps one type either way
        return f'"generic-lsid-{self.TLV}": ["{self.content}"]'

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
        """The flags this TLV carries, unpacked once."""
        cached = getattr(self, '_flags_cache', None)
        if cached is None:
            cached = self.unpack_flags(self._packed[0:1])
            self._flags_cache = cached
        return cached

    @property
    def content(self) -> Any:
        """The flags, which is what json() renders and therefore what the merge must group.

        BaseLS.content returns the raw packed bytes, and every flag TLV which did not
        override it disagreed with its own json(): one rendered a decoded object, the other
        the wire bytes.  Nothing showed, because json() is what the API calls and content is
        only reached through the merge, which none of these classes used.

        That made each of them one MERGE = True away from emitting raw bytes to the API,
        which is exactly what happened when PrefixSid and Srv6Locator were marked as
        repeatable.  Session 5.0 raised the general case after IsisArea disagreed the same
        way.  The two renderers now read one value.
        """
        return self.flags

    def __repr__(self) -> str:
        return '{}: {}'.format(self.REPR, self.flags)

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.flags)}'

    @classmethod
    def _valid_flags(cls) -> frozenset[str]:
        """The bit patterns this TLV allows, built once per class rather than per call.

        This rebuilt 2**n strings on every access, and the flags are read several times
        per render: it was 73% of the time spent decoding a BGP-LS attribute.
        """
        cached = cls.__dict__.get('_valid_flags_cache')
        if cached is None:
            pad = cls.FLAGS.count('RSV')
            repeat = len(cls.FLAGS) - pad
            cached = frozenset(
                [''.join(item) + '0' * pad for item in itertools.product('01', repeat=repeat)] + ['0000']
            )
            setattr(cls, '_valid_flags_cache', cached)
        return cached

    @classmethod
    def unpack_flags(cls, data: Buffer) -> dict[str, int]:
        if not data:
            raise Notify(3, 5, 'BGP-LS: empty data for flag unpacking')
        hex_rep = int(binascii.b2a_hex(data), 16)
        bits = f'{hex_rep:08b}'
        valid_flags = cls._valid_flags()
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
