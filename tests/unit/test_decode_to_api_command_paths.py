"""The paths of decode_to_api_command which no API encode vector reaches.

`./qa/bin/test_api_encode --self-check` decodes every one of its vectors through
decode_to_api_command and is what pins the function, but measured with coverage on
2026-09-29 it never runs the End-of-RIB forms, an RTC or SR-Policy withdrawal, a FlowSpec,
MUP or MCAST-VPN withdrawal outside a `group`, a label which is not a list, a withdrawal
given as a plain string, or an attributes-only UPDATE.  These tests pin what the function
does on each before it is split into per family helpers (plan-large-function-decomposition).

What is pinned is the dispatch from the decoded JSON to command text, which is what the
split moves.  So the JSON is built here rather than decoded from wire bytes, and the
formatters the function delegates to are replaced by stubs which say how they were called:
their own output has its own tests, and the split must not change which one is called, with
what, or in what order.

Compiled with mypyc, the module calls its own functions and the ones it imports directly,
so stubs set on it are never called. Against the compiled tree the tests therefore run the
module's source, command.py beside the extension, as an interpreted copy: what is pinned is
the dispatch the source describes, and the extension is compiled from that same source.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

import pytest

from exabgp.configuration import command
from tests import negotiation

if TYPE_CHECKING:
    from exabgp.bgp.neighbor import Neighbor


class _Encoder:
    """Stands in for Response.JSON: hands back the UPDATE the test built."""

    message: dict[str, Any] = {}
    last: _Encoder | None = None

    def __init__(self, _version: str) -> None:
        self.generic_attribute_format = False
        _Encoder.last = self

    def update(self, *_args: object) -> str:
        return json.dumps({'neighbor': {'message': {'update': _Encoder.message}}})


def _formatter(name: str) -> Any:
    def formatted(
        afi: str,
        nexthop: str,
        nlri_info: dict[str, Any],
        _attributes: dict[str, Any],
        action: str = 'announce',
        skip_attributes: bool = False,
    ) -> str | None:
        if nlri_info.get('none'):
            return None
        return f'{name} {action} {afi} {nexthop} {nlri_info["id"]}' + (' skip' if skip_attributes else '')

    return formatted


@pytest.fixture
def decode(monkeypatch: pytest.MonkeyPatch) -> Any:
    module = negotiation.interpreted(command)
    monkeypatch.setattr(module, '_hexa', lambda _payload: b'')
    monkeypatch.setattr(module, '_make_update', lambda _neighbor, _raw: object())
    monkeypatch.setattr(module, 'Response', SimpleNamespace(JSON=_Encoder))
    monkeypatch.setattr(module, 'format_flow_announce', _formatter('flow'))
    monkeypatch.setattr(module, 'format_mup_announce', _formatter('mup'))
    monkeypatch.setattr(module, 'format_mvpn_announce', _formatter('mvpn'))
    monkeypatch.setattr(module, 'format_attributes', lambda attrs: ['ATTRS'] if attrs else [])
    monkeypatch.setattr(module, 'format_withdraw_attributes', lambda _attrs: 'WATTRS')
    monkeypatch.setattr(module, 'has_extra_withdraw_attributes', lambda attrs: bool(attrs.get('extra')))
    monkeypatch.setattr(module, '_format_sr_policy_tunnel', lambda _sr: ['TUNNEL'])

    def decoded(message: dict[str, Any], generic: bool = False) -> list[str]:
        _Encoder.message = message
        commands: list[str] = module.decode_to_api_command('00', cast('Neighbor', object()), generic=generic)
        return commands

    return decoded


# ------------------------------------------------------------------------------ nothing to say


def test_an_update_the_encoder_renders_empty_gives_no_command(decode: Any) -> None:
    assert decode({}) == []


def test_generic_asks_the_encoder_for_generic_attributes(decode: Any) -> None:
    decode({}, generic=True)
    assert _Encoder.last is not None and _Encoder.last.generic_attribute_format is True


# ------------------------------------------------------------------------------ announcements


def test_the_end_of_rib_marker_as_a_string(decode: Any) -> None:
    assert decode({'announce': {'ipv6 unicast': {'null': ['eor']}}}) == ['announce eor ipv6 unicast']


def test_the_end_of_rib_marker_as_an_object(decode: Any) -> None:
    message = {'announce': {'ipv4 unicast': {'null': [{'eor': {'afi': 'ipv4', 'safi': 'mpls-vpn'}}]}}}
    assert decode(message) == ['announce eor ipv4 mpls-vpn']


def test_an_end_of_rib_object_without_a_family_says_nothing(decode: Any) -> None:
    assert decode({'announce': {'ipv4 unicast': {'null': [{'eor': 'x'}]}}}) == []


@pytest.mark.parametrize('label', [[100], [[100]]], ids=['flat', 'nested'])
def test_an_announced_label_is_its_first_value(decode: Any, label: list[Any]) -> None:
    message = {'announce': {'ipv4 nlri-mpls': {'1.1.1.1': [{'nlri': '10.0.0.0/24', 'label': label}]}}}
    assert decode(message) == ['announce route 10.0.0.0/24 next-hop 1.1.1.1 label 100']


def test_several_nlri_sharing_a_path_id_are_one_attributes_command(decode: Any) -> None:
    nlris = [{'nlri': 'a', 'path-information': '0.0.0.1'}, {'nlri': 'b', 'path-information': '0.0.0.1'}]
    message = {'announce': {'ipv4 unicast': {'1.1.1.1': nlris}}, 'attribute': {'origin': 'igp'}}
    assert decode(message) == ['announce attributes path-information 0.0.0.1 next-hop 1.1.1.1 ATTRS nlri a b']


def test_mcast_vpn_routes_of_one_next_hop_are_grouped(decode: Any) -> None:
    message = {'announce': {'ipv4 mcast-vpn': {'1.1.1.1': [{'id': 'a'}, {'id': 'b'}]}}}
    assert decode(message) == ['group mvpn announce ipv4 1.1.1.1 a ; mvpn announce ipv4 1.1.1.1 b']


def test_a_mcast_vpn_group_of_one_is_not_a_group(decode: Any) -> None:
    message = {'announce': {'ipv4 mcast-vpn': {'1.1.1.1': [{'id': 'a'}, {'id': 'b', 'none': True}]}}}
    assert decode(message) == ['mvpn announce ipv4 1.1.1.1 a']


def test_an_rtc_route_the_configuration_cannot_express_is_left_out(decode: Any) -> None:
    nlris = [{'prefix-length': 0}, {'origin': 65000, 'route-target': '65000:1'}]
    message = {'announce': {'ipv4 rtc': {'1.1.1.1': nlris}}}
    assert decode(message) == ['announce ipv4 rtc origin-as 65000 route-target 65000:1 next-hop 1.1.1.1']


def test_announcements_follow_the_family_order_of_the_update(decode: Any) -> None:
    message = {
        'announce': {
            'ipv4 flow': {'no-nexthop': [{'id': 'f'}]},
            'ipv6 mup': {'2001:db8::1': [{'id': 'm'}]},
            'l2vpn vpls': {'1.1.1.1': [{'rd': 'R', 'endpoint': 1, 'base': 2, 'offset': 3, 'size': 4}]},
            'ipv6 sr-policy': {'2001:db8::1': [{'distinguisher': 1, 'color': 2, 'endpoint': '2001:db8::2'}]},
        }
    }
    assert decode(message) == [
        'flow announce ipv4 no-nexthop f',
        'mup announce ipv6 2001:db8::1 m',
        'announce vpls rd R endpoint 1 base 2 offset 3 size 4 next-hop 1.1.1.1',
        'announce ipv6 sr-policy distinguisher 1 color 2 endpoint 2001:db8::2 next-hop 2001:db8::1 TUNNEL',
    ]


# ------------------------------------------------------------------------------ withdrawals


def test_an_rtc_withdrawal(decode: Any) -> None:
    nlris = [{'origin': 65000, 'route-target': '65000:1'}, {'prefix-length': 0}, 'junk']
    assert decode({'withdraw': {'ipv4 rtc': nlris}}) == ['withdraw ipv4 rtc origin-as 65000 route-target 65000:1']


def test_formatted_withdrawals_without_extra_attributes(decode: Any) -> None:
    message = {
        'withdraw': {'ipv4 flow': [{'id': 'f'}, 'junk'], 'ipv6 mup': [{'id': 'm'}], 'ipv4 mcast-vpn': [{'id': 'v'}]},
        'attribute': {'next-hop': '2.2.2.2'},
    }
    assert decode(message) == [
        'flow withdraw ipv4 2.2.2.2 f',
        'mup withdraw ipv6 2.2.2.2 m',
        'mvpn withdraw ipv4 2.2.2.2 v',
    ]


def test_formatted_withdrawals_with_extra_attributes_are_grouped(decode: Any) -> None:
    message = {
        'withdraw': {'ipv4 flow': [{'id': 'f'}], 'ipv6 mup': [{'id': 'm'}], 'ipv4 mcast-vpn': [{'id': 'v'}]},
        'attribute': {'extra': True},
    }
    assert decode(message) == [
        'group WATTRS ; flow withdraw ipv4 0.0.0.0 f skip',
        'group WATTRS ; mup withdraw ipv6 0.0.0.0 m skip',
        'group WATTRS ; mvpn withdraw ipv4 0.0.0.0 v skip',
    ]


def test_a_formatter_with_nothing_to_say_leaves_only_the_attributes(decode: Any) -> None:
    # no withdrawal was written, so the UPDATE is treated as carrying attributes alone
    message = {'withdraw': {'ipv4 flow': [{'id': 'f', 'none': True}]}, 'attribute': {'extra': True}}
    assert decode(message) == ['attributes ATTRS']


def test_an_sr_policy_withdrawal(decode: Any) -> None:
    nlris = [{'distinguisher': 1, 'color': 2, 'endpoint': '2001:db8::1'}, 'junk']
    message = {'withdraw': {'ipv6 sr-policy': nlris}}
    assert decode(message) == ['withdraw ipv6 sr-policy distinguisher 1 color 2 endpoint 2001:db8::1']


def test_a_vpls_withdrawal(decode: Any) -> None:
    nlris = [{'rd': 'R', 'endpoint': 1, 'base': 2, 'offset': 3, 'size': 4}, 'junk']
    message = {'withdraw': {'l2vpn vpls': nlris}}
    assert decode(message) == ['withdraw vpls rd R endpoint 1 base 2 offset 3 size 4 next-hop 0.0.0.0']


@pytest.mark.parametrize('label', [[100], [[100]]], ids=['flat', 'nested'])
def test_a_withdrawn_label_is_its_first_value(decode: Any, label: list[Any]) -> None:
    message = {'withdraw': {'ipv4 nlri-mpls': [{'nlri': '10.0.0.0/24', 'label': label}]}}
    assert decode(message) == ['withdraw route 10.0.0.0/24 label 100']


def test_a_withdrawal_with_extra_attributes_is_grouped(decode: Any) -> None:
    message = {'withdraw': {'ipv4 unicast': [{'nlri': '10.0.0.0/24', 'rd': 'R'}]}, 'attribute': {'extra': True}}
    assert decode(message) == ['group WATTRS ; withdraw route 10.0.0.0/24 rd R']


def test_a_withdrawal_given_as_a_string(decode: Any) -> None:
    assert decode({'withdraw': {'ipv6 unicast': ['2001:db8::/32']}}) == ['withdraw ipv6 unicast 2001:db8::/32']


# ------------------------------------------------------------------------------ attributes only


def test_an_update_with_only_attributes(decode: Any) -> None:
    assert decode({'attribute': {'origin': 'igp'}}) == ['attributes ATTRS']
