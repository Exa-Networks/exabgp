"""What the BGP-LS decode boundary must and must not do.

`LinkState._decode_tlv` is the seam between a TLV decoder and the reactor. Three
properties of it are stated only in its own comments, which is what makes them easy to
undo by accident:

  - it converts only the exceptions which mean the PEER sent too little. `IndexError` and
    `struct.error` are the two shapes a short read takes. `TypeError` and `AttributeError`
    out of a property are OUR bug, and renaming one of those a protocol error blames the
    peer and tears down a session carrying valid traffic. The missing
    `GenericSRId.pack_tlv` was found precisely because its `AttributeError` escaped loudly.

  - it does not render. It used to call `json()` on every TLV to prove it could be
    rendered, which cost 31x on the decode path for a result nothing keeps. The registry
    wide property tests hold the renders now.

  - a malformed BGP-LS attribute costs the attribute, not the peering. RFC 9552 7.2.1 asks
    for Attribute Discard, and `LinkState` carries the `DISCARD` flag which delivers it.

Ported from the 5.0 branch, where the same three properties are pinned and where the
converted set is `(IndexError, ValueError, KeyError)` because its decoders raise different
shapes.
"""

from __future__ import annotations

from struct import error as struct_error
from struct import pack

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.collection import AttributeCollection

# NodeOpaque, which decodes any payload, so it is the TLV to hang a render counter on.
RENDERABLE_TLV = 1025

# A TLV which declares forty bytes and carries two, so the decoder cannot read its value.
SHORT_TLV = pack('!HH', 1153, 40) + b'\x00\x00'

OURS = [AttributeError('ours'), TypeError('ours')]
THEIRS = [IndexError('short'), struct_error('short')]


def decode(data: bytes) -> Attribute:
    return LinkState.unpack_attribute(data, Negotiated.UNSET)


def one_tlv(code: int, width: int = 4) -> bytes:
    return pack('!HH', code, width) + bytes(width)


def raising_decoder(monkeypatch: pytest.MonkeyPatch, exception: Exception) -> int:
    """Make the lowest registered TLV decoder raise, and return its code."""
    code = sorted(LinkState.registered_lsids)[0]
    klass = LinkState.registered_lsids[code]

    def raising(cls: type, data: object) -> None:
        raise exception

    monkeypatch.setattr(klass, 'unpack_bgpls', classmethod(raising))
    return code


# =========================================== only a peer shortfall becomes a Notify


@pytest.mark.parametrize('exception', OURS, ids=lambda exc: type(exc).__name__)
def test_our_own_bug_escapes_rather_than_blaming_the_peer(
    monkeypatch: pytest.MonkeyPatch, exception: Exception
) -> None:
    code = raising_decoder(monkeypatch, exception)

    with pytest.raises(type(exception)):
        decode(one_tlv(code))


@pytest.mark.parametrize('exception', THEIRS, ids=lambda exc: type(exc).__name__)
def test_a_peer_shortfall_becomes_a_protocol_error(monkeypatch: pytest.MonkeyPatch, exception: Exception) -> None:
    code = raising_decoder(monkeypatch, exception)

    with pytest.raises(Notify):
        decode(one_tlv(code))


def test_a_notify_a_decoder_raised_itself_is_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """A decoder which already said what was wrong must not have its message replaced."""
    code = raising_decoder(monkeypatch, Notify(3, 5, 'the decoder said this itself'))

    with pytest.raises(Notify) as raised:
        decode(one_tlv(code))

    assert 'the decoder said this itself' in str(raised.value)


def test_the_patched_decoder_is_the_one_being_entered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Otherwise every assertion above could be passing for the wrong reason."""
    entered: list[int] = []
    code = sorted(LinkState.registered_lsids)[0]
    klass = LinkState.registered_lsids[code]
    original = klass.unpack_bgpls

    def counting(cls: type, data: object) -> object:
        entered.append(1)
        return original(data)

    monkeypatch.setattr(klass, 'unpack_bgpls', classmethod(counting))
    # The class states the width it wants, and feeding it another one refuses before the
    # decoder is entered, which is the same green-for-the-wrong-reason this test exists for.
    decode(one_tlv(code, klass.LEN or 4))

    assert entered, f'TLV {code} was never decoded, so the raising tests prove nothing'


# ==================================================== the boundary does not render


def test_decoding_never_calls_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rendering here costs 31x per attribute for a result the API then builds again."""
    klass = LinkState.registered_lsids[RENDERABLE_TLV]
    calls: list[int] = []
    original = klass.json

    def counting(self: object, compact: bool | None = None) -> str:
        calls.append(1)
        return original(self, compact)

    monkeypatch.setattr(klass, 'json', counting)
    decode(one_tlv(RENDERABLE_TLV))

    assert calls == [], 'the decode boundary rendered, which the API then does again'


def test_the_render_counter_can_actually_count() -> None:
    """A counter watching a method nothing calls would satisfy the test above."""
    klass = LinkState.registered_lsids[RENDERABLE_TLV]
    instance = klass.unpack_bgpls(bytes(4))

    assert instance.json(), f'TLV {RENDERABLE_TLV} renders nothing, so counting json() proves nothing'


# ============================ a malformed attribute costs the attribute, not the session


def test_bgp_ls_asks_for_an_attribute_discard() -> None:
    assert LinkState.DISCARD, 'RFC 9552 7.2.1 asks for Attribute Discard on a malformed BGP-LS'


def test_a_bad_tlv_costs_the_attribute_not_the_peering() -> None:
    wire = bytes([Attribute.Flag.OPTIONAL, Attribute.CODE.BGP_LS, len(SHORT_TLV)]) + SHORT_TLV

    # It must not raise: the attribute is dropped and the UPDATE survives.
    collection = AttributeCollection().parse(wire, Negotiated.UNSET)

    assert Attribute.CODE.BGP_LS not in collection


def test_the_bad_tlv_really_is_refused_on_its_own() -> None:
    """Otherwise the discard above could be swallowing a TLV which decodes fine."""
    with pytest.raises(Notify):
        decode(SHORT_TLV)
