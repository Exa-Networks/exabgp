"""Property tests over every registered BGP-LS attribute TLV.

Attribute 29 is dispatched by attribute code with no address family gate, so a peer can
attach a BGP-LS attribute to a plain IPv4 unicast UPDATE without BGP-LS ever having been
negotiated.  Every TLV payload below is therefore untrusted input, and the TLV decoders are
reachable from any session at all.

The sweep is parametrised FROM `LinkState.registered_lsids`, so a TLV registered next year
is covered the day it is added rather than the day someone remembers to test it.  That is
also why `LSID_FLOOR` exists: a parametrised sweep over a registry which failed to fill does
not go red, it collects fewer cases and reports the same green line.

Four properties, and each one is a rule about the decode boundary rather than about output
text:

1. malformed input raises `Notify`, never a Python exception
2. a TLV which decodes can be rendered, every way the API writer and the logger render it
3. what `json()` emits is one parseable line, with no member the peer chose
4. the length of a recognised TLV's sub-TLVs is validated, RFC 9552 section 8.2.2

Everything is driven through `LinkState.unpack_attribute`, which is the path
`AttributeCollection.parse` takes.  It is not driven through `AttributeCollection` itself:
`LinkState.DISCARD` is True, so the collection converts a `Notify` into an
`INTERNAL_DISCARD` marker and an absent attribute, and a crash would then be indistinguishable
from a refusal.  Asking the attribute directly is what lets a refusal and a defect be told
apart.

The BGP-LS seeds are defined here rather than imported.  5.0 keeps its corpus seeds in
`tests/fuzz/corpus.py`, which is being ported to this tree separately; this file must go red
or green on its own, so the three wire shapes it needs live below and should be folded into
that corpus once it lands.
"""

from __future__ import annotations

import json as jsonlib

from collections.abc import Iterator
from struct import pack
from typing import Any

import pytest
from hypothesis import given, strategies as st

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

from tests.fuzz.strategies import payload

pytestmark = pytest.mark.fuzz

TLVS = sorted(LinkState.registered_lsids)

# An unregistered code, which must fall through to a synthesised GenericLSID rather than be
# refused: RFC 9552 5.1 requires an unknown TLV to be preserved and propagated.
UNKNOWN_TLV = 9999

SWEPT = TLVS + [UNKNOWN_TLV]

# Ratchet on the registry this file parametrises over.  Raise it as TLVs are added, never
# lower it.  Marked registry_floor so qa/bin/check_sweep_floors can ask for it BY NAME: a
# file whose seeds break under thinning goes red with or without a floor, so "something
# failed" cannot stand in for "the floor fired".
LSID_FLOOR = 45

# A payload which closes the JSON string it is interpolated into and opens a member of its
# own.  Any TLV which builds its output by hand rather than through json.dumps lets this
# through, which is CWE-116 and was GHSA-jcrv-p53f-v5w5 in this very attribute.
INJECTION = b'x", "injected": "owned'

# Long enough to run past the fixed fields of every TLV registered here; the longest is the
# SRv6 End.X SID at 22 octets.
SHORT_TLV_MAX_LENGTH = 40

FILLS = (b'A', b'\x00', b'\xff', b'\x80', b'\x01\x02\x03')

NON_TEXT_PAYLOADS = [b'\x00' * 8, b'\xff' * 8, b'\x00\x01\x02\x03\x04\x05\x06\x07']

# The generic message LinkState._decode_tlv raises when an IndexError or a struct.error
# escapes a TLV decoder.  That conversion is a backstop, not a substitute for a decoder
# checking its own reads: because it renames an unchecked read into a protocol error, a fuzz
# sweep comes back clean while the reads are still unchecked.
DECODE_BOUNDARY = 'could not be decoded'

# SRv6 End.X SID (TLV 1106) as sent by a real router: behaviour 0x0039, flags 0x80,
# algorithm 0, weight 0, reserved 0, a sixteen octet SID, then a SID Structure sub-TLV
# (sub-TLV 1252 = 0x04E4) carrying 32/16/16/0.
SRV6_ENDX = bytes.fromhex('003980000000FC0010000112E002000000000000000004E4000420101000')

# RFC 9514 4.1: behaviour(2) flags(1) algorithm(1) weight(1) reserved(1) SID(16).
SRV6_ENDX_MIN_LENGTH = 22

# The fixed part of the same TLV, so a test about sub-TLV framing can append its own and
# change nothing else.  Sliced from the capture rather than written out again, because the
# two disagreeing by one octet is a test which passes for the wrong reason.
SRV6_ENDX_FIXED = SRV6_ENDX[:SRV6_ENDX_MIN_LENGTH]

SRV6_SID_STRUCTURE_TLV = 1252

# RFC 9514 4.1 and 4.2: the fixed part of each sub-TLV bearing TLV, IS-IS carrying a six
# octet system id where OSPF carries a four octet router id.
SUB_TLV_BEARING_MIN_LENGTH = {1106: 22, 1107: 28, 1108: 26}

FOUR_BYTE_TAG_TLVS = (1153, 1154)
FIXED_FIELD_TLVS = (1250, 1252)


@pytest.fixture(autouse=True, scope='module')
def _the_registry_is_left_as_it_was_found() -> Iterator[None]:
    """`get_ls_class` caches a synthesised class for an unknown code, so it grows the registry.

    Module scope on purpose: a function scoped autouse fixture trips
    HealthCheck.function_scoped_fixture on every @given test in the file, and what needs
    undoing is one insertion per unknown code, not one per example.
    """
    known = dict(LinkState.registered_lsids)
    yield
    LinkState.registered_lsids.clear()
    LinkState.registered_lsids.update(known)


def framed(scode: int, value: bytes) -> bytes:
    """One TLV, framed the way it arrives inside a BGP-LS attribute: Type(2) Length(2) Value."""
    return pack('!HH', scode, len(value)) + value


def render(scode: int, value: bytes) -> tuple[str, str, str]:
    """Decode one TLV the way an UPDATE would, then render it every way the process does.

    `unpack_attribute` parses eagerly, so a malformed TLV is a `Notify` from the decode path
    where the reactor can answer it.  The renders are the API writer's `json()`, the same
    with `compact`, and the logger's `str()`, which reaches every TLV's `__repr__`.
    """
    attribute = LinkState.unpack_attribute(framed(scode, value), None)
    return attribute.json(), attribute.json(True), str(attribute)


def filled(length: int, fill: bytes) -> bytes:
    """A payload of the requested length made of a repeating pattern."""
    return (fill * (length // len(fill) + 1))[:length]


def member_names(node: Any) -> Iterator[str]:
    """Every member name in the decoded JSON, at any depth."""
    if isinstance(node, dict):
        for name, value in node.items():
            yield name
            yield from member_names(value)
    elif isinstance(node, list):
        for value in node:
            yield from member_names(value)


def one_parseable_line(emitted: str, what: str) -> Any:
    """The API stream is line delimited, so a render is one line and it parses."""
    assert len(emitted.splitlines()) == 1, f'{what} split the line delimited API stream'
    try:
        return jsonlib.loads(emitted)
    except ValueError as exc:
        raise AssertionError(f'{what} emitted something no JSON parser accepts: {emitted[:200]}') from exc


@pytest.mark.parametrize('scode', SWEPT)
@pytest.mark.parametrize('length', range(0, SHORT_TLV_MAX_LENGTH))
def test_a_truncated_tlv_raises_notify_or_renders(scode: int, length: int) -> None:
    """A TLV shorter than its fixed fields is a protocol error, never a Python exception."""
    try:
        emitted, compact, _ = render(scode, b'A' * length)
    except Notify:
        return
    one_parseable_line(emitted, f'TLV {scode} at length {length}')
    one_parseable_line(compact, f'TLV {scode} at length {length}, compact')


@pytest.mark.parametrize('scode', SWEPT)
def test_a_quote_in_the_payload_cannot_add_a_member(scode: int) -> None:
    """A peer must not be able to add a member of its own to the API stream."""
    try:
        emitted, _, _ = render(scode, INJECTION)
    except Notify:
        return
    parsed = one_parseable_line(emitted, f'TLV {scode} with a quote in its payload')
    assert 'injected' not in set(member_names(parsed)), f'TLV {scode} let the peer inject a member'


@pytest.mark.parametrize('scode', SWEPT)
@pytest.mark.parametrize('value', NON_TEXT_PAYLOADS)
def test_a_non_text_payload_stays_one_json_line(scode: int, value: bytes) -> None:
    """Control bytes and invalid UTF-8 must not break the line delimited stream."""
    try:
        emitted, _, _ = render(scode, value)
    except Notify:
        return
    one_parseable_line(emitted, f'TLV {scode} carrying {value.hex()}')


@pytest.mark.parametrize('scode', TLVS)
def test_a_tlv_checks_its_own_reads(scode: int) -> None:
    """The decode boundary is a backstop, and a TLV which needs it has an unchecked read.

    `LinkState._decode_tlv` converts `IndexError` and `struct.error` into a `Notify`.  That
    keeps the daemon alive, and it also makes a decoder with no length checks look exactly
    like one which has them, which is how four SRv6 TLVs were broken on well formed input
    while the sweep over them reported clean.  If this fails, the named TLV has a read
    nobody checked.
    """
    masked = []
    for length in range(0, SHORT_TLV_MAX_LENGTH):
        for fill in FILLS:
            try:
                render(scode, filled(length, fill))
            except Notify as exc:
                if DECODE_BOUNDARY in str(exc):
                    masked.append((length, str(exc)))
            except Exception:  # noqa: BLE001 - the properties above are what report these
                pass
    assert not masked, f'TLV {scode} relies on the decode boundary: {masked[0][1]}'


@given(value=payload(0, 64))
@pytest.mark.parametrize('scode', SWEPT)
def test_arbitrary_bytes_into_any_tlv(scode: int, value: bytes) -> None:
    """Random and boundary bytes into any registered TLV: Notify, or a parseable line."""
    try:
        emitted, _, _ = render(scode, value)
    except Notify:
        return
    one_parseable_line(emitted, f'TLV {scode} carrying {value.hex()}')


@given(text=st.text(max_size=48))
@pytest.mark.parametrize('scode', SWEPT)
def test_arbitrary_text_into_any_tlv(scode: int, text: str) -> None:
    """Arbitrary text, which is where the quotes and the control characters come from."""
    try:
        emitted, _, _ = render(scode, text.encode('utf-8'))
    except Notify:
        return
    parsed = one_parseable_line(emitted, f'TLV {scode} carrying text')
    assert 'injected' not in set(member_names(parsed))


@pytest.mark.parametrize('scode', SWEPT)
def test_the_same_tlv_twice_names_its_member_once(scode: int) -> None:
    """Two of one TLV must not emit the member twice: every JSON parser keeps one silently.

    RFC 9552 8.2.2 forbids calling the attribute malformed over which TLVs it includes, so a
    repeat cannot be refused.  `LinkState.json()` groups a repeated key into an array instead,
    and this is what holds it to that: a duplicate member is data loss no consumer can see.
    """
    value = b'\x00' * 8
    try:
        attribute = LinkState.unpack_attribute(framed(scode, value) + framed(scode, value), None)
        emitted = attribute.json()
    except Notify:
        return
    repeated: list[str] = []

    def one_of_each(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        """Per object, not per document: two members of one object are the loss, two sibling
        objects carrying the same member name are what an array of them looks like."""
        names = [name for name, _ in pairs]
        repeated.extend(name for name in set(names) if names.count(name) > 1)
        return dict(pairs)

    jsonlib.loads(emitted, object_pairs_hook=one_of_each)
    assert not repeated, f'TLV {scode} sent twice emitted {repeated} twice in one object: {emitted[:200]}'


class TestRealWirePayloadsRender:
    """Wire shapes the synthetic fillers above do not reach.

    A TLV which decodes but cannot be rendered breaks the API writer and the logger, and with
    the decode boundary in place it closes the session as well.  These came out of the
    decoding functional suite.
    """

    def test_a_real_srv6_endx_renders_every_way(self) -> None:
        """`str()` reaches Srv6EndX.__repr__, which used attribute access on what is a dict."""
        emitted, _, as_str = render(1106, SRV6_ENDX)
        parsed = one_parseable_line(emitted, 'a real SRv6 End.X SID')
        assert 'srv6-sid-structure' in set(member_names(parsed))
        assert 'behavior' in as_str
        assert 'sid' in as_str

    def test_a_real_srv6_lan_endx_isis_renders_every_way(self) -> None:
        """The same shape with a six octet IS-IS neighbour id in front of the SID.

        Exactly 28 octets, RFC 9514 4.2: behaviour(2) flags(1) algorithm(1) weight(1)
        reserved(1) System-ID(6) SID(16).  5.0's copy of this test carried 29 and was wrapped
        in a skip for when the decoder refused it, which is a test that reports nothing.
        """
        value = bytes.fromhex('00398000' + '0000' + '010203040506' + '00' * 16)
        assert len(value) == SUB_TLV_BEARING_MIN_LENGTH[1107]
        emitted, _, as_str = render(1107, value)
        one_parseable_line(emitted, 'a real SRv6 LAN End.X SID')
        assert 'neighbor-id' in as_str


class TestALengthCheckIsAMinimumNotAnExactLength:
    """A length check must not refuse what a decoder has no trouble with.

    RFC 9552 8.2.2 names "the length of a fixed-length TLV is correct or the length of a
    variable length TLV is valid or permissible" among the checks a BGP-LS propagator should
    NOT perform.  A check stricter than the decoder needs turns a working route into a
    discarded attribute, which is worse than what it was written to prevent.
    """

    @pytest.mark.parametrize('scode', FOUR_BYTE_TAG_TLVS)
    def test_an_empty_tag_list_is_not_refused(self, scode: int) -> None:
        """None is a whole number of elements, and it renders as an empty list."""
        emitted, _, _ = render(scode, b'')
        parsed = one_parseable_line(emitted, f'TLV {scode} carrying no tag')
        assert list(parsed.values()) == [[]]

    @pytest.mark.parametrize('scode', FIXED_FIELD_TLVS)
    @pytest.mark.parametrize('length', range(4, 20))
    def test_a_longer_tlv_is_not_refused(self, scode: int, length: int) -> None:
        """The fixed fields are a MINIMUM: a TLV may carry fields a later RFC adds."""
        emitted, _, _ = render(scode, b'\x01' * length)
        one_parseable_line(emitted, f'TLV {scode} at length {length}')


class TestARecognisedTlvValidatesItsSubTlvLengths:
    """RFC 9552 8.2.2, third bullet of the BGP-LS Attribute validation a speaker MUST perform:

    "The length of each TLV and, when the TLV is recognized then, the length of its sub-TLVs
    in the BGP-LS Attribute are valid."

    TLV 1106 and its two LAN siblings walk their sub-TLVs with `data[4:length + 4]`, a slice,
    which cannot raise however large the declared length is.  So a sub-TLV claiming more than
    the enclosing TLV holds was reported as whatever happened to be there, and the peer's
    length was never compared with anything.  The answer is `Notify`, which `LinkState.DISCARD`
    turns into the 'Attribute Discard' the same section asks for.
    """

    @pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation', polarity='negative')
    @pytest.mark.parametrize('scode', sorted(SUB_TLV_BEARING_MIN_LENGTH))
    def test_an_unknown_sub_tlv_claiming_more_than_is_there_is_refused(self, scode: int) -> None:
        """An unrecognised code is preserved, and its LENGTH is still the enclosing TLV's business.

        The unknown code is what pins the check to the enclosing TLV.  A recognised sub-TLV
        refuses a short value through its own minimum, so that case would go green on the day
        the enclosing loop stopped comparing anything at all.
        """
        value = bytes(SUB_TLV_BEARING_MIN_LENGTH[scode]) + pack('!HH', UNKNOWN_TLV, 8) + b'\xaa\xbb'
        with pytest.raises(Notify):
            render(scode, value)

    @pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation')
    @pytest.mark.parametrize('scode', sorted(SUB_TLV_BEARING_MIN_LENGTH))
    def test_a_stub_too_short_for_a_sub_tlv_header_is_tolerated(self, scode: int) -> None:
        """Three trailing octets cannot be a sub-TLV, and are logged and ignored, not refused.

        This test asserted `Notify` when the length check first went in, and `qa/bin/compat_gate`
        answered with nine regressions: TLV 1106 at payload lengths 23, 24 and 25 over a 22 octet
        fixed part, each an SRv6 End.X SID which used to decode and would have gone dark on
        upgrade.  Refusing discards the whole BGP-LS attribute, so a peer which pads its TLV
        loses a route over three octets that say nothing an operator can act on.

        The half worth keeping is the one above: a sub-TLV *claiming* more octets than exist is a
        length the peer got wrong about data we would go on to read, and that is still refused.
        The distinction is deliberate, not a weakening.
        """
        value = bytes(SUB_TLV_BEARING_MIN_LENGTH[scode]) + b'\x01\x02\x03'

        emitted, _, _ = render(scode, value)

        one_parseable_line(emitted, f'TLV {scode} with a trailing remnant')

    @pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation', polarity='negative')
    @pytest.mark.parametrize('scode', sorted(SUB_TLV_BEARING_MIN_LENGTH))
    @pytest.mark.parametrize('remnant', [1, 2, 3])
    def test_a_tolerated_remnant_is_not_reported_as_a_sub_tlv(self, scode: int, remnant: int) -> None:
        """Ignoring the remnant must not invent a member from it, which is what the walk did.

        Before the length check the remnant was dropped silently; the risk in forgiving it again
        is that it comes back as an `unknown-subtlv-` member built out of whatever the octets
        happen to say.  Nothing in the output may mention it.
        """
        value = bytes(SUB_TLV_BEARING_MIN_LENGTH[scode]) + bytes([0x30] * remnant)

        emitted, _, _ = render(scode, value)

        parsed = one_parseable_line(emitted, f'TLV {scode} with {remnant} trailing octets')
        clean, _, _ = render(scode, bytes(SUB_TLV_BEARING_MIN_LENGTH[scode]))
        assert set(member_names(parsed)) == set(member_names(one_parseable_line(clean, 'no remnant')))

    @pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation')
    def test_a_sub_tlv_whose_length_agrees_is_still_accepted(self) -> None:
        """The positive half: the real router's TLV, whose sub-TLV length is honest."""
        emitted, _, _ = render(1106, SRV6_ENDX)
        parsed = one_parseable_line(emitted, 'a real SRv6 End.X SID')
        assert 'srv6-sid-structure' in set(member_names(parsed))

    @pytest.mark.rfc('rfc9552#8.2.2-attribute-syntactic-validation')
    @pytest.mark.parametrize('scode', sorted(SUB_TLV_BEARING_MIN_LENGTH))
    def test_a_tlv_with_no_sub_tlv_at_all_is_still_accepted(self, scode: int) -> None:
        """The fixed part on its own is the common case and must not be caught by the check."""
        emitted, _, _ = render(scode, bytes(SUB_TLV_BEARING_MIN_LENGTH[scode]))
        one_parseable_line(emitted, f'TLV {scode} with no sub-TLV')


class TestKnownGaps:
    """Demonstrated rather than described, per qa/rfc/README.md."""

    @pytest.mark.xfail(strict=True, reason='RFC 9552 8.2.2: a repeated sub-TLV is silently dropped')
    def test_a_repeated_sub_tlv_does_not_lose_the_first_one(self) -> None:
        """`_unpack_data` joins its sub-TLV renders into a string and calls json.loads on it.

        Two sub-TLVs of one code therefore write the same member twice into that string, and
        `json.loads` keeps the last: the first sub-TLV leaves the process without a trace.
        RFC 9552 8.2.2 forbids refusing the attribute over which sub-TLVs it includes, so the
        answer is not a `Notify` but an array, the way `LinkState.json()` answers a repeated
        TLV.  That is a change to how the member is shaped, so it is recorded here rather than
        made alongside the length checks.
        """
        first = pack('!HH', SRV6_SID_STRUCTURE_TLV, 4) + bytes([1, 2, 3, 4])
        second = pack('!HH', SRV6_SID_STRUCTURE_TLV, 4) + bytes([9, 9, 9, 9])
        emitted, _, _ = render(1106, SRV6_ENDX_FIXED + first + second)
        assert '"loc_block_len": 1' in emitted, emitted


@pytest.mark.registry_floor
def test_the_registry_this_file_sweeps_is_populated() -> None:
    """A short registry does not fail this file, it collects fewer cases and still reads green.

    The registries fill by import side effect; `tests/fuzz/conftest.py` walks the attribute
    package before collection for exactly this reason.
    """
    assert len(TLVS) >= LSID_FLOOR, f'only {len(TLVS)} BGP-LS TLVs are registered: {TLVS}'
