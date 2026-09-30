"""internal.py

The values exabgp keeps with a route and never sends: its name, split, watchdog, withdraw.

They travel in the AttributeCollection under the private INTERNAL_* codes. The
configuration made them as `str` and `int` subclasses carrying the code as `ID`, which the
collection, typed `Attribute`, only accepted because nothing checked: compiled with mypyc
it does check. They are attributes now, each holding its value, and they still compare
equal to the plain value, as the `str` and `int` subclasses did, and keep the class names
the configuration gave them (tests/unit/config_grammar/test_frozen.py records them).

See plan/wip-mypyc.md.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from exabgp.bgp.message.update.attribute.attribute import Attribute

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated


class InternalAttribute(Attribute):
    NO_GENERATION: ClassVar[bool] = True

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        return b''

    def json(self, compact: bool = False) -> str:
        return ''


class InternalText(InternalAttribute):
    def __init__(self, value: str) -> None:
        self.value = value

    def _comparable(self) -> tuple[int, int, object]:
        return (self.ID, self.FLAG, self.value)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self.value == other
        return Attribute.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        # the operator, not a call to __eq__: it answers NotImplemented the way Python does,
        # where a compiled bool-typed local would refuse it
        return not self == other

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return self.value


class InternalNumber(InternalAttribute):
    def __init__(self, value: int) -> None:
        self.value = value

    def _comparable(self) -> tuple[int, int, object]:
        return (self.ID, self.FLAG, self.value)

    def __int__(self) -> int:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.value == other
        return Attribute.__eq__(self, other)

    def __ne__(self, other: object) -> bool:
        # the operator, not a call to __eq__: it answers NotImplemented the way Python does,
        # where a compiled bool-typed local would refuse it
        return not self == other

    def __hash__(self) -> int:
        return hash(self.value)

    def __str__(self) -> str:
        return str(self.value)

    def __repr__(self) -> str:
        return str(self.value)


class Name(InternalText):
    """`name <name>`: a name for the route, kept by exabgp and never sent."""

    ID: ClassVar[int] = Attribute.CODE.INTERNAL_NAME


class Watchdog(InternalText):
    """`watchdog <name>`: the watchdog whose API commands announce and withdraw the route."""

    ID: ClassVar[int] = Attribute.CODE.INTERNAL_WATCHDOG


class Split(InternalNumber):
    """`split /<length>`: announce the prefix as its more specifics of this length."""

    ID: ClassVar[int] = Attribute.CODE.INTERNAL_SPLIT


class Withdrawn(InternalAttribute):
    """`withdraw`: start with the route withdrawn."""

    ID: ClassVar[int] = Attribute.CODE.INTERNAL_WITHDRAW

    def _comparable(self) -> tuple[int, int, object]:
        return (self.ID, self.FLAG, None)

    def __hash__(self) -> int:
        return hash(self._comparable())

    def __repr__(self) -> str:
        return ''
