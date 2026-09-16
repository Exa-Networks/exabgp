#!/usr/bin/env python3
# encoding: utf-8
"""test_role_capability.py

RFC 9234 BGP Role capability (code 9).

The capability value is a single octet naming the sender's role. Five values are
assigned, 0 to 4; everything above is unassigned. The tests below hold the wire
format, the two failure modes a peer can trigger (a wrong length and an
unassigned value), and the duplicate rule: RFC 5492 lets a receiver keep one
instance of a repeated capability, but two Role capabilities disagreeing about
the sender's role cannot both be kept, and RFC 9234 has a subcode for exactly
that disagreement.

Role 0 is provider, so every check here uses an explicit absence test rather
than truthiness. A `if role:` anywhere in this feature silently means
"if the role is not provider".

Created for ExaBGP testing framework
License: 3-clause BSD
"""

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.capabilities import Capabilities
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.role import Role
from exabgp.bgp.message.open.capability.role import RoleValue


# ==============================================================================
# Wire format
# ==============================================================================


def test_capability_code_is_nine() -> None:
    """RFC 9234 assigns capability code 9."""
    assert Capability.CODE.ROLE == 9
    assert Role.ID == 9


def test_capability_code_names_itself() -> None:
    """The registry name is what logs and the JSON envelope print."""
    assert CapabilityCode(9).name() == 'role'


@pytest.mark.parametrize(
    'value,name',
    [
        (0, 'provider'),
        (1, 'rs'),
        (2, 'rs-client'),
        (3, 'customer'),
        (4, 'peer'),
    ],
)
def test_every_assigned_role_round_trips(value: int, name: str) -> None:
    """RFC 9234 section 4 assigns 0 to 4, and the names are the configuration tokens."""
    role = Role(RoleValue(value))
    assert role.extract_capability_bytes() == [bytes([value])]
    assert str(RoleValue(value)) == name

    parsed = Role.unpack_capability(Role(), memoryview(bytes([value])), Capability.CODE.ROLE)
    assert isinstance(parsed, Role)
    assert parsed.value == value


def test_provider_is_zero_and_not_absent() -> None:
    """Role 0 is a configured role, not a missing one. Truthiness must not decide."""
    capabilities = Capabilities()
    capabilities[Capability.CODE.ROLE] = Role(RoleValue.PROVIDER)
    packed = capabilities.pack_capabilities()
    assert packed == bytes.fromhex('050203090100')
    assert Capabilities.unpack(packed).role() == RoleValue.PROVIDER


def test_value_is_exactly_one_octet() -> None:
    assert len(Role(RoleValue.CUSTOMER).extract_capability_bytes()[0]) == 1


def test_no_role_is_not_advertised() -> None:
    capabilities = Capabilities()
    capabilities[Capability.CODE.ROLE] = Role()
    assert capabilities.role() == RoleValue.NO_ROLE
    packed = capabilities.pack_capabilities()
    assert packed == b'\x00'
    assert Capabilities.unpack(packed).role() == RoleValue.NO_ROLE


# ==============================================================================
# What a peer can get wrong
# ==============================================================================


@pytest.mark.parametrize('payload', [b'', b'\x03\x03', b'\x00\x00\x00\x00'])
def test_wrong_length_ends_the_session(payload: bytes) -> None:
    """A malformed capability is Notify(2, 0), the house convention.

    Never an assert: peer input is not an invariant, and -O would remove the check.
    """
    with pytest.raises(Notify) as exc:
        Role.unpack_capability(Role(), memoryview(payload), Capability.CODE.ROLE)
    assert exc.value.code == 2
    assert exc.value.subcode == 0


@pytest.mark.parametrize('value', [5, 6, 128, 255])
def test_unassigned_role_is_a_role_mismatch(value: int) -> None:
    """An unassigned value names a role no allowed pair can satisfy.

    Notify(2, 11) rather than (2, 0): the capability is well formed, and the
    honest complaint is that the role it carries cannot be agreed with.
    """
    with pytest.raises(Notify) as exc:
        Role.unpack_capability(Role(), memoryview(bytes([value])), Capability.CODE.ROLE)
    assert exc.value.code == 2
    assert exc.value.subcode == 11


# ==============================================================================
# Duplicates
# ==============================================================================


def test_identical_duplicate_is_kept_once() -> None:
    """RFC 5492 section 5: a receiver may keep one instance of a repeated capability."""
    instance = Role()
    first = Role.unpack_capability(instance, memoryview(b'\x03'), Capability.CODE.ROLE)
    second = Role.unpack_capability(first, memoryview(b'\x03'), Capability.CODE.ROLE)
    assert isinstance(second, Role)
    assert second.value == RoleValue.CUSTOMER


def test_differing_duplicate_is_a_role_mismatch() -> None:
    """Two Role capabilities disagreeing cannot both be kept, and keeping either
    would be picking one of the peer's two answers for it."""
    instance = Role()
    first = Role.unpack_capability(instance, memoryview(b'\x03'), Capability.CODE.ROLE)
    with pytest.raises(Notify) as exc:
        Role.unpack_capability(first, memoryview(b'\x00'), Capability.CODE.ROLE)
    assert exc.value.code == 2
    assert exc.value.subcode == 11


# ==============================================================================
# Presentation
# ==============================================================================


def test_str_names_the_role() -> None:
    assert str(Role(RoleValue.RS_CLIENT)) == 'Role(rs-client)'


def test_json_is_parseable_and_names_the_role() -> None:
    import json

    payload = json.loads(Role(RoleValue.PEER).json())
    assert payload == {'name': 'role', 'role': 'peer'}


# ==============================================================================
# Role pairing, RFC 9234 section 4
# ==============================================================================


@pytest.mark.parametrize(
    'local,remote',
    [
        (RoleValue.PROVIDER, RoleValue.CUSTOMER),
        (RoleValue.CUSTOMER, RoleValue.PROVIDER),
        (RoleValue.RS, RoleValue.RS_CLIENT),
        (RoleValue.RS_CLIENT, RoleValue.RS),
        (RoleValue.PEER, RoleValue.PEER),
    ],
)
def test_the_five_allowed_pairs(local: RoleValue, remote: RoleValue) -> None:
    assert RoleValue.pair_allowed(local, remote) is True


@pytest.mark.parametrize(
    'local,remote',
    [
        (RoleValue.PROVIDER, RoleValue.PROVIDER),
        (RoleValue.PROVIDER, RoleValue.PEER),
        (RoleValue.CUSTOMER, RoleValue.CUSTOMER),
        (RoleValue.RS, RoleValue.RS),
        (RoleValue.RS, RoleValue.CUSTOMER),
        (RoleValue.PEER, RoleValue.CUSTOMER),
    ],
)
def test_disallowed_pairs(local: RoleValue, remote: RoleValue) -> None:
    assert RoleValue.pair_allowed(local, remote) is False


@pytest.mark.parametrize(
    'local,complement',
    [
        (RoleValue.PROVIDER, RoleValue.CUSTOMER),
        (RoleValue.CUSTOMER, RoleValue.PROVIDER),
        (RoleValue.RS, RoleValue.RS_CLIENT),
        (RoleValue.RS_CLIENT, RoleValue.RS),
        (RoleValue.PEER, RoleValue.PEER),
    ],
)
def test_complement_is_what_strict_disabled_infers(local: RoleValue, complement: RoleValue) -> None:
    """With strict mode off a missing remote capability is not an error: the
    effective remote role is the complement, and the same procedures run."""
    assert RoleValue.complement(local) == complement


def test_every_role_has_exactly_one_complement() -> None:
    """The pairing table and the complement table must not disagree."""
    for role in RoleValue.assigned():
        assert RoleValue.pair_allowed(role, RoleValue.complement(role)) is True


def test_no_role_never_forms_a_relationship() -> None:
    for role in RoleValue:
        assert not RoleValue.pair_allowed(RoleValue.NO_ROLE, role)
        assert not RoleValue.pair_allowed(role, RoleValue.NO_ROLE)
    with pytest.raises(ValueError):
        RoleValue.complement(RoleValue.NO_ROLE)


# ==============================================================================
# Names as configuration tokens
# ==============================================================================


@pytest.mark.parametrize(
    'name,value',
    [
        ('provider', RoleValue.PROVIDER),
        ('rs', RoleValue.RS),
        ('rs-client', RoleValue.RS_CLIENT),
        ('customer', RoleValue.CUSTOMER),
        ('peer', RoleValue.PEER),
    ],
)
def test_names_parse_back_to_values(name: str, value: RoleValue) -> None:
    assert RoleValue.from_string(name) == value


def test_an_unknown_name_is_refused() -> None:
    with pytest.raises(ValueError):
        RoleValue.from_string('upstream')


def test_a_numeric_string_is_not_a_role_name() -> None:
    """The configuration takes names. Accepting '3' here would make the error
    message for a typo'd name depend on whether the typo happened to be digits."""
    with pytest.raises(ValueError):
        RoleValue.from_string('3')


def test_no_role_is_not_a_configuration_token() -> None:
    with pytest.raises(ValueError):
        RoleValue.from_string(str(RoleValue.NO_ROLE))
