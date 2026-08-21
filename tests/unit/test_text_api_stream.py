#!/usr/bin/env python3
# encoding: utf-8

"""The text API writes one event per line, so a peer newline forges an event

The advisory covered the JSON encoder. The text encoder has the same class of
problem with a different shape: a newline in peer supplied text does not inject
a member, it fabricates a whole event line for whatever reads the stream.

Nothing here refuses a session. A router with an odd hostname must keep working;
the encoders are what make its text safe.
"""

import io
import json
import contextlib

import pytest

from exabgp.bgp.message.notification import Notify


class TestTextEncoderStaysOneLine:
    def test_down_reason_cannot_forge_an_event(self) -> None:
        from exabgp.reactor.api.response.text import Text

        line = Text('5.0.12').down({'peer-address': '127.0.0.1'}, 'a\nneighbor 1.2.3.4 down - forged')
        assert len(line.splitlines()) == 1
        assert 'forged' in line  # kept, but on the line it belongs to

    def test_capability_string_cannot_forge_an_event(self) -> None:
        from exabgp.reactor.api.response.text import Text

        assert '\n' not in Text('5.0.12').oneline('a\nb')

    def test_ordinary_text_is_untouched(self) -> None:
        from exabgp.reactor.api.response.text import Text

        assert Text('5.0.12').oneline('router1.example.com') == 'router1.example.com'


class TestCapabilityControlCharacters:
    """A peer capability string reaches both encoders as free text"""

    FORGED = b'victim\nneighbor 1.2.3.4 down - forged'

    def test_an_odd_hostname_still_decodes(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8

        # refusing it would drop sessions which come up today
        assert decode_utf8(self.FORGED, 'host name')

    def test_a_normal_hostname_is_kept(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8

        assert decode_utf8(b'router1.example.com', 'host name') == 'router1.example.com'

    def test_invalid_utf8_is_a_protocol_error(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8

        with pytest.raises(Notify):
            decode_utf8(b'\xff\xfe', 'host name')

    def test_the_text_encoder_neutralises_it(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8
        from exabgp.reactor.api.response.text import Text

        assert '\n' not in Text('5.0.12').oneline(decode_utf8(self.FORGED, 'host name'))

    def test_the_json_encoder_neutralises_it(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8
        from exabgp.bgp.message.open.capability.hostname import HostName

        capability = HostName(decode_utf8(self.FORGED, 'host name'), 'example.com')
        parsed = json.loads('{ "capability": ' + capability.json() + ' }')
        assert sorted(parsed['capability']) == ['domain-name', 'host-name']


class TestAddPathUnknownSendReceive:
    """RFC 7911 defines 1, 2 and 3, and a peer can send anything else"""

    def test_unknown_value_still_negotiates(self) -> None:
        from exabgp.bgp.message.open.capability.addpath import AddPath

        # the value is consumed as a bitmask, so refusing it would change which
        # sessions come up
        instance = AddPath.unpack_capability(AddPath(), bytes.fromhex('00010167'))
        assert instance

    def test_unknown_value_renders_without_raising(self) -> None:
        from exabgp.bgp.message.open.capability.addpath import AddPath

        # this used to raise KeyError from the API writer and from the logger
        instance = AddPath.unpack_capability(AddPath(), bytes.fromhex('00010167'))
        json.loads('{ "capability": ' + instance.json() + ' }')
        assert '103' in str(instance)

    def test_a_truncated_entry_is_a_protocol_error(self) -> None:
        from exabgp.bgp.message.open.capability.addpath import AddPath

        with pytest.raises(Notify):
            AddPath.unpack_capability(AddPath(), bytes.fromhex('000101'))


class TestOperationalDecoder:
    """Nothing in this decoder checked a length, and it wrote to stdout"""

    @pytest.mark.parametrize('length', range(0, 20))
    def test_short_message_never_raises_a_python_exception(self, length) -> None:
        from exabgp.bgp.message.operational import Operational

        try:
            Operational.unpack_message(b'\x00' * length, None, None)
        except Notify:
            return

    def test_unknown_type_is_ignored_without_writing_to_stdout(self) -> None:
        from exabgp.bgp.message.operational import Operational

        # an unknown type has always been ignored and must stay ignored, but in
        # daemon mode stdout is the pipe feeding the API subprocesses, so the
        # report must not go there
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            assert Operational.unpack_message(b'\xff\xff\x00\x00', None, None) is None
        assert captured.getvalue() == ''
