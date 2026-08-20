"""Property based tests covering every registered NLRI decoder.

The number of examples and whether the seed varies come from the Hypothesis profiles in
conftest.py: derandomized for the gate, random and deeper for ./qa/bin/fuzz_hunt.

The hand written corpus in tests/unit/test_input_validation.py checks a fixed
list of truncated EVPN, BGP-LS and MUP routes.  These tests generalise it: for
*every* family in NLRI.registered_nlri, arbitrary wire bytes must either decode
into a usable NLRI or raise Notify.  No raw Python exception may escape, neither
during unpack nor later when the NLRI is turned into JSON, a string or an index.

A decoder which raises IndexError, struct.error, ValueError or AssertionError on
peer supplied bytes is a bug: the session must be closed with a NOTIFICATION,
not the process killed by a traceback.
"""

import pytest
from hypothesis import given, strategies as st

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

# de-duplicated: the registry lists (ipv4, multicast) twice
FAMILIES = sorted(set(NLRI.known_families()), key=lambda family: (int(family[0]), int(family[1])))

FAMILY_IDS = [f'{afi}/{safi}' for afi, safi in FAMILIES]


def decode(afi: AFI, safi: SAFI, data: bytes) -> NLRI | None:
    """Decode wire bytes, letting a Notify through but not a raw Python exception.

    Returns the decoded NLRI, or None when the decoder rejected the input.
    """
    try:
        nlri, _ = NLRI.unpack_nlri(afi, safi, data, Action.ANNOUNCE, None, None)
    except Notify:
        return None
    # the flow decoder reports a route it could not parse with the INVALID singleton,
    # which every caller drops before it reaches the RIB or the API
    if nlri is NLRI.INVALID:
        return None
    # a decoded NLRI must survive every representation the API and the RIB use
    nlri.json()
    nlri.json(announced=False)
    str(nlri)
    repr(nlri)
    nlri.index()
    hash(nlri)
    return nlri


@pytest.mark.fuzz
@pytest.mark.parametrize('family', FAMILIES, ids=FAMILY_IDS)
@given(data=st.binary(min_size=0, max_size=80))
def test_random_bytes_only_raise_notify(family: tuple[AFI, SAFI], data: bytes) -> None:
    """Arbitrary bytes decode or Notify, they never crash the parser."""
    afi, safi = family
    decode(afi, safi, data)


@pytest.mark.fuzz
@pytest.mark.parametrize('family', FAMILIES, ids=FAMILY_IDS)
@given(
    length=st.integers(min_value=0, max_value=255),
    payload=st.binary(min_size=0, max_size=80),
)
def test_lying_length_prefix_only_raises_notify(family: tuple[AFI, SAFI], length: int, payload: bytes) -> None:
    """A length byte which does not match the payload must not be trusted.

    Most families start with a one byte length or a type/length pair, so a
    generated prefix reaches deeper into the decoders than pure random bytes.
    """
    afi, safi = family
    decode(afi, safi, bytes([length]) + payload)
    decode(afi, safi, bytes([length & 0x0F, length]) + payload)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', list(range(0, 12)))
@given(
    length=st.integers(min_value=0, max_value=60),
    payload=st.binary(min_size=0, max_size=60),
)
def test_evpn_route_types_only_raise_notify(code: int, length: int, payload: bytes) -> None:
    """EVPN routes are a type byte, a length byte, then the route itself."""
    decode(AFI.l2vpn, SAFI.evpn, bytes([code, length]) + payload)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', list(range(0, 8)))
@given(
    length=st.integers(min_value=0, max_value=0xFFFF),
    payload=st.binary(min_size=0, max_size=60),
)
def test_bgpls_tlv_only_raises_notify(code: int, length: int, payload: bytes) -> None:
    """BGP-LS NLRI are a 16 bit type and a 16 bit length, followed by TLVs."""
    header = code.to_bytes(2, 'big') + length.to_bytes(2, 'big')
    decode(AFI.bgpls, SAFI.bgp_ls, header + payload)
    decode(AFI.bgpls, SAFI.bgp_ls_vpn, header + payload)


@pytest.mark.fuzz
@pytest.mark.parametrize('architecture', [1, 2, 3])
@pytest.mark.parametrize('code', [1, 2, 3, 4, 5])
@given(
    length=st.integers(min_value=0, max_value=255),
    payload=st.binary(min_size=0, max_size=60),
)
def test_mup_routes_only_raise_notify(architecture: int, code: int, length: int, payload: bytes) -> None:
    """MUP NLRI are an architecture byte, a 16 bit type, a length, then the route."""
    header = bytes([architecture]) + code.to_bytes(2, 'big') + bytes([length])
    for afi in (AFI.ipv4, AFI.ipv6):
        decode(afi, SAFI.mup, header + payload)


@pytest.mark.fuzz
@pytest.mark.parametrize('family', FAMILIES, ids=FAMILY_IDS)
@given(data=st.binary(min_size=0, max_size=80))
def test_decoding_is_idempotent(family: tuple[AFI, SAFI], data: bytes) -> None:
    """What a decoder accepts, it must re-encode into something it accepts again.

    A decoder which drops or invents bytes would announce a route the peer never
    sent, so packing then decoding again has to yield the same NLRI.
    """
    afi, safi = family
    nlri = decode(afi, safi, data)
    if nlri is None:
        return
    packed = nlri.pack_nlri(Negotiated.UNSET)
    again = decode(afi, safi, packed)
    assert again is not None, f'{afi}/{safi} refuses to decode what it just packed: {packed.hex()}'
    assert again.index() == nlri.index(), f'{afi}/{safi} is not stable across a pack and unpack cycle'
