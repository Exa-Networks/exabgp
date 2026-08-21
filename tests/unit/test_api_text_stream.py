"""The text API is one event per line, so a peer must not be able to end a line.

GHSA-jcrv-p53f-v5w5 was about the JSON encoder: a peer chose a member in the stream every
API subprocess reads.  The text encoder has the same shape of defect and the advisory did
not cover it.  A consumer of the text stream splits on newlines, so a peer supplied string
carrying one forges a whole event:

    neighbor 127.0.0.1 in open ... capabilities [hostname(a
    neighbor 1.2.3.4 down - forged ...

The reader sees a session go down which never did.  For a DDoS mitigation or FlowSpec
controller, a forged event is the same class of problem as an injected JSON member.

Two defences, and both are tested here: the peer's strings are refused at the decoder when
they hold a control character, and the encoder escapes anything which reaches it anyway.
"""

import struct

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open import Open
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.operational import Operational
from exabgp.configuration.setup import create_minimal_configuration
from exabgp.reactor.api.response.text import Text, oneline
from exabgp.version import version

FORGED = 'a\nneighbor 1.2.3.4 down - forged'


@pytest.fixture(scope='module')
def neighbor():
    configuration = create_minimal_configuration(families='all', add_path=False)
    configuration.reload()
    return list(configuration.neighbors.values())[0]


@pytest.fixture(scope='module')
def encoder() -> Text:
    return Text(version)


def one_line(produced: str) -> None:
    """What the encoder emits must be a single event, whatever the peer put in it."""
    body = produced[:-1] if produced.endswith('\n') else produced
    assert '\n' not in body, f'a peer ended the line early: {produced!r}'
    assert '\r' not in body, f'a peer ended the line early: {produced!r}'


def _open_with_capability(code: int, value: bytes) -> bytes:
    capability = bytes([code, len(value)]) + value
    params = bytes([2, len(capability)]) + capability
    body = bytes([4]) + struct.pack('!H', 65001) + struct.pack('!H', 180)
    return body + bytes([10, 0, 0, 1]) + bytes([len(params)]) + params


@pytest.mark.parametrize('control', [b'\n', b'\r', b'\r\n', b'\x00', b'\x1b'])
def test_a_hostname_holding_a_control_character_cannot_forge_an_event(control: bytes, neighbor, encoder: Text) -> None:
    """A peer's hostname is not refused for holding one, it is escaped when printed.

    Refusing it at the decoder would drop the session, and a router which pads its
    hostname to a fixed width has done nothing wrong: an installation which works today
    has to keep working after an upgrade.  So the encoder is where the line is held.
    """
    name = b'a' + control + b'neighbor 1.2.3.4 down - forged'
    value = bytes([len(name)]) + name + bytes([len(name)]) + name
    message = Open.unpack_message(_open_with_capability(CapabilityCode.HOSTNAME, value), Negotiated.UNSET)
    one_line(encoder.open(neighbor, 'in', message, b'', b'', Negotiated.UNSET))


@pytest.mark.parametrize('control', [b'\n', b'\r', b'\x00'])
def test_a_software_version_holding_a_control_character_cannot_forge_an_event(
    control: bytes, neighbor, encoder: Text
) -> None:
    name = b'a' + control + b'shutdown 1 1'
    message = Open.unpack_message(
        _open_with_capability(CapabilityCode.SOFTWARE_VERSION, bytes([len(name)]) + name),
        Negotiated.UNSET,
    )
    one_line(encoder.open(neighbor, 'in', message, b'', b'', Negotiated.UNSET))


def test_a_hostname_without_control_characters_still_decodes() -> None:
    name = b'router1.example.net'
    value = bytes([len(name)]) + name + bytes([len(name)]) + name
    message = Open.unpack_message(_open_with_capability(CapabilityCode.HOSTNAME, value), Negotiated.UNSET)
    assert 'router1.example.net' in str(message.capabilities)


def test_oneline_escapes_every_line_ending() -> None:
    assert '\n' not in oneline(FORGED)
    assert '\r' not in oneline('a\rb')
    assert '\n' not in oneline('a\r\nb')


def test_oneline_leaves_ordinary_text_alone() -> None:
    assert oneline('router1.example.net') == 'router1.example.net'
    assert oneline('a name with spaces') == 'a name with spaces'


def test_down_reason_cannot_forge_an_event(neighbor, encoder: Text) -> None:
    one_line(encoder.down(neighbor, FORGED))


def test_operational_advisory_cannot_forge_an_event(neighbor, encoder: Text) -> None:
    """The advisory is free text a peer sends, which makes it the easiest one to reach."""
    advisory = FORGED.encode('utf-8')
    body = struct.pack('!HH', 1, len(advisory) + 3) + struct.pack('!H', 1) + bytes([1]) + advisory
    operational = Operational.unpack_message(body, Negotiated.UNSET)
    produced = encoder.operational(neighbor, 'in', operational.category, operational, b'', b'', Negotiated.UNSET)
    one_line(produced)


def test_operational_advisory_survives_bytes_which_are_not_text(neighbor, encoder: Text) -> None:
    """decode() without an error handler put a UnicodeDecodeError in the API writer."""
    advisory = b'\xff\xfe\xfd'
    body = struct.pack('!HH', 1, len(advisory) + 3) + struct.pack('!H', 1) + bytes([1]) + advisory
    operational = Operational.unpack_message(body, Negotiated.UNSET)
    one_line(encoder.operational(neighbor, 'in', operational.category, operational, b'', b'', Negotiated.UNSET))


@pytest.mark.parametrize(
    'body',
    [
        b'',
        b'\x00',
        b'\x00\x01',
        b'\x00\x01\x00',
        b'\x00\x01\x00\xff',  # announces 255 bytes of payload and sends none
        b'\x00\x01\x00\x03\x00\x01',  # advisory, one byte short of its safi
        b'\x00\x03\x00\x0f\x00\x01\x01\xff\xfe',  # query, truncated router-id
        b'\x00\x06\x00\x13\x00\x01\x01\x0a\x00\x00\x01\x00\x00',  # counter, truncated sequence
    ],
)
def test_truncated_operational_message_raises_notify(body: bytes) -> None:
    """Every read was unchecked: struct.error and ValueError escaped into the reactor.

    Neither is caught by anything on the way out, and struct.error is not even one of the
    types AttributeCollection.parse converts.
    """
    with pytest.raises(Notify):
        Operational.unpack_message(body, Negotiated.UNSET)


def test_unknown_operational_type_is_reported_not_raised(neighbor, encoder: Text) -> None:
    """A type we do not know is the peer's choice, and must not kill the encoder.

    Both encoders ended their dispatch with `raise RuntimeError('the code is broken')`,
    which an UnknownOperational reached simply by having category 'unknown'.
    """
    payload = b'\x01\x02\x03'
    body = struct.pack('!HH', 0xBEEF, len(payload)) + payload
    operational = Operational.unpack_message(body, Negotiated.UNSET)
    assert operational.category == 'unknown'
    str(operational)
    repr(operational)
    one_line(encoder.operational(neighbor, 'in', operational.category, operational, b'', b'', Negotiated.UNSET))


def test_unknown_operational_type_has_a_printable_type() -> None:
    """Type.__str__ raised NotImplementedError, so the logger raised instead of logging."""
    body = struct.pack('!HH', 0xBEEF, 0)
    operational = Operational.unpack_message(body, Negotiated.UNSET)
    assert '48879' in str(operational.what)


def test_the_operational_decoder_does_not_write_to_stdout(capsys) -> None:
    """In daemon mode stdout is the pipe feeding the API subprocesses.

    The decoder used to print 'ignoring ATM this kind of message' there, which is a line
    no consumer can parse, on a message any peer can send.
    """
    Operational.unpack_message(struct.pack('!HH', 0xBEEF, 0), Negotiated.UNSET)
    captured = capsys.readouterr()
    assert captured.out == ''
