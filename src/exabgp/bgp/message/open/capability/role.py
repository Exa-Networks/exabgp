"""role.py

BGP Role capability (RFC 9234, capability code 9).

The value is one octet naming the sender's role in the relationship. RFC 9234
section 4 assigns five, and a session is only allowed to form when the two roles
are complementary.

Role 0 is provider. Absence uses the internal NO_ROLE sentinel, never truthiness.
The sentinel is not a configuration token or a wire role.

Created for ExaBGP.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from enum import IntEnum

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.logger import log, lazymsg
from exabgp.util.types import Buffer


class RoleValue(IntEnum):
    """The five wire roles and an internal marker for an absent role."""

    NO_ROLE = -1
    PROVIDER = 0
    RS = 1
    RS_CLIENT = 2
    CUSTOMER = 3
    PEER = 4

    def __str__(self) -> str:
        if self == RoleValue.NO_ROLE:
            return 'no-role'
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
        """RFC 9234 section 4: five pairs form a session, everything else is a mismatch."""
        return local != RoleValue.NO_ROLE and _COMPLEMENT[local] == remote


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


@Capability.register()
class Role(Capability):
    """RFC 9234 BGP Role capability, one octet of value."""

    ID = Capability.CODE.ROLE
    VALUE_SIZE = 1

    def __init__(self, value: RoleValue = RoleValue.NO_ROLE) -> None:
        self.value: RoleValue = value

    def __str__(self) -> str:
        if self.value == RoleValue.NO_ROLE:
            return 'Role(unset)'
        return 'Role({})'.format(self.value)

    def json(self) -> str:
        return '{{ "name": "role", "role": {} }}'.format(json.dumps(str(self.value)))

    def extract_capability_bytes(self) -> list[bytes]:
        if self.value == RoleValue.NO_ROLE:
            return []
        return [bytes([self.value])]

    @classmethod
    def unpack_capability(cls, instance: Capability, data: Buffer, capability: CapabilityCode) -> Capability:  # pylint: disable=W0613
        assert isinstance(instance, Role)

        view = memoryview(data)
        if len(view) != cls.VALUE_SIZE:
            # The peer controls this length, so it is checked, never asserted.
            raise Notify(2, 0, 'role capability is {} bytes, it must be {}'.format(len(view), cls.VALUE_SIZE))

        received = view[0]
        if received not in _NAMES:
            # Well formed, but naming a role no allowed pair can satisfy. Role
            # Mismatch is the honest subcode; (2, 0) would say the bytes were bad.
            raise Notify(2, 11, 'role capability carries unassigned value {}'.format(received))
        role = RoleValue(received)

        if instance.value == RoleValue.NO_ROLE:
            instance.value = role
            return instance

        # RFC 5492 section 5 lets a receiver keep one instance of a capability sent
        # more than once. Two Role capabilities which agree are one answer sent
        # twice. Two which disagree are two answers, and keeping either would be
        # choosing on the peer's behalf what its role is.
        if instance.value != role:
            raise Notify(
                2,
                11,
                'role capability sent twice with different roles, {} then {}'.format(instance.value, role),
            )
        log.debug(lazymsg('capability.role.duplicate action=ignore role={role}', role=role), 'parser')
        return instance

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Role):
            return False
        return self.value == other.value

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing Role for ordering does not make sense')
