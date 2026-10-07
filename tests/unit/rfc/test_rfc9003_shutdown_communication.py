"""RFC 9003, the Shutdown Communication carried by a Cease (6, 2) or (6, 4).

RFC 9003 obsoletes RFC 8203 and raises the longest communication from 128 octets to 255.
exabgp still refused anything over 128 on receipt, and sent its own text through an ASCII
encoder, so an operator's message with one accented letter raised instead of going out.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.notification import Notification, Notify

CEASE = 6
ADMINISTRATIVE_SHUTDOWN = 2
PEER_DECONFIGURED = 3
ADMINISTRATIVE_RESET = 4

# RFC 9003 3: the most we send without knowing the peer implements RFC 9003
LEGACY_LIMIT_OCTETS = 128
# the Length field is one octet
FIELD_LIMIT_OCTETS = 255


def received(subcode: int, communication: bytes) -> bytes:
    return Notification.make_notification(CEASE, subcode, bytes([len(communication)]) + communication).text


# ------------------------------------------------------------------- what we send


@pytest.mark.rfc('rfc9003#2-subcode-is-shutdown-or-reset')
@pytest.mark.parametrize('subcode', [ADMINISTRATIVE_SHUTDOWN, ADMINISTRATIVE_RESET])
def test_shutdown_and_reset_carry_a_length_prefixed_communication(subcode: int) -> None:
    assert Notify(CEASE, subcode, 'maintenance').data == b'\x0bmaintenance'


@pytest.mark.rfc('rfc9003#2-subcode-is-shutdown-or-reset', polarity='negative')
def test_another_cease_subcode_carries_no_length_octet() -> None:
    assert Notify(CEASE, PEER_DECONFIGURED, 'maintenance').data == b'maintenance'


@pytest.mark.rfc('rfc9003#2-communication-is-utf8')
def test_the_communication_is_encoded_in_utf8() -> None:
    communication = 'maintenance à 22h'.encode()
    assert (
        Notify(CEASE, ADMINISTRATIVE_SHUTDOWN, 'maintenance à 22h').data == bytes([len(communication)]) + communication
    )


@pytest.mark.rfc('rfc9003#3-no-longer-than-128-octets-unless-known')
def test_a_long_communication_is_cut_to_128_octets_on_a_character_boundary() -> None:
    sent = Notify(CEASE, ADMINISTRATIVE_SHUTDOWN, 'é' * 100).data  # 200 octets of two octet characters
    assert sent[0] == LEGACY_LIMIT_OCTETS
    assert sent[1:].decode('utf-8') == 'é' * (LEGACY_LIMIT_OCTETS // 2)


def test_no_communication_is_the_old_fashioned_empty_data_field() -> None:
    assert Notify(CEASE, ADMINISTRATIVE_SHUTDOWN).data == b''


# ---------------------------------------------------------------- what we receive


@pytest.mark.rfc('rfc9003#3-up-to-255-octets-may-be-sent')
def test_a_communication_longer_than_128_octets_is_accepted() -> None:
    """RFC 8203 capped it at 128; RFC 9003 lets a peer which knows we support it send 255."""
    decoded = received(ADMINISTRATIVE_SHUTDOWN, b'A' * FIELD_LIMIT_OCTETS)
    assert decoded == b'Shutdown Communication: "' + b'A' * FIELD_LIMIT_OCTETS + b'"'


@pytest.mark.rfc('rfc9003#2-must-not-interpret-invalid-utf8', polarity='negative')
@pytest.mark.parametrize('communication', [b'\x80\x81', b'\xc0\x80'], ids=['continuation', 'overlong'])
def test_invalid_utf8_is_reported_and_not_interpreted(communication: bytes) -> None:
    decoded = received(ADMINISTRATIVE_SHUTDOWN, communication)
    assert decoded.startswith(b'invalid Shutdown Communication (invalid UTF-8)')


@pytest.mark.rfc('rfc9003#2-must-not-interpret-invalid-utf8')
def test_valid_utf8_is_interpreted() -> None:
    assert received(ADMINISTRATIVE_RESET, 'réinitialisé'.encode()) == 'Shutdown Communication: "réinitialisé"'.encode()


@pytest.mark.rfc('rfc9003#2-shortest-form-required', polarity='negative')
def test_an_overlong_encoding_is_not_accepted() -> None:
    """C0 80 is an overlong NUL: the UTF-8 "Shortest Form" rule is what makes it invalid."""
    assert received(ADMINISTRATIVE_SHUTDOWN, b'\xc0\x80').startswith(b'invalid Shutdown Communication')


@pytest.mark.rfc('rfc9003#2-shortest-form-required')
def test_what_we_send_is_shortest_form() -> None:
    sent = Notify(CEASE, ADMINISTRATIVE_SHUTDOWN, 'é').data
    assert sent == b'\x02\xc3\xa9'


@pytest.mark.rfc('rfc9003#2-report-the-communication')
def test_a_utf8_communication_is_logged_as_text_not_hex() -> None:
    """The log line is str(): it decoded the text as ASCII, so one accented letter turned
    the whole communication into hex, which no operator reads."""
    notification = Notification.make_notification(CEASE, ADMINISTRATIVE_SHUTDOWN, b'\x0dmaintenance\xc3\xa9')

    assert str(notification) == 'Cease / Administrative Shutdown / Shutdown Communication: "maintenanceé"'


@pytest.mark.parametrize('control', [b'\x1b', b'\x00', b'\x07', b'\r\n'], ids=['escape', 'nul', 'bell', 'crlf'])
def test_a_control_character_in_a_communication_is_shown_as_a_space(control: bytes) -> None:
    """Valid UTF-8 can still carry a terminal escape: the text is shown, never interpreted."""
    decoded = received(ADMINISTRATIVE_SHUTDOWN, b'down' + control + b'now')

    assert decoded == b'Shutdown Communication: "down' + b' ' * len(control) + b'now"'


@pytest.mark.parametrize(
    'data', [b'\x1b[2Jcleared', b'tab\there', b'\x00\x01', b'caf\xc3\xa9'], ids=['escape', 'tab', 'nul', 'utf8']
)
def test_a_data_field_which_is_not_printable_ascii_is_shown_in_hex(data: bytes) -> None:
    """Outside 6/2 and 6/4 the Data field is shown as it is only when it is printable.

    The check ran on str(bytes), the repr, which is always printable: an escape sequence
    from the peer went to the log and the terminal as it was.
    """
    notification = Notification.make_notification(CEASE, PEER_DECONFIGURED, data)

    assert notification.text == ('0x' + data.hex().upper()).encode()
    assert str(notification).endswith('/ 0x' + data.hex().upper())


def test_a_printable_data_field_is_shown_as_it_is() -> None:
    notification = Notification.make_notification(CEASE, PEER_DECONFIGURED, b'removed by operator')

    assert notification.text == b'removed by operator'
