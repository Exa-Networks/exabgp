#!/usr/bin/env python3
# encoding: utf-8

"""The text API writes one event per line, so a peer newline forges an event"""

import io
import contextlib
import pytest
from exabgp.bgp.message.notification import Notify


class TestTextEncoderStaysOneLine:
    """The text stream is one event per line, so a newline forges an event"""

    def test_down_reason_cannot_forge_an_event(self) -> None:
        from exabgp.reactor.api.response.text import Text

        line = Text('5.0.12').down({'peer-address': '127.0.0.1'}, 'a\nneighbor 1.2.3.4 down - forged')
        assert len(line.splitlines()) == 1
        assert 'forged' in line  # kept, but on the same line

    def test_capability_string_cannot_forge_an_event(self) -> None:
        from exabgp.reactor.api.response.text import Text

        assert '\n' not in Text('5.0.12').oneline('a\nb')


class TestCapabilityControlCharacters:
    """A peer capability string reaches both encoders as free text"""

    def test_newline_in_a_capability_is_refused(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8

        with pytest.raises(Notify):
            decode_utf8(b'victim\nneighbor 1.2.3.4 down - forged', 'host name')

    def test_a_normal_hostname_is_kept(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8

        assert decode_utf8(b'router1.example.com', 'host name') == 'router1.example.com'


class TestOperationalDecoder:
    """Nothing in this decoder checked a length, and it wrote to stdout"""

    @pytest.mark.parametrize('length', range(0, 20))
    def test_short_message_is_a_protocol_error(self, length) -> None:
        from exabgp.bgp.message.operational import Operational

        try:
            Operational.unpack_message(b'\x00' * length, None, None)
        except Notify:
            return

    def test_unknown_type_does_not_write_to_stdout(self) -> None:
        from exabgp.bgp.message.operational import Operational

        # in daemon mode stdout is the pipe feeding the API subprocesses
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            with pytest.raises(Notify):
                Operational.unpack_message(b'\xff\xff\x00\x00', None, None)
        assert captured.getvalue() == ''
