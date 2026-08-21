#!/usr/bin/env python3
# encoding: utf-8

"""BGP-LS JSON emission safety tests

The BGP-LS attribute is OPTIONAL|TRANSITIVE, so the TLV payloads below can be
originated several ASes away and reach us through peers we do trust.  They are
therefore untrusted input and must never be able to break, or inject into, the
line delimited JSON API stream.
"""

import json

import pytest

from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.link.linkname import LinkName
from exabgp.bgp.message.update.attribute.bgpls.link.opaque import LinkOpaque
from exabgp.bgp.message.update.attribute.bgpls.node.nodename import NodeName
from exabgp.bgp.message.update.attribute.bgpls.node.opaque import NodeOpaque
from exabgp.bgp.message.update.attribute.bgpls.prefix.opaque import PrefixOpaque


def emitted(*ls_attrs):
    """Render the attributes the way the JSON API does, and parse the result"""
    attributes = Attributes()
    attributes.add(LinkState(ls_attrs=list(ls_attrs)))
    line = attributes.json()
    assert len(line.splitlines()) == 1, 'the TLV split the line delimited stream'
    return json.loads('{' + line + '}')['bgp-ls']


class TestNameTlvEscaping:
    """A peer must not be able to inject JSON through a name TLV"""

    def test_link_name_quote_is_escaped(self) -> None:
        parsed = emitted(LinkName.unpack(b'legit", "forged-key": "owned'))
        assert parsed == {'link-name': 'legit", "forged-key": "owned'}
        assert 'forged-key' not in parsed

    def test_node_name_quote_is_escaped(self) -> None:
        parsed = emitted(NodeName.unpack(b'legit", "forged-key": "owned'))
        assert parsed == {'node-name': 'legit", "forged-key": "owned'}
        assert 'forged-key' not in parsed

    def test_opaque_prefix_quote_is_escaped(self) -> None:
        parsed = emitted(PrefixOpaque.unpack(b'a", "forged-key": "1'))
        assert parsed == {'opaque-prefix': 'a", "forged-key": "1'}
        assert 'forged-key' not in parsed

    @pytest.mark.parametrize(
        'payload',
        [
            b'one\ntwo',
            b'one\r\ntwo',
            b'trailing-backslash\\',
            b'back\\slash',
            b'bell\x07and\ttab',
        ],
    )
    def test_control_characters_keep_one_line(self, payload) -> None:
        """A raw newline used to split one API event into two stream lines"""
        parsed = emitted(LinkName.unpack(payload))
        assert parsed == {'link-name': payload.decode('utf-8')}


class TestNameTlvDecoding:
    """RFC 7752 mandates 7-bit ASCII, but a peer can send any bytes"""

    def test_node_name_non_ascii_does_not_raise(self) -> None:
        parsed = emitted(NodeName.unpack('réuter'.encode('utf-8')))
        assert parsed == {'node-name': 'réuter'}

    def test_node_name_invalid_utf8_does_not_raise(self) -> None:
        parsed = emitted(NodeName.unpack(b'bad\xff\xfename'))
        assert parsed['node-name'].startswith('bad')
        assert parsed['node-name'].endswith('name')

    def test_link_name_invalid_utf8_does_not_raise(self) -> None:
        parsed = emitted(LinkName.unpack(b'\xff\xfe'))
        assert parsed['link-name'] == '��'

    def test_as_dict_matches_json(self) -> None:
        for tlv in (NodeName.unpack(b'\xff\xfe'), LinkName.unpack(b'q"uote')):
            assert tlv.as_dict() == json.loads('{' + tlv.json() + '}')


class TestOpaqueLinkAttribute:
    """TLV 1097 did not subclass BaseLS, so unpacking it raised TypeError"""

    def test_opaque_link_unpacks(self) -> None:
        parsed = emitted(LinkOpaque.unpack(b'opaque'))
        assert parsed == {'opaque-link': 'opaque'}

    def test_opaque_link_quote_is_escaped(self) -> None:
        parsed = emitted(LinkOpaque.unpack(b'a", "forged-key": "1'))
        assert 'forged-key' not in parsed


class TestOpaqueNodeAttribute:
    """TLV 1025 overrode json() with json.dumps() on raw bytes, which raised TypeError"""

    def test_opaque_node_unpacks(self) -> None:
        parsed = emitted(NodeOpaque.unpack(b'opaque'))
        assert parsed == {'opaque': 'opaque'}

    def test_opaque_node_quote_is_escaped(self) -> None:
        parsed = emitted(NodeOpaque.unpack(b'a", "forged-key": "1'))
        assert 'forged-key' not in parsed

    def test_opaque_node_invalid_utf8_does_not_raise(self) -> None:
        parsed = emitted(NodeOpaque.unpack(b'\xff\xfe'))
        assert 'opaque' in parsed
