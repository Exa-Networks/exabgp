"""OTC route instructions survive static, API and schema-based family parsing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from exabgp.application import encode
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.attribute.otc import OTC, OTCSelf
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.configuration.setup import create_minimal_configuration
from exabgp.reactor.api import API
from exabgp.rib.route import Route


FORMS = ['1.1', 'self', 'provider', 'customer', 'peer', 'rs', 'rs-client']
FAMILIES = [
    ('route', '10.0.0.0/24 next-hop 192.0.2.1'),
    ('ipv4', 'unicast 10.0.0.0/24 next-hop 192.0.2.1'),
    ('ipv6', 'unicast 2001:db8::/32 next-hop 2001:db8::1'),
    ('ipv4', 'multicast 10.0.0.0/24 next-hop 192.0.2.1'),
    ('ipv6', 'multicast 2001:db8::/32 next-hop 2001:db8::1'),
    ('ipv4', 'nlri-mpls 10.0.0.0/24 next-hop 192.0.2.1 label 100'),
    ('ipv6', 'nlri-mpls 2001:db8::/32 next-hop 2001:db8::1 label 100'),
    ('ipv4', 'mpls-vpn 10.0.0.0/24 next-hop 192.0.2.1 label 100 rd 65000:1'),
    ('ipv6', 'mpls-vpn 2001:db8::/32 next-hop 2001:db8::1 label 100 rd 65000:1'),
]


def api_routes(family: str, body: str) -> list[Route]:
    api = API(Mock())
    parser = {'route': api.api_route, 'ipv4': api.api_announce_v4, 'ipv6': api.api_announce_v6}[family]
    return parser(f'{family} {body}', 'announce')


@pytest.mark.parametrize('family,body', FAMILIES)
@pytest.mark.parametrize('form', FORMS)
def test_otc_forms_through_api_family_parsers(family: str, body: str, form: str) -> None:
    routes = api_routes(family, f'{body} otc {form}')
    assert len(routes) == 1
    attributes = routes[0].attributes
    if form == '1.1':
        attribute = attributes[Attribute.CODE.OTC]
        assert isinstance(attribute, OTC)
        assert attribute.asn == 65537
        assert 'otc 65537' in str(attributes)
        assert json.loads('{' + attributes.json() + '}')['otc'] == 65537
    else:
        attribute = attributes[Attribute.CODE.OTC]
        assert isinstance(attribute, OTCSelf)
        assert attribute.role == (RoleValue.NO_ROLE if form == 'self' else RoleValue.from_string(form))
        assert f'otc {form}' in str(attributes)


@pytest.mark.parametrize('family,body', [FAMILIES[0], FAMILIES[1], FAMILIES[-1]])
# 'none' used to suppress the automatic marking for one route. RFC 9234 section 5 says the
# operator MUST NOT be able to modify these procedures, so it is refused like any other
# value which is not an ASN, self, or a role name.
@pytest.mark.parametrize(
    'value', ['', 'none', 'unknown', '-1', '+1', '4294967296', '65536.0', '1.65536', '1.1.1', '0x10']
)
def test_invalid_otc_is_rejected_by_route_parsers(family: str, body: str, value: str) -> None:
    assert api_routes(family, f'{body} otc {value}') == []


def configuration_text(form: str) -> str:
    role = f'role {{ local {form}; }}' if form in FORMS[2:] else ''
    return f"""
neighbor 192.0.2.1 {{
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65537;
    peer-as 65002;
    {role}
    family {{ ipv4 unicast; }}
    static {{ route 10.0.0.0/24 {{ next-hop 192.0.2.2; otc {form}; }} }}
}}
"""


@pytest.mark.parametrize('form', FORMS)
def test_static_block_preserves_explicit_otc_instruction(form: str) -> None:
    configuration = Configuration([configuration_text(form)], text=True)
    assert configuration.reload(), str(configuration.error)
    neighbor = next(iter(configuration.neighbors.values()))
    routes = list(neighbor.rib.outgoing.queued_routes())
    assert len(routes) == 1
    _, negotiated = _negotiated(neighbor)
    assert routes[0].attributes[Attribute.CODE.OTC].pack_attribute(negotiated) == b'\xc0\x23\x04\x00\x01\x00\x01'


def encode_args(arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    encode.setargs(parser)
    return parser.parse_args(arguments)


def decoded_attributes(output: str, family: str = 'ipv4 unicast') -> AttributeCollection:
    configuration = create_minimal_configuration(families=family)
    _, negotiated = _negotiated(next(iter(configuration.neighbors.values())))
    wire = bytes.fromhex(output.strip())
    return Update.unpack_message(wire[19:], negotiated).parse(negotiated).attributes


@pytest.mark.parametrize('form', ['self', 'provider', 'customer', 'peer', 'rs', 'rs-client'])
def test_inline_encode_rejects_session_dependent_otc(form: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        encode.cmdline(encode_args([f'route 10.0.0.0/24 next-hop 192.0.2.1 otc {form}']))
    assert error.value.code == 1
    assert 'encode -c' in capsys.readouterr().out


@pytest.mark.parametrize(
    'family,route',
    [
        ('ipv4 unicast', 'route 10.0.0.0/24 next-hop 192.0.2.1'),
        ('ipv6 unicast', 'route 2001:db8::/32 next-hop 2001:db8::1'),
    ],
)
def test_inline_encode_literal_otc(family: str, route: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert encode.cmdline(encode_args(['-f', family, f'{route} otc 1.1'])) == 0
    attribute = decoded_attributes(capsys.readouterr().out, family)[Attribute.CODE.OTC]
    assert isinstance(attribute, OTC)
    assert attribute.asn == 65537


@pytest.mark.parametrize('form', ['self', 'provider'])
def test_configured_encode_resolves_session_otc(form: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / 'otc.conf'
    path.write_text(configuration_text(form))
    assert encode.cmdline(encode_args(['-c', str(path)])) == 0
    attribute = decoded_attributes(capsys.readouterr().out)[Attribute.CODE.OTC]
    assert isinstance(attribute, OTC)
    assert attribute.asn == 65537


def test_configured_encode_reports_unresolved_otc_without_traceback(tmp_path: Path, capsys) -> None:
    path = tmp_path / 'otc-auto.conf'
    text = (
        configuration_text('self')
        .replace('local-as 65537;', 'local-as auto;')
        .replace('peer-as 65002;', 'peer-as auto;')
    )
    path.write_text(text)
    with pytest.raises(SystemExit) as error:
        encode.cmdline(encode_args(['-c', str(path)]))
    assert error.value.code == 1
    assert 'configuration error:' in capsys.readouterr().out


def test_configured_encode_resolves_auto_local_as_for_otc(tmp_path: Path, capsys) -> None:
    path = tmp_path / 'otc-auto.conf'
    text = (
        configuration_text('self')
        .replace('local-as 65537;', 'local-as auto;')
        .replace('peer-as 65002;', 'peer-as 65538;')
    )
    path.write_text(text)
    assert encode.cmdline(encode_args(['-c', str(path)])) == 0
    attributes = decoded_attributes(capsys.readouterr().out)
    assert attributes[Attribute.CODE.OTC].asn == 65538
