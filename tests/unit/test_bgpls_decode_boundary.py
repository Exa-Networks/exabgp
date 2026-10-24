#!/usr/bin/env python3
# encoding: utf-8

"""What the BGP-LS decode boundary must and must not do

The boundary converts a decoder's exception into a protocol error. Three
properties of it were changed without a test, which is how they are easy to
undo by accident:

  - it must convert only the exceptions that mean the PEER sent too little
  - it must not render, because that cost is paid per UPDATE for nothing
  - a malformed BGP-LS attribute must cost the attribute, not the session
"""

from struct import pack
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState


@pytest.fixture
def mocked_logger():
    """Attributes.parse logs, and the logger is not initialised under pytest"""
    from exabgp.logger.option import option

    saved = option.logger
    option.logger = Mock()
    yield
    option.logger = saved


class TestOnlyPeerErrorsAreConverted:
    """AttributeError and TypeError out of a decoder are OUR bug

    Converting them blames the peer and tears down a session carrying valid
    traffic. This series is the evidence: the SRv6 End.X __repr__ defect was
    found because its AttributeError escaped loudly.
    """

    @staticmethod
    def _decode_with(monkeypatch, exception):
        scode = sorted(LinkState.registered_lsids)[0]
        klass = LinkState.registered_lsids[scode]

        def raising(cls, data):
            raise exception

        monkeypatch.setattr(klass, 'unpack', classmethod(raising))
        return LinkState.unpack(pack('!HH', scode, 4) + b'\x00\x00\x00\x00', None, None)

    @pytest.mark.parametrize('exception', [AttributeError('ours'), TypeError('ours')])
    def test_our_own_bugs_escape(self, monkeypatch, exception) -> None:
        with pytest.raises(type(exception)):
            self._decode_with(monkeypatch, exception)

    @pytest.mark.parametrize('exception', [IndexError('short'), ValueError('short'), KeyError('short')])
    def test_peer_shortfalls_become_a_protocol_error(self, monkeypatch, exception) -> None:
        with pytest.raises(Notify):
            self._decode_with(monkeypatch, exception)


class TestTheBoundaryDoesNotRender:
    """Rendering at decode costs 1.6x per UPDATE for a result nothing keeps"""

    RENDERABLE_TLV = 1025  # NodeOpaque, which decodes any payload

    def test_decoding_never_calls_json(self, monkeypatch) -> None:
        scode = self.RENDERABLE_TLV
        klass = LinkState.registered_lsids[scode]
        calls = []
        original = klass.json

        def counting(self, compact=None):
            calls.append(1)
            return original(self, compact)

        monkeypatch.setattr(klass, 'json', counting)
        LinkState.unpack(pack('!HH', scode, 4) + b'\x00\x00\x00\x00', None, None)
        assert calls == [], 'the decode boundary rendered, which the API then does again'


class TestMalformedBgpLsIsDiscarded:
    """RFC 7752 section 5.3 and RFC 9552 section 7.2.1 ask for Attribute Discard"""

    def test_bgp_ls_is_in_the_discard_set(self) -> None:
        assert Attribute.CODE.BGP_LS in Attributes.DISCARD

    def test_a_bad_tlv_costs_the_attribute_not_the_peering(self, mocked_logger) -> None:
        # a TLV announcing more than it carries, wrapped as attribute 29
        bad_tlv = pack('!HH', 1153, 40) + b'\x00\x00'
        attribute = bytes([Attribute.Flag.OPTIONAL, Attribute.CODE.BGP_LS, len(bad_tlv)]) + bad_tlv

        attributes = Attributes()
        # it must not raise: the attribute is dropped and the UPDATE survives
        attributes.parse(attribute, None, None)
        assert Attribute.CODE.BGP_LS not in attributes
