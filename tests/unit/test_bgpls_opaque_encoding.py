"""BGP-LS carries two kinds of byte string and rendered them as one.

RFC 9552 splits them:

  a name        5.3.1.3 Node Name and 5.3.2.7 Link Name, "encoded in 7-bit ASCII",
                with RFC 5890 ToASCII the sender's job
  an envelope   5.3.1.5, 5.3.2.6 and 5.3.3.6 carry IGP TLVs which this decoder does not
                look into, so the payload is arbitrary binary

Both were reaching the API as text, and each was wrong in its own direction.

The names were the stricter half, and the RFC is on their side: a peer sending raw UTF-8
here is not conformant, and decode('ascii') was matching what the RFC asks for.  We accept
it anyway for proportion rather than permission.  A name is a descriptive field, and
refusing it from the decoder discards the whole BGP-LS attribute, so a router loses its
router-ids, its metrics and its SIDs over something cosmetic.  UTF-8 is a superset of
ASCII, so a conformant name is unaffected and only a non-conformant one is read leniently.
Link Name did not decode at all and left it to jsonable(), which is a fallback for values
nobody declared rather than a decision about this one.

The envelopes were the lossy half.  Their bytes went through the same fallback, which
decodes with 'replace', so anything which was not valid UTF-8 arrived as U+FFFD and the
value the peer sent could not be recovered from what we published.  TLV 1025 already
rendered hex, so the three opaque TLVs did not even agree with each other.
"""

from __future__ import annotations

import json as jsonlib
from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute

# code, name, and the JSON member it renders under
OPAQUE = [
    (1025, 'node opaque', 'opaque'),
    (1097, 'link opaque', 'opaque-link'),
    (1157, 'prefix opaque', 'opaque-prefix'),
]
NAMES = [
    (1026, 'node name', 'node-name'),
    (1098, 'link name', 'link-name'),
]

# bytes no text decoder can read, which is what the envelopes must carry unharmed
NOT_TEXT = bytes([0xFF, 0xFE, 0x80, 0x00, 0xC3])


def render(code: int, payload: bytes) -> dict:
    klass = Attribute.klass_by_id(Attribute.CODE.BGP_LS)
    assert klass is not None
    attribute = klass.unpack_attribute(pack('!HH', code, len(payload)) + payload, Negotiated.UNSET)
    return jsonlib.loads(attribute.json())


@pytest.mark.parametrize('code, name, member', OPAQUE, ids=[row[1] for row in OPAQUE])
def test_an_opaque_payload_survives_bytes_which_are_not_text(code: int, name: str, member: str) -> None:
    """The value the peer sent must be recoverable from what we published.

    'replace' satisfies "did not crash" and "is valid JSON" while destroying the payload,
    which is why this asserts the round trip rather than that the render parses.
    """
    document = render(code, NOT_TEXT)

    assert member in document, f'{name} rendered nothing under {member}'
    assert bytes.fromhex(document[member]) == NOT_TEXT, f'{name} could not return the bytes the peer sent'


@pytest.mark.parametrize('code, name, member', OPAQUE, ids=[row[1] for row in OPAQUE])
def test_the_three_opaque_tlvs_agree_with_each_other(code: int, name: str, member: str) -> None:
    """One rendered hex and two rendered text, for the same kind of payload."""
    payload = bytes([0xDE, 0xAD, 0xBE, 0xEF])

    assert render(code, payload)[member] == payload.hex(), f'{name} does not render hex'


@pytest.mark.parametrize('code, name, member', NAMES, ids=[row[1] for row in NAMES])
def test_a_name_the_rfc_does_not_allow_is_read_rather_than_refused(code: int, name: str, member: str) -> None:
    """RFC 9552 asks for 7-bit ASCII here, so this name is NOT conformant.

    It is accepted for proportion, not permission: the alternative is discarding the
    whole BGP-LS attribute, and routers put UTF-8 on the wire whatever the RFC says.
    The name being non-conformant is the point of the test, not an oversight in it.
    """
    document = render(code, 'café-rtr1'.encode('utf-8'))

    assert document[member] == 'café-rtr1', f'{name} refuses a non-conformant name outright'


@pytest.mark.parametrize('code, name, member', NAMES, ids=[row[1] for row in NAMES])
def test_a_conformant_ascii_name_is_unchanged(code: int, name: str, member: str) -> None:
    """The lenient decode must not have altered what the RFC actually asks for.

    UTF-8 is a superset of ASCII, so the conformant spelling of an accented name, its
    RFC 5890 punycode, has to come back byte for byte.
    """
    document = render(code, b'xn--caf-dma-rtr1')

    assert document[member] == 'xn--caf-dma-rtr1', f'{name} altered a conformant ASCII name'


@pytest.mark.parametrize('code, name, member', NAMES, ids=[row[1] for row in NAMES])
def test_a_name_which_is_not_utf8_is_neither_refused_nor_fatal(code: int, name: str, member: str) -> None:
    """A name we cannot read is not a reason to drop the rest of the attribute.

    Text is the one place replacement is the right answer: there is no encoding which makes
    an unreadable name readable, and the other TLVs in the attribute are still good.
    """
    document = render(code, NOT_TEXT)

    assert member in document, f'{name} was refused for carrying bytes which are not text'
    assert isinstance(document[member], str)


@pytest.mark.parametrize('code', [row[0] for row in OPAQUE + NAMES], ids=[row[1] for row in OPAQUE + NAMES])
def test_a_peer_cannot_choose_a_member_of_the_api_stream(code: int) -> None:
    """The rule GHSA-jcrv-p53f-v5w5 was about, held for both categories.

    Hex is the stronger of the two positions: an escaped string still has to be escaped
    correctly, and hex has no quotes to escape.
    """
    document = render(code, b'x", "injected": "owned')

    assert 'injected' not in document, 'a peer chose a key in the API stream'
    assert len(document) == 1


def test_an_ascii_only_gate_is_not_back_on_the_name_tlvs() -> None:
    """The refusal this replaced was a Notify raised at decode, so it is asserted there.

    A later change which reinstates an encoding gate would make the rendering tests above
    skip rather than fail, if they caught Notify.  They do not, and this says why.
    """
    for code, name, _member in NAMES:
        try:
            render(code, 'café'.encode('utf-8'))
        except Notify as notify:
            pytest.fail(f'{name} refuses a valid UTF-8 name: {notify}')
