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
    """The RFC says ASCII; accepting anything else is our choice, not its permission

    RFC 9552 5.3.1.3 and 5.3.2.7, for Node Name and Link Name both: "The Value
    field is encoded in 7-bit ASCII. If a user interface for configuring or
    displaying this field permits Unicode characters, then the user interface is
    responsible for applying the ToASCII and/or ToUnicode algorithm as described
    in RFC 5890". So the conformant way to carry an accented hostname is the
    ToASCII form, xn--caf-dma-rtr1, and a peer putting raw UTF-8 on the wire is
    not following the RFC.

    We accept it anyway, and these tests hold that. The reason is proportion, not
    permission: the name is a descriptive field, and the alternative is raising
    from the decoder, which discards the WHOLE BGP-LS attribute and takes the
    router-ids, the metrics and the SIDs with it. Refusing an entire attribute
    over a cosmetic field is the worse failure.

    This branch decoded Node Name with data.decode('ascii') from November 2016
    until it was replaced by utf-8 with 'replace' in 6960a1859. That was a nine
    year old refusal, removed as part of the JSON escaping work rather than as a
    decision about encodings, which is exactly why it is pinned here.
    """

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

    def test_a_conformant_ascii_name_is_unchanged(self) -> None:
        """The half of the range the RFC actually specifies

        Every other test here feeds this decoder something the RFC does not
        allow, and a lenient decode is a superset, so nothing was checking that
        what the RFC DOES ask for still comes back untouched. ToASCII output is
        the conformant way to carry an accented hostname, so it is the case a
        real router following 5.3.1.3 puts on the wire.

        Suggested by the session working main, who added it after I pushed back
        on the encoding, and who was right that correcting the words was not
        enough on its own.
        """
        for name in (b'router1', b'xn--caf-dma-rtr1', b'core-1.example.net', b'a' * 255):
            assert emitted(NodeName.unpack(name)) == {'node-name': name.decode('ascii')}
            assert emitted(LinkName.unpack(name)) == {'link-name': name.decode('ascii')}

    def test_every_printable_ascii_byte_survives(self) -> None:
        # the whole 7 bit printable range in one name, quotes and backslashes
        # included, so the escaping cannot be confused with the decoding
        name = bytes(range(0x20, 0x7F))
        assert emitted(NodeName.unpack(name)) == {'node-name': name.decode('ascii')}

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
