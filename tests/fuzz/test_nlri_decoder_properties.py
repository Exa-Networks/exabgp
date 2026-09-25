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

import json as jsonlib


import pytest
from hypothesis import example, given, strategies as st

from tests.fuzz import corpus
from tests.fuzz.strategies import framed, payload

from exabgp.bgp.message import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.protocol.family import AFI, SAFI

# de-duplicated: the registry lists (ipv4, multicast) twice
FAMILIES = sorted(set(NLRI.known_families()), key=lambda family: (int(family[0]), int(family[1])))

MIN_FAMILIES = 23  # a ratchet: raise it as families are added, never lower it

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
    parses(nlri.json())
    parses(nlri.json(announced=False))
    str(nlri)
    repr(nlri)
    nlri.index()
    hash(nlri)
    return nlri


def parses(fragment: str) -> None:
    """A json() fragment must be readable by the API consumer it is written to.

    The fragments are members of a larger object, so they are wrapped before parsing.
    A fragment which needs no wrapping is already a complete object.  Emitting one
    which parses as neither corrupts every line ExaBGP writes to that subprocess:
    the CWE-116 half of GHSA-jcrv-p53f-v5w5 which escaping alone does not close.
    """
    for candidate in (fragment, '{' + fragment + '}', '[' + fragment + ']'):
        try:
            jsonlib.loads(candidate)
            return
        except ValueError:
            continue
    raise AssertionError(f'json() returned something no JSON parser accepts: {fragment[:200]}')


@pytest.mark.fuzz
@pytest.mark.parametrize('family', FAMILIES, ids=FAMILY_IDS)
@given(data=payload(0, 80))
def test_random_bytes_only_raise_notify(family: tuple[AFI, SAFI], data: bytes) -> None:
    """Arbitrary bytes decode or Notify, they never crash the parser."""
    afi, safi = family
    decode(afi, safi, data)


@pytest.mark.fuzz
@pytest.mark.parametrize('family', FAMILIES, ids=FAMILY_IDS)
@given(framed=framed(80, 255))
def test_lying_length_prefix_only_raises_notify(family: tuple[AFI, SAFI], framed: tuple[int, bytes]) -> None:
    """A length byte which does not match the payload must not be trusted.

    Most families start with a one byte length or a type/length pair, so a
    generated prefix reaches deeper into the decoders than pure random bytes.

    The length used to be drawn independently of the payload, which made it agree with
    the bytes behind it 1/256 of the time: a lying length is what the name says and what
    the decoders must refuse, but a *truthful* one is what gets past the truncation check
    and into the decoder this file claims to cover.  `framed()` draws both.
    """
    length, body = framed
    afi, safi = family
    decode(afi, safi, bytes([length]) + body)
    decode(afi, safi, bytes([length & 0x0F, length]) + body)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', list(range(0, 12)))
# The only lengths at which a registered EVPN route type decodes at all, mapped by
# sweeping every length from 0 to 51 against four fill bytes: 17 for the inclusive
# multicast tag, 23 for the ethernet segment, 34 for the IP prefix route, and 22 for the
# shortest auto-discovery route.  A length drawn uniformly from 0 to 60 hits a given one
# of them in 1 example out of 61.
@example(framed=(17, bytes(17)))
@example(framed=(22, bytes(22)))
@example(framed=(23, bytes(23)))
@example(framed=(34, bytes(34)))
@given(framed=framed(60, 60))
def test_evpn_route_types_only_raise_notify(code: int, framed: tuple[int, bytes]) -> None:
    """EVPN routes are a type byte, a length byte, then the route itself."""
    length, body = framed
    decode(AFI.l2vpn, SAFI.evpn, bytes([code, length]) + body)


@pytest.mark.fuzz
@pytest.mark.parametrize('code', list(range(0, 8)))
# A two octet length agrees with a payload of at most sixty bytes 1/65536 of the time, so
# this sweep reached the decoders behind the header in 0.3% of gate runs.  Twenty one is an
# accepting length for the link NLRI on both SAFIs, and the one which caught a VPN NLRI
# packing back without its route distinguisher: see
# tests/unit/test_nlri_wire_bounds.py::test_bgpls_vpn_registered_code_packs_back_its_route_distinguisher
@example(framed=(21, bytes(21)))
@given(framed=framed(60, 0xFFFF))
def test_bgpls_tlv_only_raises_notify(code: int, framed: tuple[int, bytes]) -> None:
    """BGP-LS NLRI are a 16 bit type and a 16 bit length, followed by TLVs."""
    length, body = framed
    header = code.to_bytes(2, 'big') + length.to_bytes(2, 'big')
    decode(AFI.bgpls, SAFI.bgp_ls, header + body)
    decode(AFI.bgpls, SAFI.bgp_ls_vpn, header + body)


@pytest.mark.fuzz
@pytest.mark.parametrize('architecture', [1, 2, 3])
@pytest.mark.parametrize('code', [1, 2, 3, 4, 5])
# Measured over forty rounds of two hundred examples, an independently drawn length
# reached a MUP route of twelve bytes or more, which is the shortest one any route type
# accepts, in 8 rounds out of 40.  framed() reaches it in all forty.
@example(framed=(16, bytes(16)))
@given(framed=framed(60, 255))
def test_mup_routes_only_raise_notify(architecture: int, code: int, framed: tuple[int, bytes]) -> None:
    """MUP NLRI are an architecture byte, a 16 bit type, a length, then the route."""
    length, body = framed
    header = bytes([architecture]) + code.to_bytes(2, 'big') + bytes([length])
    for afi in (AFI.ipv4, AFI.ipv6):
        decode(afi, SAFI.mup, header + body)


# The header shape of every family which frames its route behind a type and a length, and
# the architecture byte MUP puts in front of both.  Random bytes reach these decoders rarely
# and a random length almost never, so the idempotence rule below was being checked mostly
# on inputs refused at the header.  This pairs a header built by construction with that
# rule, which is how a BGP-LS VPN NLRI was caught packing back without its route
# distinguisher: see
# tests/unit/test_nlri_wire_bounds.py::test_bgpls_vpn_registered_code_packs_back_its_route_distinguisher
FRAMED_SHAPES: list[tuple[str, AFI, SAFI, bytes]] = [
    ('evpn', AFI.l2vpn, SAFI.evpn, b''),
    ('bgp-ls', AFI.bgpls, SAFI.bgp_ls, b''),
    ('bgp-ls-vpn', AFI.bgpls, SAFI.bgp_ls_vpn, b''),
    ('mup-ipv4-arch1', AFI.ipv4, SAFI.mup, bytes([1])),
    ('mup-ipv6-arch2', AFI.ipv6, SAFI.mup, bytes([2])),
    ('mup-ipv6-arch3', AFI.ipv6, SAFI.mup, bytes([3])),
]
FRAMED_SHAPE_IDS = [name for name, _afi, _safi, _architecture in FRAMED_SHAPES]


def header_for(safi: SAFI, architecture: bytes, code: int, length: int) -> bytes:
    """The type and length octets this family puts in front of its route."""
    if safi == SAFI.evpn:
        return bytes([code, length])
    if safi == SAFI.mup:
        return architecture + code.to_bytes(2, 'big') + bytes([length])
    return code.to_bytes(2, 'big') + length.to_bytes(2, 'big')


@pytest.mark.fuzz
@pytest.mark.parametrize('shape', FRAMED_SHAPES, ids=FRAMED_SHAPE_IDS)
@example(code=2, framed=(21, bytes(21)))
@given(code=st.integers(min_value=0, max_value=11), framed=framed(60, 255))
def test_a_framed_nlri_is_idempotent(shape: tuple[str, AFI, SAFI, bytes], code: int, framed: tuple[int, bytes]) -> None:
    """What a framed decoder accepts, it must re-encode into the same NLRI again."""
    _name, afi, safi, architecture = shape
    length, body = framed
    data = header_for(safi, architecture, code, length) + body

    nlri = decode(afi, safi, data)
    if nlri is None:
        return
    packed = nlri.pack_nlri(Negotiated.UNSET)
    again = decode(afi, safi, packed)
    assert again is not None, f'{afi}/{safi} refuses to decode what it just packed: {bytes(packed).hex()}'
    assert again.index() == nlri.index(), f'{afi}/{safi} is not stable across a pack and unpack cycle'


@pytest.mark.fuzz
@pytest.mark.parametrize('family', FAMILIES, ids=FAMILY_IDS)
@given(data=payload(0, 80))
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


# ---------------------------------------------------------------------------
# The seeded corpus, from tests/fuzz/corpus.py
#
# Everything above draws its bytes, and a drawn byte does not build a valid-but-unusual
# shape.  Counted on the gate profile, over every decode the drawn tests above perform:
#
#     flow-vpn v4      0 / 400        sr-policy v4     0 / 400
#     flow-vpn v6      0 / 400        sr-policy v6     0 / 400
#     vpls             0 / 400        flow v6          3 / 400
#     mpls-vpn v4      3 / 400        flow v4          7 / 400
#
# Five families decoded nothing at all, and four more were reached by luck.  A sweep which
# finds a decoder on a coin toss reads in the summary line exactly like one which enters it
# every run.  What follows hands each family a shape a real speaker could send: an eight
# byte route distinguisher before the flow rules, a length byte of 96 or 192 for sr-policy,
# a two byte length which agrees with the buffer for vpls, a label carrying the bottom of
# stack bit for mpls-vpn.
# ---------------------------------------------------------------------------

FAMILY_BY_NAME: dict[str, tuple[AFI, SAFI]] = {f'{afi}/{safi}': (afi, safi) for afi, safi in FAMILIES}

SEEDED_FAMILIES = sorted(corpus.NLRI_SEEDS)


@pytest.mark.fuzz
def test_every_registered_family_carries_a_seed() -> None:
    """A family with no legal seed is a family the corpus sweeps at arm's length.

    Set equality both ways on purpose.  A seed for a family which is not registered is dead
    weight that reads as coverage, and a family with no seed is the hole this corpus exists
    to close, so neither may pass quietly.

    The emptiness check is not decoration.  Emptying a list rather than removing its key
    leaves every test below iterating over nothing and reporting green, which is the same
    shape of failure one level down.
    """
    assert set(corpus.NLRI_SEEDS) == set(FAMILY_BY_NAME), {
        'families with no seed': sorted(set(FAMILY_BY_NAME) - set(corpus.NLRI_SEEDS)),
        'seeds for no family': sorted(set(corpus.NLRI_SEEDS) - set(FAMILY_BY_NAME)),
    }
    assert not [name for name, seeds in corpus.NLRI_SEEDS.items() if not seeds]


@pytest.mark.fuzz
@pytest.mark.parametrize('name', SEEDED_FAMILIES)
def test_every_seed_decodes_and_renders(name: str) -> None:
    """A seed the decoder refuses at the first byte is the bug this corpus fixes.

    So it is not enough that nothing crashes: each seed has to come back as a usable NLRI,
    which is also what makes `decode` check every rendering of it.
    """
    afi, safi = FAMILY_BY_NAME[name]
    for seed in corpus.NLRI_SEEDS[name]:
        assert decode(afi, safi, seed) is not None, f'{name} refused its own seed: {seed.hex()}'


@pytest.mark.fuzz
@pytest.mark.parametrize('name', SEEDED_FAMILIES)
def test_a_seeded_nlri_survives_a_pack_and_unpack(name: str) -> None:
    """What a decoder accepts, it must re-encode into something it accepts again.

    EXA_STYLE.md 1.1: a decoder which drops or invents bytes announces a route the peer
    never sent.  The drawn sweep above asserts the same thing and never reached these
    families with anything it could pack.

    It found two.  A VPLS NLRI announcing more than the decoder reads kept the peer's
    length in front of a truncated payload, so pack_nlri emitted an NLRI this decoder
    refuses; fixed in nlri/vpls.py.  A bgp-ls-vpn NLRI packed without the route
    distinguisher unpack_nlri had sliced out of it, eight bytes and a length short of what
    arrived, and two route distinguishers shared one index(); fixed in bgpls/nlri.py.
    """
    afi, safi = FAMILY_BY_NAME[name]
    for seed in corpus.NLRI_SEEDS[name]:
        nlri = decode(afi, safi, seed)
        assert nlri is not None
        packed = nlri.pack_nlri(Negotiated.UNSET)
        again = decode(afi, safi, packed)
        assert again is not None, f'{name} refuses to decode what it packed: {packed.hex()} from {seed.hex()}'
        assert again.index() == nlri.index(), f'{name} is not stable across pack and unpack: {packed.hex()}'


@pytest.mark.fuzz
@pytest.mark.parametrize('name', sorted(corpus.REFUSED_SEEDS))
def test_a_flow_nlri_with_no_component_is_refused(name: str) -> None:
    """These decode on 5.0 and are refused here, which is the stricter answer.

    A flow specification with no component matches every packet on the box, so this tree
    answers with NLRI.INVALID and the caller treats the route as a withdraw.  Pinned as
    negative coverage: relaxing that check has to go red somewhere.
    """
    afi, safi = FAMILY_BY_NAME[name]
    for seed in corpus.REFUSED_SEEDS[name]:
        assert decode(afi, safi, seed) is None, f'{name} accepted a component-less flow: {seed.hex()}'


@pytest.mark.fuzz
@pytest.mark.parametrize('name', SEEDED_FAMILIES)
def test_the_whole_corpus_only_raises_notify(name: str) -> None:
    """Every seed, every fill pattern, and both length framings of each.

    The count at the end is what stops this being another green sweep over nothing: a
    family whose framing changes so that not one input decodes goes red here rather than
    passing with an empty loop.
    """
    afi, safi = FAMILY_BY_NAME[name]
    decoded = sum(decode(afi, safi, seed) is not None for seed in corpus.seeds_for(name))
    assert decoded, f'{name}: not one corpus input decoded, so this sweep proves nothing'


@pytest.mark.registry_floor
def test_the_registry_this_file_parametrises_from_is_whole() -> None:
    """A parametrised sweep does not FAIL on a thin registry, it SHRINKS.

    This one parametrises over NLRI.known_families(), which reads registered_families
    and NOT registered_nlri: thinning the dict left the parametrisation at full width, so
    the first version of the experiment reported this file clean for the wrong reason.

    Session 5.0 found this shape on their branch: 2060 passing tests became 296 passing
    tests, still green, and a summary line reads the same either way.  It is the import
    order failure from the top of the list, so it is the one which actually happens.

    Measured here by thinning the registries to three entries and counting: 104 tests became 41, all green.
    """
    assert len(FAMILIES) >= MIN_FAMILIES, (
        f'only {len(FAMILIES)} families are registered, so this file sweeps a fraction of them'
    )
