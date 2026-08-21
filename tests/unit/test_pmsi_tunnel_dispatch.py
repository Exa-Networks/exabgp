#!/usr/bin/env python3
# encoding: utf-8

"""A PMSI tunnel identifier must match the class which decodes it

PMSIIngressReplication.prettytunnel() calls IPv4.ntop() on the tunnel
identifier, which needs exactly four bytes. The header check was five bytes, so
a seven byte PMSI decoded and then raised ValueError from str() and repr(), in
the API writer and in the logger.

The width decides which class can represent the bytes, not whether to accept
them: an attribute which decodes today must keep decoding after an upgrade.
"""

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.pmsi import PMSI


def decoded(hexs):
    return PMSI.unpack(bytes.fromhex(hexs), None, None)


class TestPmsiRenders:
    """Every accepted PMSI must survive str() and repr()"""

    @pytest.mark.parametrize(
        'hexs',
        [
            '0006000000c0a80101',  # ingress replication, a real IPv4 tunnel
            '0006000000ffff',  # ingress replication, too short for an IPv4
            '0006000000ff',
            '0000000000',  # no tunnel
            '000000000041424344',  # no tunnel, with bytes behind it
            '0009000000abcdef',  # a type we do not know
        ],
    )
    def test_renders_without_raising(self, hexs) -> None:
        attribute = decoded(hexs)
        assert str(attribute)
        assert repr(attribute)


class TestPmsiKeepsDecoding:
    """The width picks the class; nothing which decoded before is refused"""

    def test_a_valid_ingress_replication_keeps_its_address(self) -> None:
        assert '192.168.1.1' in str(decoded('0006000000c0a80101'))

    def test_a_tunnel_too_short_for_its_type_falls_back_to_hex(self) -> None:
        # this used to raise ValueError from str()
        assert '0xFFFF' in str(decoded('0006000000ffff'))

    def test_a_no_tunnel_with_trailing_bytes_still_decodes(self) -> None:
        # 5.0.12 accepted this and dropped the bytes; refusing it would be a
        # regression, so it decodes and the bytes are shown
        rendered = str(decoded('000000000041424344'))
        assert 'notunnel' in rendered
        assert '0x41424344' in rendered

    def test_an_unknown_tunnel_type_still_decodes(self) -> None:
        assert '0xABCDEF' in str(decoded('0009000000abcdef'))


class TestPmsiHeader:
    """A PMSI shorter than its own header is a protocol error"""

    @pytest.mark.parametrize('hexs', ['', '00', '0006', '000600', '00060000'])
    def test_truncated_header_is_a_notify(self, hexs) -> None:
        with pytest.raises(Notify):
            decoded(hexs)
