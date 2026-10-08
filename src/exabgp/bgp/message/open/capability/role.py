"""role.py

BGP Role capability (RFC 9234, capability code 9).

The value is one octet naming the sender's role in the relationship. RFC 9234
section 4 assigns five, and a session is only allowed to form when the two roles
are complementary.

Role 0 is provider. Absence uses the internal NO_ROLE sentinel, never truthiness.
The sentinel is not a configuration token or a wire role. A value RFC 9234 does not
assign is decoded as UNASSIGNED, the octet kept beside it: whether it matters is
decided by the negotiation, which knows if we advertised a role.

Created for ExaBGP.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

import json
from enum import IntEnum

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log, lazymsg
from exabgp.util.types import Buffer


class RoleValue(IntEnum):
    """The five wire roles, an internal marker for an absent role, and one for an unassigned one."""

    UNASSIGNED = -2
    NO_ROLE = -1
    PROVIDER = 0
    RS = 1
    RS_CLIENT = 2
    CUSTOMER = 3
    PEER = 4

    def __str__(self) -> str:
        if self == RoleValue.NO_ROLE:
            return 'no-role'
        if self == RoleValue.UNASSIGNED:
            return 'unassigned'
        return _NAMES[self]

    @classmethod
    def assigned(cls) -> tuple[RoleValue, ...]:
        return (cls.PROVIDER, cls.RS, cls.RS_CLIENT, cls.CUSTOMER, cls.PEER)

    @classmethod
    def from_string(cls, name: str) -> RoleValue:
        """Parse a configuration token. Names only.

        A numeric string is refused on purpose: accepting '3' would make the
        error for a mistyped name depend on whether the mistake was digits.
        """
        value = _VALUES.get(name)
        if value is None:
            raise ValueError('{} is not a role, use one of {}'.format(name, ', '.join(_VALUES)))
        return value

    @staticmethod
    def complement(role: RoleValue) -> RoleValue:
        """The role the other end must hold for the pair to be allowed.

        With strict mode disabled a missing remote capability is not an error:
        this is the role assumed for it, and the same procedures then run.
        """
        if role == RoleValue.NO_ROLE:
            raise ValueError('NO_ROLE has no complementary role')
        return _COMPLEMENT[role]

    @staticmethod
    def pair_allowed(local: RoleValue, remote: RoleValue) -> bool:
        """RFC 9234 section 4: five pairs form a session, everything else is a mismatch.

        No row of Table 2 holds an unassigned role, on either side.
        """
        return local in _COMPLEMENT and _COMPLEMENT[local] == remote


_NAMES: dict[RoleValue, str] = {
    RoleValue.PROVIDER: 'provider',
    RoleValue.RS: 'rs',
    RoleValue.RS_CLIENT: 'rs-client',
    RoleValue.CUSTOMER: 'customer',
    RoleValue.PEER: 'peer',
}

_VALUES: dict[str, RoleValue] = {name: value for value, name in _NAMES.items()}

_COMPLEMENT: dict[RoleValue, RoleValue] = {
    RoleValue.PROVIDER: RoleValue.CUSTOMER,
    RoleValue.CUSTOMER: RoleValue.PROVIDER,
    RoleValue.RS: RoleValue.RS_CLIENT,
    RoleValue.RS_CLIENT: RoleValue.RS,
    RoleValue.PEER: RoleValue.PEER,
}

assert set(_NAMES) == set(RoleValue.assigned()), 'every assigned role needs a name'
assert set(_COMPLEMENT) == set(RoleValue.assigned()), 'every assigned role needs a complement'


class Role(Capability):
    """RFC 9234 BGP Role capability, one octet of value."""

    ID: ClassVar = Capability.CODE.ROLE
    VALUE_SIZE: ClassVar[int] = 1

    def __init__(self, value: RoleValue = RoleValue.NO_ROLE, octet: int = -1) -> None:
        assert value != RoleValue.UNASSIGNED or (0 <= octet <= 255 and octet not in _NAMES), 'an unassigned octet'
        self.value: RoleValue = value
        # The octet on the wire: the role's own value, or the unassigned one a peer sent
        self.octet: int = int(value) if value != RoleValue.UNASSIGNED else octet

    def __str__(self) -> str:
        if self.value == RoleValue.NO_ROLE:
            return 'Role(unset)'
        if self.value == RoleValue.UNASSIGNED:
            return 'Role(unassigned {})'.format(self.octet)
        return 'Role({})'.format(self.value)

    def json(self) -> str:
        return '{{ "name": "role", "role": {} }}'.format(json.dumps(str(self.value)))

    def extract_capability_bytes(self) -> list[bytes]:
        if self.value == RoleValue.NO_ROLE:
            return []
        return [bytes([self.octet])]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, Role)

        view = memoryview(data)
        if len(view) != cls.VALUE_SIZE:
            # The peer controls this length, so it is checked, never asserted.
            raise Notify(2, 0, 'role capability is {} bytes, it must be {}'.format(len(view), cls.VALUE_SIZE))

        received = view[0]
        # An unassigned value is well formed. RFC 9234 4.2 makes it a Role Mismatch only
        # "If the BGP Role Capability is advertised" by us, which the negotiation decides:
        # without a role of ours it is a capability we have no use for, as RFC 5492 has it.
        role = RoleValue(received) if received in _NAMES else RoleValue.UNASSIGNED

        if instance.value == RoleValue.NO_ROLE:
            instance.value = role
            instance.octet = received
            return instance

        # RFC 5492 section 5 lets a receiver keep one instance of a capability sent
        # more than once. Two Role capabilities which agree are one answer sent
        # twice. Two which disagree are two answers, and keeping either would be
        # choosing on the peer's behalf what its role is.
        if instance.octet != received:
            raise Notify(
                2,
                11,
                'role capability sent twice with different roles, {} then {}'.format(instance.octet, received),
            )
        log.debug(lazymsg('capability.role.duplicate action=ignore role={role}', role=role), 'parser')
        return instance

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Role):
            return False
        return self.value == other.value and self.octet == other.octet

    def __ne__(self, other: object) -> bool:
        return not self == other

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')


Capability.register()(Role)
