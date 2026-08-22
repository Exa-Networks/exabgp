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

    def test_the_text_encoder_keeps_the_name_it_neutralised(self) -> None:
        """Deleting the newline also satisfies the assertion above

        A fix which stripped the offending character, or dropped the value
        entirely, passes "no newline in the output" perfectly. This is the half
        which says the operator can still see what the peer called itself.
        """
        from exabgp.bgp.message.open.capability.capability import decode_utf8
        from exabgp.reactor.api.response.text import Text

        rendered = Text('5.0.12').oneline(decode_utf8(self.FORGED, 'host name'))
        assert 'victim' in rendered
        assert 'forged' in rendered
        assert '\\x0a' in rendered, 'the newline should be escaped, not removed'

    def test_the_json_encoder_neutralises_it(self) -> None:
        from exabgp.bgp.message.open.capability.capability import decode_utf8
        from exabgp.bgp.message.open.capability.hostname import HostName

        capability = HostName(decode_utf8(self.FORGED, 'host name'), 'example.com')
        parsed = json.loads('{ "capability": ' + capability.json() + ' }')
        assert sorted(parsed['capability']) == ['domain-name', 'host-name']

    def test_the_json_encoder_keeps_the_name_it_neutralised(self) -> None:
        """The keys surviving says nothing about the value

        Asserting only that both members are present passes for an encoder which
        emits "host-name": "" , or which strips the newline out of the middle of
        the name. Escaping and deleting are different fixes and only this tells
        them apart.

        The question came from the session working main, who found their
        operational advisory tested with a single string which could not fail,
        and measured that sanitising-by-deleting passes a corruption check and
        fails only a round trip.
        """
        from exabgp.bgp.message.open.capability.capability import decode_utf8
        from exabgp.bgp.message.open.capability.hostname import HostName

        decoded = decode_utf8(self.FORGED, 'host name')
        capability = HostName(decoded, 'example.com')
        parsed = json.loads('{ "capability": ' + capability.json() + ' }')
        assert parsed['capability']['host-name'] == decoded
        assert parsed['capability']['domain-name'] == 'example.com'


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


class TestTheShutdownCommunicationIsFlattenedOnPurpose:
    """A sanitise-by-deleting which is deliberate, and said so nowhere

    RFC 9003 shutdown communication is text the peer chose. Both paths that
    render it replace CR and LF with spaces rather than escaping them:

        data[:length].decode('utf-8').replace('\r', ' ').replace('\n', ' ')

    That is the shape this series has been treating as a defect everywhere else,
    and here it is a display choice: the message is meant to be one line for an
    operator, the same reason the text encoder has oneline(). Both the decoder
    and the transcoder do it identically, so a consumer sees the same thing
    either way.

    It is pinned rather than changed because the encoder now escapes correctly,
    which makes the replace redundant for JSON, which makes it look exactly like
    a bug to the next person applying the escaping lens. Turning it into escaping
    would change what every operator sees on a shutdown, and that is a decision
    rather than a cleanup.

    The distinction this file exists to hold: a peer must not be able to FORGE a
    line, and that is served by escaping. Whether a multi-line human message is
    flattened for display is a different question with a different answer.
    """

    @staticmethod
    def shutdown(text):
        from exabgp.bgp.message.notification import Notification

        encoded = text.encode('utf-8')
        return Notification.unpack_message(bytes([6, 2, len(encoded)]) + encoded)

    def test_a_newline_becomes_a_space(self) -> None:
        data = self.shutdown('maintenance\nwindow')
        rendered = data.data.decode() if isinstance(data.data, bytes) else str(data.data)
        assert '\n' not in rendered
        assert 'maintenance window' in rendered

    def test_the_exact_flattened_text(self) -> None:
        # The exact text, rather than two properties of it.
        #
        # I added this believing the two assertions above let a strip-rather-than
        # -space implementation through, and they do not: 'maintenance window' is
        # spelled with the space, so it is already absent from 'maintenancewindow'
        # and the words-survive assertion fails. I claimed otherwise without
        # running it, which is the whole failure this series keeps finding, made
        # while writing the fix for a neighbouring instance of it.
        #
        # It stays because the exact string is the honest statement of a display
        # choice: what an operator sees is the thing being pinned, and two
        # properties of it are a description. The carriage return case below is
        # the gap that WAS real, and no measurement was needed to see it, because
        # nothing in the tree passed a \r at all.
        data = self.shutdown('maintenance\nwindow')
        rendered = data.data.decode() if isinstance(data.data, bytes) else str(data.data)
        assert rendered == 'Shutdown Communication: "maintenance window"'

    def test_a_carriage_return_is_flattened_too(self) -> None:
        # the replace handles \r as well as \n, and only \n was pinned
        data = self.shutdown('maintenance\r\nwindow')
        rendered = data.data.decode() if isinstance(data.data, bytes) else str(data.data)
        assert rendered == 'Shutdown Communication: "maintenance  window"'

    def test_the_words_survive_the_flattening(self) -> None:
        # the half which separates flattening from discarding: an implementation
        # which dropped the message entirely also has no newline in it
        data = self.shutdown('urgent\nreboot at 0300')
        rendered = data.data.decode() if isinstance(data.data, bytes) else str(data.data)
        assert 'urgent' in rendered
        assert 'reboot at 0300' in rendered

    def test_a_quote_in_it_cannot_forge_a_member(self) -> None:
        # flattening is a display choice; NOT being forgeable is the property
        # this file is about, and it is the encoder's job rather than the
        # replace's
        from exabgp.reactor.api.response.json import JSON

        data = self.shutdown('x", "injected": "owned')
        rendered = data.data.decode() if isinstance(data.data, bytes) else str(data.data)
        line = JSON('5.0.0')._string(rendered)
        assert json.loads('{"shutdown": %s}' % line)['shutdown'] == rendered
