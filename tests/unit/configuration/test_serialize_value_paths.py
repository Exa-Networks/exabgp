"""The paths of _serialize_value which the configuration export tests do not reach.

`tests/unit/configuration/test_configuration_export.py` and
`tests/unit/test_otc_role_configuration.py` drive _serialize_value through every example
configuration, but measured with branch coverage on 2026-09-29 they never hand it a None
inside a container, an IPSelf, a RoleValue on its own, a Counter, or a dataclass which has
no branch of its own.  These tests pin what the function does on each before it is split
into per type helpers (plan-large-function-decomposition), together with the order of the
checks the split must keep: the IP subclasses before IP, the int subclasses before the
primitive fall through, and the values it hands back unchanged.

They pin what the function does today, including the Counter whose values are not
converted and the containers (set, bytearray) passed through for json.dumps to refuse.
"""

from __future__ import annotations

import json
from collections import Counter, deque
from dataclasses import dataclass

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.neighbor.session import Session
from exabgp.configuration.encoder import ConfigEncoder, _serialize_value, config_to_json
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP, IPRange, IPSelf
from exabgp.util.enumeration import TriState


@dataclass
class _Pair:
    """A dataclass the encoder has no branch for, so it takes the generic fallback."""

    left: object = None
    right: object = None


class TestNone:
    def test_none_alone(self) -> None:
        assert _serialize_value(None) is None

    def test_none_inside_containers(self) -> None:
        assert _serialize_value([None, {'a': None}, (None,)]) == [None, {'a': None}, [None]]


class TestIPSelf:
    @pytest.mark.parametrize(('afi', 'name'), [(AFI.ipv4, 'ipv4'), (AFI.ipv6, 'ipv6')])
    def test_ipself(self, afi: AFI, name: str) -> None:
        assert _serialize_value(IPSelf(afi)) == {'_type': 'IPSelf', 'afi': name}

    def test_ipself_through_encoder_default(self) -> None:
        assert ConfigEncoder().default(IPSelf(AFI.ipv4)) == {'_type': 'IPSelf', 'afi': 'ipv4'}

    def test_iprange_is_not_serialised_as_plain_ip(self) -> None:
        value = IPRange.make_range('10.0.0.0', 24)
        assert _serialize_value(value) == {'_type': 'IPRange', 'ip': '10.0.0.0', 'mask': 24}

    def test_no_nexthop(self) -> None:
        assert _serialize_value(IP.NoNextHop) == {'_type': 'IP', 'value': 'no-nexthop'}


class TestRoleValue:
    @pytest.mark.parametrize('role', list(RoleValue))
    def test_role_is_its_string(self, role: RoleValue) -> None:
        assert _serialize_value(role) == str(role)

    def test_role_inside_a_dict(self) -> None:
        assert _serialize_value({'role': RoleValue.CUSTOMER}) == {'role': str(RoleValue.CUSTOMER)}


class TestIntSubclasses:
    def test_each_is_tagged_not_a_plain_int(self) -> None:
        assert _serialize_value([TriState.TRUE, HoldTime(90), ASN(65000), AFI.ipv6, SAFI.unicast]) == [
            {'_type': 'TriState', 'value': 'TRUE'},
            {'_type': 'HoldTime', 'value': 90},
            {'_type': 'ASN', 'value': 65000},
            {'_type': 'AFI', 'value': 'ipv6'},
            {'_type': 'SAFI', 'value': 'unicast'},
        ]

    @pytest.mark.parametrize('value', [0, 7, 1.5, True, False, '', 'text'])
    def test_primitives_are_returned_unchanged(self, value: object) -> None:
        assert _serialize_value(value) is value


class TestSession:
    def test_falsy_optionals_become_none(self) -> None:
        result = _serialize_value(Session())
        assert result['router_id'] is None
        assert result['md5_password'] is None
        assert result['md5_ip'] is None
        assert result['source_interface'] is None
        assert 'role' not in result

    def test_set_optionals_are_kept(self) -> None:
        session = Session(md5_password='secret', md5_ip=IP.from_string('1.1.1.1'), source_interface='eth0')
        result = _serialize_value(session)
        assert result['md5_password'] == 'secret'
        assert result['md5_ip'] == {'_type': 'IP', 'value': '1.1.1.1'}
        assert result['source_interface'] == 'eth0'

    def test_role_keys_follow_the_rest(self) -> None:
        result = _serialize_value(Session(role=RoleValue.PEER, role_strict=True, role_add_meta=False))
        assert list(result)[-3:] == ['role', 'role_strict', 'role_add_meta']
        assert (result['role'], result['role_strict'], result['role_add_meta']) == (str(RoleValue.PEER), True, False)


class TestCounter:
    def test_counter_becomes_a_dict(self) -> None:
        result = _serialize_value(Counter({'a': 2, 'b': 1}))
        assert type(result) is dict
        assert result == {'a': 2, 'b': 1}

    def test_counter_values_are_not_converted(self) -> None:
        result = _serialize_value(Counter({'a': ASN(5)}))
        assert type(result['a']) is ASN

    def test_counter_through_encoder_default(self) -> None:
        assert ConfigEncoder().default(Counter({'x': 3})) == {'x': 3}


class TestContainers:
    def test_deque_recurses(self) -> None:
        assert _serialize_value(deque([ASN(1), deque([b'\x01'])])) == [
            {'_type': 'ASN', 'value': 1},
            [{'_type': 'bytes', 'hex': '01'}],
        ]

    def test_tuple_becomes_a_list(self) -> None:
        assert _serialize_value((ASN(1), 'y')) == [{'_type': 'ASN', 'value': 1}, 'y']

    def test_dict_keys_are_not_converted(self) -> None:
        result = _serialize_value({ASN(3): 'x'})
        assert type(next(iter(result))) is ASN

    @pytest.mark.parametrize('value', [bytearray(b'ab'), {1, 2}, frozenset()])
    def test_unknown_containers_pass_through(self, value: object) -> None:
        assert _serialize_value(value) is value
        with pytest.raises(TypeError):
            config_to_json(value)


class TestDataclassFallback:
    def test_dataclass_recurses_into_its_fields(self) -> None:
        value = _Pair(ASN(7), [_Pair(TriState.FALSE)])
        assert _serialize_value(value) == {
            'left': {'_type': 'ASN', 'value': 7},
            'right': [{'left': {'_type': 'TriState', 'value': 'FALSE'}, 'right': None}],
        }

    def test_dataclass_through_config_to_json(self) -> None:
        assert json.loads(config_to_json(_Pair('a', 1))) == {'left': 'a', 'right': 1}

    def test_dataclass_class_itself_is_returned_unchanged(self) -> None:
        assert _serialize_value(_Pair) is _Pair
        with pytest.raises(TypeError):
            ConfigEncoder().default(_Pair)
