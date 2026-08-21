"""What a peer sends must never corrupt or crash the JSON API stream.

GHSA-jcrv-p53f-v5w5 was a peer choosing what appeared in the stream ExaBGP writes to
every subscribed API subprocess.  Escaping closed that.  These are the cases found by
the property tests in tests/fuzz afterwards, where a peer instead makes ExaBGP write a
line no JSON parser accepts, or makes the encoder raise on its way there.

Both matter to the same consumer: a DDoS mitigation or FlowSpec controller reading the
stream is equally broken by an injected member, by a line it cannot parse, and by a
session that died mid-write.  TIGER_STYLE.md 1.1: validate once, at the boundary, and
what decoded must survive json(), str() and index().
"""

import json as jsonlib
import struct

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.collection import AttributeCollection
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

FLOW_FAMILIES = [
    (AFI.ipv4, SAFI.flow_ip),
    (AFI.ipv4, SAFI.flow_vpn),
    (AFI.ipv6, SAFI.flow_ip),
    (AFI.ipv6, SAFI.flow_vpn),
]


def parsed(fragment: str) -> dict[str, object]:
    """Parse a json() result the way the API consumer parses the line holding it.

    Some json() methods return a complete object, others a member of the object their
    caller is building.  Both have to be readable; which one it is, is not the point.
    """
    for candidate in (fragment, '{' + fragment + '}'):
        try:
            decoded: dict[str, object] = jsonlib.loads(candidate)
            return decoded
        except ValueError:
            continue
    raise AssertionError(f'json() returned something no JSON parser accepts: {fragment[:200]}')


@pytest.mark.parametrize('family', FLOW_FAMILIES, ids=lambda f: f'{f[0]}/{f[1]}')
def test_flow_fragment_with_a_two_byte_value_does_not_crash(family: tuple[AFI, SAFI]) -> None:
    """The fragment component is an IOperationByteShort, so it may carry two bytes.

    Its decoder was ord(), which takes one, so a two byte fragment raised TypeError out
    of unpack_nlri and killed the process instead of closing the session.
    """
    afi, safi = family
    # component 0x0C (fragment), operator 0x90: end of list, two byte value
    payload = b'\x0c\x90\x00\x01'
    if safi == SAFI.flow_vpn:
        payload = bytes(8) + payload
    data = bytes([len(payload)]) + payload
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID, 'a fragment component may carry a two byte value'
    assert 'fragment' in parsed(nlri.json())


@pytest.mark.parametrize('family', FLOW_FAMILIES, ids=lambda f: f'{f[0]}/{f[1]}')
def test_flow_truncated_before_its_end_of_list_is_refused(family: tuple[AFI, SAFI]) -> None:
    """A rule list which stops before its end of list operator must not be kept.

    _parse_rules ended in `except (IndexError, KeyError): pass`, so a truncated flow was
    accepted as a shorter route than the peer announced.  A route nobody sent is worse
    than no route at all: TIGER_STYLE.md 1.1.
    """
    afi, safi = family
    # source port (component 5): the operator asks for two bytes and does not end the list,
    # and nothing follows. Deliberately not the fragment component, which has its own test.
    payload = b'\x05\x10\x00\x01'
    if safi == SAFI.flow_vpn:
        payload = bytes(8) + payload
    data = bytes([len(payload)]) + payload
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    assert nlri is NLRI.INVALID


@pytest.mark.parametrize('family', FLOW_FAMILIES, ids=lambda f: f'{f[0]}/{f[1]}')
def test_flow_with_no_component_is_dropped(family: tuple[AFI, SAFI]) -> None:
    """A flow which parsed no component matches everything.

    json() used to render such a route as `{, "string": "flow" }`, which no parser accepts,
    and the obvious repair was to emit `{"string": "flow"}` instead. That is worse: a
    controller reading a FlowSpec route with no component and applying discard or rate
    limit to it hits all traffic. An unknown component now ends the NLRI, so the route is
    dropped, which is what RFC 8955 section 4.3 asks for.
    """
    afi, safi = family
    payload = b'\xff\x00'  # component 0xFF is not one any family defines
    if safi == SAFI.flow_vpn:
        payload = bytes(8) + payload
    data = bytes([len(payload)]) + payload
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    assert nlri is NLRI.INVALID


@pytest.mark.parametrize('family', FLOW_FAMILIES, ids=lambda f: f'{f[0]}/{f[1]}')
@pytest.mark.parametrize('component', [0x0C, 0x09], ids=['fragment', 'tcp-flags'])
def test_flow_rule_which_renders_empty_still_emits_json(family: tuple[AFI, SAFI], component: int) -> None:
    """A bitmask rule can render as the empty string, and it used to eat its own quotes.

    The members were assembled out of quoted pieces and then repaired with
    .replace('""', ''), so an element which rendered empty left `[ , "is-fragment" ]`
    behind: the same unreadable line as the leading comma, reached another way.
    """
    afi, safi = family
    payload = bytes([component, 0x00, 0x00, 0x80, 0x02])
    if safi == SAFI.flow_vpn:
        payload = bytes(8) + payload
    data = bytes([len(payload)]) + payload
    nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    if nlri is NLRI.INVALID:
        return
    parsed(nlri.json())
    parsed(nlri.json(announced=False))


def _addpath(data: bytes) -> Capability:
    code: CapabilityCode = CapabilityCode.ADD_PATH
    klass = Capability.klass(code)
    return klass.unpack_capability(klass(), data, code)


@pytest.mark.parametrize('send_receive', [4, 5, 103, 255])
def test_addpath_names_an_undefined_send_receive(send_receive: int) -> None:
    """RFC 7911 defines 1, 2 and 3, and a peer sending anything else is not refused.

    RequirePath.setup reads the value as a bitmask, so such a peer establishes a session
    today and has to keep establishing one after an upgrade. What was wrong was the name
    lookup: a table holding only 0 to 3, consulted without a default, raised KeyError from
    json() and from __str__(), which is the writer feeding the API subprocesses and the
    logger.
    """
    capability = _addpath(bytes([0x00, 0x01, 0x01, send_receive]))
    described = jsonlib.loads(capability.json())
    assert described['ipv4/unicast'] == f'invalid ({send_receive})'
    assert str(send_receive) in str(capability)


@pytest.mark.parametrize('send_receive', [1, 2, 3])
def test_addpath_accepts_what_the_rfc_defines(send_receive: int) -> None:
    capability = _addpath(bytes([0x00, 0x01, 0x01, send_receive]))
    assert jsonlib.loads(capability.json())['name'] == 'addpath'
    str(capability)


def _decode_attribute(code: int, data: bytes) -> Attribute:
    klass = Attribute.klass_by_id(code)
    assert klass is not None, f'attribute {code} is not registered'
    return klass.unpack_attribute(data, Negotiated.UNSET)


def _pmsi(data: bytes) -> Attribute:
    return _decode_attribute(Attribute.CODE.PMSI_TUNNEL, data)


@pytest.mark.parametrize('tunnel', [b'', b'\xff', b'\xff\xff', b'\x0a\x00\x00\x01\x05', b'\x00' * 8])
def test_pmsi_gives_a_mismatched_tunnel_the_generic_class(tunnel: bytes) -> None:
    """A subclass exists to read one shape of tunnel identifier, and its accessors say so.

    PMSIIngressReplication.ip hands four bytes to IPv4.ntop(), which raises ValueError on
    anything else: that surfaced from str() and repr(), which is the logger and the text
    API, long after the UPDATE was accepted. Selecting the class on the type byte alone
    meant the class and the data disagreed.

    Refusing the attribute would drop a route this release accepts, so the dispatch is what
    gives way: the identifier has to fit the class, or the generic PMSI holds the same
    bytes and prints them as hex.
    """
    attribute = _pmsi(b'\x00\x06\x00\x00\x00' + tunnel)
    assert type(attribute).__name__ == 'PMSI'
    assert str(attribute)
    repr(attribute)


def test_pmsi_ingress_replication_accepts_an_address() -> None:
    attribute = _pmsi(b'\x00\x06\x00\x00\x00\x0a\x00\x00\x01')
    assert '10.0.0.1' in str(attribute)


def _linkstate(data: bytes) -> Attribute:
    return _decode_attribute(Attribute.CODE.BGP_LS, data)


def test_bgpls_rejects_a_truncated_tlv_when_it_decodes() -> None:
    """A TLV claiming more bytes than the attribute holds must be refused at decode.

    unpack_attribute only stored the bytes, so the Notify surfaced later, from json()
    and from str(), by which point the UPDATE had been accepted and the API writer was
    the one holding an exception nothing there treats as a protocol error.
    """
    with pytest.raises(Notify):
        _linkstate(b'\x04\x00\xff\xff\x01\x02\x03')


def test_bgpls_renders_a_well_formed_tlv() -> None:
    # TLV 1088 (administrative group), a four byte mask
    attribute = _linkstate(b'\x04\x40\x00\x04\x00\x00\x00\x0a')
    assert parsed(attribute.json()) is not None
    str(attribute)


def _tlv(code: int, payload: bytes) -> Attribute:
    return _linkstate(struct.pack('!HH', code, len(payload)) + payload)


def keys_anywhere(decoded: object) -> set[str]:
    """Every key in the structure, however deep.

    Checking only the top level would miss a member injected inside a nested object, and
    checking whether the payload text appears anywhere is the wrong test: correctly
    escaped text appears as a value, which is exactly what should happen.
    """
    if isinstance(decoded, dict):
        found = set(decoded)
        for value in decoded.values():
            found |= keys_anywhere(value)
        return found
    if isinstance(decoded, list):
        found: set[str] = set()
        for item in decoded:
            found |= keys_anywhere(item)
        return found
    return set()


@pytest.mark.parametrize('code', [1097, 1157])
def test_bgpls_opaque_tlv_cannot_inject_a_json_member(code: int) -> None:
    """A peer must not be able to add a member of its choosing to the API stream.

    This is GHSA-jcrv-p53f-v5w5 reached by a different road: attribute 29 is dispatched
    by attribute code with no family gate, so it rides on a plain IPv4 unicast UPDATE
    and needs no BGP-LS capability.
    """
    payload = b'x", "injected": "owned'
    attribute = _tlv(code, payload)
    decoded = jsonlib.loads(attribute.json())
    assert 'injected' not in keys_anywhere(decoded), 'a peer chose a key in the API stream'
    assert len(decoded) == 1

    # The payload is still recoverable, which is the point: escaping it kept the bytes and
    # so does hex.  These TLVs render hex now, because RFC 9552 makes them envelopes for
    # IGP TLVs rather than text, so this asserts the bytes round trip rather than that a
    # particular rendering of them appears.  Hex is the stronger position of the two: an
    # escaped string still has to be escaped correctly, and hex has no quotes to escape.
    rendered = list(decoded.values())[0]
    assert bytes.fromhex(rendered) == payload, 'the opaque payload did not survive the render'


@pytest.mark.parametrize('code', [1026, 1097, 1098, 1157])
def test_bgpls_text_tlv_survives_bytes_which_are_not_text(code: int) -> None:
    """Bytes a peer sent are not guaranteed to be UTF-8, or ASCII.

    decode() without an error handler raised UnicodeDecodeError out of the API writer.
    """
    try:
        attribute = _tlv(code, b'\xff\xfe\xfd')
    except Notify:
        return
    parsed(attribute.json())
    str(attribute)


@pytest.mark.parametrize('code', [1097, 1157])
def test_bgpls_opaque_tlv_escapes_control_characters(code: int) -> None:
    """Raw control bytes inside a JSON string are rejected by a standard parser."""
    attribute = _tlv(code, b'\x00\x01\x02\x03')
    parsed(attribute.json())


@pytest.mark.parametrize(
    'code, payload',
    [
        (1099, b'AAAAAAAA'),  # AdjacencySid: unpack('!L', ...) past the end
        (1100, b'AAAA'),  # LanAdjacencySid
        (1153, b'A'),  # IgpTags: LEN is 0 so check_length checks nothing
        (1154, b'A'),  # IgpExTags: the same, with 8 byte elements
        (1158, b'AAAAAAAAAAAAAAAA'),  # PrefixSid
    ],
)
def test_bgpls_short_tlv_raises_notify_at_the_decoder(code: int, payload: bytes) -> None:
    """A TLV which cannot be decoded is the peer's error, and it is ours to report.

    struct.error is not caught by AttributeCollection.parse, so it escaped into the
    reactor.  It has to be a Notify, and it has to come from the decode path and not
    from the API writer half a second later.
    """
    with pytest.raises(Notify):
        _tlv(code, payload)


def test_evpn_ethernet_ad_without_a_label_stack_still_emits_json() -> None:
    """json() was built by concatenating members which carried their own separators.

    self.label.json() is empty when there is no label stack, so the route came out as
    `..., "ethernet-tag": 0,  }` and no consumer could read the line.  Found by the
    property tests in tests/fuzz once they started checking that json() parses.
    """
    payload = bytes(22)
    nlri, _ = NLRI.unpack_nlri(AFI.l2vpn, SAFI.evpn, bytes([1, len(payload)]) + payload, Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID
    assert parsed(nlri.json())['code'] == 1


@pytest.mark.parametrize('code, payload', [(2, bytes(33)), (5, bytes(34))])
def test_evpn_route_json_has_no_stray_separator(code: int, payload: bytes) -> None:
    try:
        nlri, _ = NLRI.unpack_nlri(
            AFI.l2vpn, SAFI.evpn, bytes([code, len(payload)]) + payload, Action.ANNOUNCE, None, None
        )
    except Notify:
        return  # refusing the route is a fine answer, it is a stray comma we are after
    if nlri is None or nlri is NLRI.INVALID:
        return
    assert parsed(nlri.json())['code'] == code


@pytest.mark.parametrize(
    'code, value',
    [
        (Attribute.CODE.EXTENDED_COMMUNITY, bytes.fromhex('0208359d0f6f18f2')),  # redirect to ASN4
        (Attribute.CODE.IPV6_EXTENDED_COMMUNITY, bytes.fromhex('000b') + bytes(18)),  # redirect to IPv6
    ],
)
def test_extended_community_without_its_own_repr_does_not_recurse(code: int, value: bytes) -> None:
    """__repr__ delegated to the registered class, which had inherited it back.

    Eight bytes of FlowSpec redirect community exhausted the stack inside the writer
    feeding the API subprocesses.  A RecursionError there is a dead process rather than a
    dead session, and both affected types are redirect communities: what the FlowSpec
    controllers this API exists for actually receive.
    """
    attribute = _decode_attribute(code, value)
    parsed(attribute.json())
    str(attribute)
    repr(attribute)


def test_a_whole_update_carrying_a_redirect_community_renders() -> None:
    """The recursion was reached by a plain IPv4 unicast UPDATE, not by a FlowSpec one."""
    collection = AttributeCollection()
    collection.add(_decode_attribute(Attribute.CODE.EXTENDED_COMMUNITY, bytes.fromhex('0208359d0f6f18f2')))
    assert jsonlib.loads('{' + collection.json() + '}')


@pytest.mark.parametrize('tlv', [0, 2, 4, 7, 8, 255])
def test_unregistered_prefix_sid_tlv_decodes(tlv: int) -> None:
    """GenericSRId had no pack_tlv(), and __init__ rebuilt the attribute from its TLVs.

    So every TLV type a peer picks other than 1 and 3 raised AttributeError out of the
    decoder.  The wire bytes are kept now, which is also what stops the attribute being
    re-encoded into something the peer never sent.
    """
    payload = b'\x01\x02\x03'
    attribute = _decode_attribute(
        Attribute.CODE.BGP_PREFIX_SID, bytes([tlv]) + struct.pack('!H', len(payload)) + payload
    )
    parsed(attribute.json())
    str(attribute)


@pytest.mark.parametrize(
    'code, payload, why',
    [
        (1153, b'AA', 'route tags are four bytes each'),
        (1154, b'AAAA', 'extended route tags are eight bytes each'),
        (1099, b'\x30\x00\x00\x00\xff', 'a label needs three bytes'),
        (1100, b'\x30\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff', 'a label needs three bytes'),
        (1158, b'\x0c\x00\x00\x00\xff', 'a label needs three bytes'),
        (1026, b'\xff\xfe', 'a node name is ASCII'),
        (1098, b'\xff\xfe', 'a link name is UTF-8'),
    ],
)
def test_bgpls_tlv_checks_its_own_reads(code: int, payload: bytes, why: str) -> None:
    """Whatever happens, it is not the central catch-all that has to notice."""
    try:
        attribute = _tlv(code, payload)
    except Notify as exc:
        assert 'could not be decoded' not in str(exc), f'{code} still leans on the boundary: {why}'
        return
    parsed(attribute.json())
    str(attribute)


# ============================================================================
# SR Policy names: escaping the quotes and nothing else is the half fix
# ============================================================================


SR_POLICY_TUNNEL_TYPE = 15
POLICY_NAME_SUBTYPE = 130
CANDIDATE_PATH_NAME_SUBTYPE = 129


def _sr_policy_name(subtype: int, name: bytes) -> Attribute:
    """A tunnel encapsulation attribute holding one SR Policy name sub-TLV.

    RFC 9012: a sub-TLV type of 128 or more carries a two byte length, which is what makes
    these reachable at all. A sweep which writes a one byte length there never gets past
    the framing and reports a clean run over code it never ran.
    """
    value = b'\x00' + name  # a flags byte, then the name
    sub = bytes([subtype]) + struct.pack('!H', len(value)) + value
    return _decode_attribute(Attribute.CODE.TUNNEL_ENCAP, struct.pack('!HH', SR_POLICY_TUNNEL_TYPE, len(sub)) + sub)


@pytest.mark.parametrize('subtype', [POLICY_NAME_SUBTYPE, CANDIDATE_PATH_NAME_SUBTYPE])
@pytest.mark.parametrize(
    'name',
    [
        b'a\\',  # a backslash ate its own closing quote
        b'x", "injected": "owned',  # the quotes were escaped, the backslashes were not
        b'a\nb',  # a raw control character inside a JSON string
        b'\x00\x01\x02',
        b'my-policy',
    ],
)
def test_sr_policy_name_stays_one_json_value(subtype: int, name: bytes) -> None:
    """json() escaped the quotes by hand, which handles one character out of several.

    A peer names its policy through the Tunnel Encapsulation attribute, so this is peer
    supplied text on the API path: the corruption half of GHSA-jcrv-p53f-v5w5.
    """
    attribute = _sr_policy_name(subtype, name)
    decoded = parsed(attribute.json())
    assert 'injected' not in keys_anywhere(decoded)


@pytest.mark.parametrize('code', [1153, 1154])
def test_bgpls_empty_tag_list_is_still_accepted(code: int) -> None:
    """None is a whole number of elements, and this release renders it as an empty list.

    check_multiple() started out refusing an empty TLV as well as a partial one. RFC 7752
    says one or more, but a peer sending none has its route accepted today, and a check
    added to stop a crash must not take that with it.
    """
    attribute = _tlv(code, b'')
    assert parsed(attribute.json())
    str(attribute)


@pytest.mark.parametrize(
    'width, operator, value',
    [
        (1, 0x81, b'\x50'),
        (2, 0x91, b'\x00\x50'),
        (4, 0xA1, b'\x00\x00\x00\x50'),
        (8, 0xB1, bytes(7) + b'\x50'),
    ],
)
def test_flow_accepts_every_value_width_the_rfc_defines(width: int, operator: int, value: bytes) -> None:
    """RFC 8955 section 4.2.1.1 lets a sender encode a value in one, two, four or eight bytes.

    The check added to stop an ord() crash refused any width outside the component's
    VALUE_SIZES, which is what the component *encodes*, not what it may be sent. A
    destination port of 80 written in four bytes became NLRI.INVALID and was dropped with
    no log and no NOTIFICATION: a FlowSpec filter silently not installed, with the console
    still green.
    """
    component = bytes([0x05, operator]) + value  # destination-port
    data = bytes([len(component)]) + component
    nlri, _ = NLRI.unpack_nlri(AFI.ipv4, SAFI.flow_ip, data, Action.ANNOUNCE, None, None)
    assert nlri is not NLRI.INVALID, f'a {width} byte value was dropped'
    assert parsed(nlri.json())['destination-port'] == ['=80']
