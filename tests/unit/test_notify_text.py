"""What a Notify says, to our log and to the peer.

A Notify carries two things which used to be one.  The *detail* is our explanation, for
str() and so for the log: it is appended to the IANA names of the code and subcode, so a
caller only writes what the names do not already say.  The *data* is the NOTIFICATION Data
field, whose content several RFCs define (RFC 4271 6.1 wants the erroneous Length field
for a Bad Message Length, RFC 7313 5 the complete ROUTE-REFRESH message).  When the caller
gives data, the octets go to the peer and the detail stays local.  When it does not, the
detail goes to the peer as text, as it always has, and nothing is invented to fill it.
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.extended import ExtendedMessage
from exabgp.bgp.message.open.capability.negotiated import Negotiated


def test_the_detail_is_appended_to_the_iana_names() -> None:
    notify = Notify(3, 5, 'OTC is 3 bytes, need 4')
    assert str(notify) == 'UPDATE Message Error / Attribute Length Error: OTC is 3 bytes, need 4'


def test_subcode_zero_is_named_by_its_code_alone() -> None:
    """ "OPEN Message Error / Unspecific: ..." says Unspecific and nothing else."""
    assert str(Notify(2, 0, 'ADD-PATH capability truncated')) == 'OPEN Message Error: ADD-PATH capability truncated'


def test_with_no_detail_the_names_are_the_whole_text() -> None:
    assert str(Notify(6, 3)) == 'Cease / Peer De-configured'


def test_without_data_the_detail_is_what_the_peer_reads() -> None:
    assert Notify(3, 5, 'OTC is 3 bytes, need 4').data == b'OTC is 3 bytes, need 4'


def test_with_no_detail_the_peer_gets_an_empty_data_field() -> None:
    """The peer already has the code and subcode; spelling their names back to it adds nothing."""
    assert Notify(6, 3).data == b''


def test_data_is_sent_and_the_detail_stays_local() -> None:
    notify = Notify(1, 2, 'KEEPALIVE of 20 octets', data=b'\x00\x14')
    assert notify.data == b'\x00\x14'
    assert str(notify) == 'Message Header Error / Bad Message Length: KEEPALIVE of 20 octets'


def test_data_with_no_detail() -> None:
    notify = Notify(1, 2, data=b'\x00\x14')
    assert notify.data == b'\x00\x14'
    assert str(notify) == 'Message Header Error / Bad Message Length'


def test_a_detail_which_is_not_ascii_does_not_stop_the_notification() -> None:
    """A Notify raised while handling an error must not itself raise on its own text."""
    notify = Notify(3, 10, 'préfixe')
    assert notify.data.isascii()
    assert str(notify).endswith('préfixe')


def test_the_detail_on_the_wire_is_bounded_so_the_message_fits() -> None:
    notify = Notify(3, 1, 'x' * 10000)
    assert len(notify.notification.pack_message(Negotiated.UNSET)) <= ExtendedMessage.INITIAL_SIZE
    assert str(notify).endswith('x' * 10000), 'the log keeps what the wire had to cut'


def test_the_wire_message_is_marker_length_type_code_subcode_data() -> None:
    packed = Notify(4, 0, 'late').notification.pack_message(Negotiated.UNSET)
    assert packed[19:] == b'\x04\x00late'


def test_short_says_what_was_needed_and_what_arrived() -> None:
    """Sixty seven call sites wrote this sentence by hand, in a dozen wordings."""
    notify = Notify.short(3, 10, 'EVPN NLRI', 40, 12)
    assert (notify.code, notify.subcode) == (3, 10)
    assert str(notify) == 'UPDATE Message Error / Invalid Network Field: EVPN NLRI needs 40 octets, got 12'
    assert notify.data == b'EVPN NLRI needs 40 octets, got 12'
