"""RFC 6793 4.2.3: rebuilding the AS path from an AS_PATH and the AS4_PATH beside it.

    "the AS path information SHALL be constructed by taking as many AS numbers and
    path segments as necessary from the leading part of the AS_PATH attribute, and
    then prepending them to the AS4_PATH attribute so that the AS path information
    has a number of AS numbers identical to that of the AS_PATH attribute"

and, the sentence before it, when the AS_PATH holds fewer AS numbers than the AS4_PATH:

    "the AS4_PATH attribute SHALL be ignored, and the AS_PATH attribute SHALL be
    taken as the AS path information"

`Attributes.merge_attributes` is where that happens, and it did not run at all.  It read
`as2path.as_seq` and `as4path.as_seq`, fields which `ASPath` has not had since it was
refactored to hold one `aspath` list of path segments: every occurrence of `as_seq` and
`as_set` in this tree was inside `attributes.py` itself.  The call site in
`Attributes.unpack` is reached whenever a peer's UPDATE carries both attributes, which is
the ordinary case for a two-octet-ASN session behind an older speaker, so the wire reached
an `AttributeError` rather than a `Notify`, out of the decoder and into the reactor's
catch-all.

The count is per RFC 4271 9.1.2.2, which RFC 6793 4.2.3 leans on twice: an AS_SET is one
AS number however many members it holds, a sequence is its length, and a confederation
segment is none (RFC 5065 5.3).  Counting members instead would be wrong only for a set
holding more than one, which is why one case below has a two-member set: with every set
holding a single member, `total += 1` and `total += len(segment)` cannot be told apart.
"""

from __future__ import annotations

from struct import pack
from typing import Any
from unittest.mock import Mock

import pytest

from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute.aspath import CONFED_SEQUENCE, SEQUENCE, SET, ASPath
from exabgp.bgp.message.update.attribute.attributes import Attributes

TRANSITIVE = 0x40
OPTIONAL_TRANSITIVE = 0xC0

# AS numbers which fit in two octets, and two which do not
MAPPABLE = 65001
ALSO_MAPPABLE = 65002
NON_MAPPABLE = 100000
ALSO_NON_MAPPABLE = 100001


@pytest.fixture(autouse=True)
def _logger() -> Any:
    """The parser logs every attribute it sees, and the logger is not set up under pytest."""
    from exabgp.logger.option import option

    logger, formater = option.logger, option.formater
    option.logger = Mock()
    option.formater = Mock(return_value='formatted message')
    yield
    option.logger, option.formater = logger, formater


def negotiated() -> Any:
    """An old session: two octet AS numbers on the wire, so the AS4_ attributes are used."""
    session = Mock()
    session.asn4 = False
    session.families = []
    session.nexthop = []
    session.msg_size = 4096
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    session.neighbor = neighbor
    return session


def segment(kind: int, asns: list[int], octets: int) -> bytes:
    packer = '!L' if octets == 4 else '!H'
    return bytes([kind, len(asns)]) + b''.join(pack(packer, asn) for asn in asns)


def attribute(code: int, flag: int, value: bytes) -> bytes:
    return bytes([flag, code, len(value)]) + value


def wire(two_octet: bytes, four_octet: bytes) -> bytes:
    return attribute(Attribute.CODE.AS_PATH, TRANSITIVE, two_octet) + attribute(
        Attribute.CODE.AS4_PATH, OPTIONAL_TRANSITIVE, four_octet
    )


def path_of(payload: bytes) -> ASPath:
    parsed = Attributes.unpack(payload, Direction.IN, negotiated())
    decoded = parsed[Attribute.CODE.AS_PATH]
    assert isinstance(decoded, ASPath), 'the AS_PATH did not decode to an AS path'
    assert Attribute.CODE.AS4_PATH not in parsed, 'the AS4_PATH survived the merge'
    return decoded


def counted(path: ASPath) -> int:
    """AS numbers in a path, by RFC 4271 9.1.2.2: a set is one, a confederation segment none."""
    total = 0
    for content in path.aspath:
        if isinstance(content, SET):
            total += 1
        elif isinstance(content, SEQUENCE):
            total += len(content)
    return total


def flattened(path: ASPath) -> list[list[int]]:
    return [[int(asn) for asn in content] for content in path.aspath]


def test_the_reported_update_decodes_instead_of_raising_attribute_error() -> None:
    """An UPDATE carrying both attributes, which is what reached the AttributeError.

    A two-octet session behind a four-octet-capable peer: the AS_PATH carries AS_TRANS
    where the real number did not fit, and the AS4_PATH carries the real number.
    """
    payload = wire(
        segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2),
        segment(SET.ID, [NON_MAPPABLE], 4),
    )

    path = path_of(payload)

    assert path.string(), 'the merged path must render'


RECONSTRUCTION = [
    (
        'a sequence shorter than the AS_PATH',
        segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS), int(AS_TRANS)], 2),
        segment(SEQUENCE.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
        3,
    ),
    (
        'a sequence as long as the AS_PATH',
        segment(SEQUENCE.ID, [int(AS_TRANS), int(AS_TRANS)], 2),
        segment(SEQUENCE.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
        2,
    ),
    (
        'an AS4_PATH holding only a set',
        segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2),
        segment(SET.ID, [NON_MAPPABLE], 4),
        2,
    ),
    (
        'an AS4_PATH holding a set after a sequence',
        segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS), int(AS_TRANS)], 2) + segment(SET.ID, [ALSO_MAPPABLE], 2),
        segment(SEQUENCE.ID, [NON_MAPPABLE], 4) + segment(SET.ID, [ALSO_NON_MAPPABLE], 4),
        4,
    ),
    (
        'an AS4_PATH holding a set of two, which is one AS number and not two',
        segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2),
        segment(SET.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
        2,
    ),
]

IDS = [what for what, _, _, _ in RECONSTRUCTION]


@pytest.mark.parametrize('what,two_octet,four_octet,expected', RECONSTRUCTION, ids=IDS)
def test_the_reconstructed_path_has_as_many_as_numbers_as_the_as_path(
    what: str, two_octet: bytes, four_octet: bytes, expected: int
) -> None:
    """The rule names one number, and it is this one."""
    path = path_of(wire(two_octet, four_octet))

    assert (
        counted(path) == expected
    ), f'{what}: {counted(path)} AS numbers where the AS_PATH had {expected} ({path.string()})'


@pytest.mark.parametrize('what,two_octet,four_octet,expected', RECONSTRUCTION, ids=IDS)
def test_the_reconstruction_never_makes_the_path_longer_than_the_as_path(
    what: str, two_octet: bytes, four_octet: bytes, expected: int
) -> None:
    """A peer must not be able to lengthen its own path by what it puts in its AS4_PATH."""
    path = path_of(wire(two_octet, four_octet))

    assert counted(path) <= expected, f'{what} produced a path longer than the AS_PATH'


def test_the_leading_part_of_the_as_path_is_kept() -> None:
    """Not merely the right length: the AS numbers the AS4_PATH does not replace stay put."""
    path = path_of(
        wire(
            segment(SEQUENCE.ID, [MAPPABLE, ALSO_MAPPABLE, int(AS_TRANS)], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE], 4),
        )
    )

    assert flattened(path) == [
        [MAPPABLE, ALSO_MAPPABLE, NON_MAPPABLE]
    ], 'the leading AS numbers of the AS_PATH were not prepended to the AS4_PATH'


def test_an_as4_path_longer_than_the_as_path_is_ignored() -> None:
    """RFC 6793 4.2.3: the AS_PATH is then the answer, and the AS4_PATH is dropped."""
    path = path_of(
        wire(
            segment(SEQUENCE.ID, [MAPPABLE], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE, ALSO_NON_MAPPABLE], 4),
        )
    )

    assert flattened(path) == [[MAPPABLE]], 'the AS_PATH should have been taken as it stands'


def test_an_as4_path_no_longer_than_the_as_path_is_not_ignored() -> None:
    """Ignoring it always would satisfy the test above and lose every four-octet AS number."""
    path = path_of(
        wire(
            segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE], 4),
        )
    )

    assert flattened(path) == [[MAPPABLE, NON_MAPPABLE]], 'the four octet AS number was lost'


def test_the_join_is_one_sequence_rather_than_two() -> None:
    """Two adjacent sequences are the seam of the merge, not something the peer sent.

    Adjacent AS_SETs are deliberately left alone: two of them count two AS numbers and one
    holding both members counts one, so joining those would change the length of the path.
    """
    path = path_of(
        wire(
            segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE], 4),
        )
    )

    assert len(path.aspath) == 1, f'the merge left a seam: {path.string()}'


def test_the_merged_path_can_be_re_encoded() -> None:
    """The merged attribute is re-advertised, so it has to survive a pack."""
    path = path_of(
        wire(
            segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2),
            segment(SEQUENCE.ID, [NON_MAPPABLE], 4),
        )
    )
    onward = Mock()
    onward.asn4 = True

    assert path.pack(onward), 'the merged AS path could not be packed'


# ================================ an AS4_PATH which was never merged has to pack


def test_an_as4_path_survives_being_re_encoded() -> None:
    """A peer can send an AS4_PATH with no AS_PATH beside it, and nothing stops it.

    `Attributes.MANDATORY` names AS_PATH but is read nowhere, so such an UPDATE parses to a
    collection holding AS4_PATH alone.  `Attributes.merge_attributes` is then never reached,
    the attribute survives the parse, and `Attributes.pack` calls `AS4Path.pack` on it when
    the route is advertised onwards: AS4_PATH is in neither `INTERNAL` nor the `skip` table.

    `AS4Path.pack` called `ASPath.pack(self, True)`, passing `True` where a negotiated
    session belongs, so the first thing it did was read `True.asn4`.  Peer bytes reached an
    `AttributeError` out of the pack path, and had that been fixed the result was still
    discarded rather than returned.
    """
    payload = attribute(Attribute.CODE.AS4_PATH, OPTIONAL_TRANSITIVE, segment(SEQUENCE.ID, [NON_MAPPABLE], 4))
    parsed = Attributes.unpack(payload, Direction.IN, negotiated())
    assert Attribute.CODE.AS4_PATH in parsed, 'an AS4_PATH with no AS_PATH beside it should parse'

    onward = Mock()
    onward.asn4 = True

    packed = parsed[Attribute.CODE.AS4_PATH].pack(onward)

    assert packed, 'AS4Path.pack returned nothing'
    assert packed[1] == Attribute.CODE.AS4_PATH, 'the attribute was packed under the wrong code'
    assert packed[0] == OPTIONAL_TRANSITIVE, 'RFC 6793 4.2.1 makes AS4_PATH optional transitive'
    assert packed.endswith(
        segment(SEQUENCE.ID, [NON_MAPPABLE], 4)
    ), 'an AS4_PATH carries four octet AS numbers whatever the session negotiated'


# ============================== RFC 6793 4.2.2 and 6: confederation segments


def attributes_of(packed: bytes) -> dict[int, bytes]:
    """The attribute stream we produced, as a mapping of code to value."""
    found = {}
    offset = 0
    while offset < len(packed):
        flag, code = packed[offset], packed[offset + 1]
        if flag & Attribute.Flag.EXTENDED_LENGTH:
            length = int.from_bytes(packed[offset + 2 : offset + 4], 'big')
            offset += 4
        else:
            length = packed[offset + 2]
            offset += 3
        found[code] = bytes(packed[offset : offset + length])
        offset += length
    assert offset == len(packed), 'the attributes we packed do not parse'
    return found


def segment_kinds(value: bytes, octets: int = 4) -> list[int]:
    kinds = []
    offset = 0
    while offset < len(value):
        kinds.append(value[offset])
        offset += 2 + value[offset + 1] * octets
    assert offset == len(value), 'the path segments we packed do not parse'
    return kinds


def old_peer() -> Any:
    """A peer which did not offer four octet AS numbers, so AS4_ attributes are built."""
    session = Mock()
    session.asn4 = False
    return session


def test_the_as4_path_we_build_holds_no_confederation_segment() -> None:
    """RFC 6793 4.2.2: the AS4_PATH we build has to exclude confederation segments.

    Copying the path unfiltered published confederation membership past the confederation
    border, in an attribute RFC 6793 6 says may not carry those segment types at all.
    """
    path = ASPath([CONFED_SEQUENCE([ASN(64512)]), SEQUENCE([ASN(NON_MAPPABLE)])])

    packed = attributes_of(path.pack(old_peer()))

    assert Attribute.CODE.AS4_PATH in packed, 'a four octet AS number needs an AS4_PATH'
    assert segment_kinds(packed[Attribute.CODE.AS4_PATH]) == [
        SEQUENCE.ID
    ], 'the AS4_PATH carries a confederation segment'
    assert segment_kinds(packed[Attribute.CODE.AS_PATH], 2) == [
        CONFED_SEQUENCE.ID,
        SEQUENCE.ID,
    ], 'the AS_PATH itself must keep every segment it had'


def test_no_as4_path_is_built_when_no_segment_is_left_to_carry() -> None:
    """RFC 6793 6 gives AS4_PATH no empty form, so a confederation-only path sends none."""
    path = ASPath([CONFED_SEQUENCE([ASN(NON_MAPPABLE)])])

    packed = attributes_of(path.pack(old_peer()))

    assert Attribute.CODE.AS4_PATH not in packed, 'an empty AS4_PATH was sent'
    assert Attribute.CODE.AS_PATH in packed, 'the AS_PATH is still owed to the peer'


def test_a_confederation_segment_is_discarded_from_a_received_as4_path() -> None:
    """RFC 6793 6: an AS4_PATH which arrives with one has that path segment discarded."""
    payload = attribute(
        Attribute.CODE.AS4_PATH,
        OPTIONAL_TRANSITIVE,
        segment(CONFED_SEQUENCE.ID, [64512], 4) + segment(SEQUENCE.ID, [NON_MAPPABLE], 4),
    )

    parsed = Attributes.unpack(payload, Direction.IN, negotiated())

    assert flattened(parsed[Attribute.CODE.AS4_PATH]) == [
        [NON_MAPPABLE]
    ], 'the confederation segment survived the parse'


def test_a_confederation_as_number_from_an_as4_path_does_not_reach_the_published_path() -> None:
    """Why the discard above matters: the merge folds what is left into what we publish.

    A confederation segment counts as no AS number, so the reconstruction carries it along
    whatever its length, and a peer outside the confederation could put a confederation AS
    number into the path we advertise onwards.
    """
    path = path_of(
        wire(
            segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2),
            segment(CONFED_SEQUENCE.ID, [64512], 4) + segment(SEQUENCE.ID, [NON_MAPPABLE], 4),
        )
    )

    assert flattened(path) == [[MAPPABLE, NON_MAPPABLE]], f'a confederation AS number reached {path.string()}'


# ==================================== RFC 6793 4.2.3: what the AGGREGATOR decides


SPEAKER = pack('!4B', 192, 0, 2, 1)


def aggregator(asn: int, octets: int) -> bytes:
    code = Attribute.CODE.AS4_AGGREGATOR if octets == 4 else Attribute.CODE.AGGREGATOR
    packer = '!L' if octets == 4 else '!H'
    return attribute(code, OPTIONAL_TRANSITIVE, pack(packer, asn) + SPEAKER)


def test_an_as4_aggregator_decodes_on_a_two_octet_session() -> None:
    """RFC 6793 4.2.2: AS4_AGGREGATOR is eight octets whatever the session negotiated.

    Aggregator4 inherited Aggregator.unpack, which sizes itself on negotiated.asn4, so the
    only kind of session which is ever sent an AS4_AGGREGATOR was the one which answered a
    correctly formed one with a NOTIFICATION, and the rules below could never be reached.
    """
    parsed = Attributes.unpack(aggregator(NON_MAPPABLE, 4), Direction.IN, negotiated())

    decoded = parsed[Attribute.CODE.AS4_AGGREGATOR]
    assert int(decoded.asn) == NON_MAPPABLE, 'the four octet aggregating AS was not read'


def test_an_aggregator_which_is_not_as_trans_drops_both_as4_attributes() -> None:
    """RFC 6793 4.2.3: a real aggregating AS was not written by a translating speaker."""
    payload = (
        aggregator(MAPPABLE, 2)
        + aggregator(NON_MAPPABLE, 4)
        + wire(segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2), segment(SEQUENCE.ID, [NON_MAPPABLE], 4))
    )

    parsed = Attributes.unpack(payload, Direction.IN, negotiated())

    assert Attribute.CODE.AS4_AGGREGATOR not in parsed, 'the AS4_AGGREGATOR should have been discarded'
    assert Attribute.CODE.AS4_PATH not in parsed, 'the AS4_PATH should have been discarded'
    assert int(parsed[Attribute.CODE.AGGREGATOR].asn) == MAPPABLE, 'the AGGREGATOR is the aggregating node'
    assert flattened(parsed[Attribute.CODE.AS_PATH]) == [[MAPPABLE, int(AS_TRANS)]], 'the AS_PATH is the path, unmerged'


def test_an_aggregator_of_as_trans_is_replaced_by_the_as4_aggregator() -> None:
    """RFC 6793 4.2.3: AS_TRANS is a placeholder, and publishing it names AS 23456 an aggregator."""
    payload = aggregator(int(AS_TRANS), 2) + aggregator(NON_MAPPABLE, 4)

    parsed = Attributes.unpack(payload, Direction.IN, negotiated())

    assert Attribute.CODE.AGGREGATOR not in parsed, 'AS 23456 was published as the aggregating AS'
    assert int(parsed[Attribute.CODE.AS4_AGGREGATOR].asn) == NON_MAPPABLE, 'the real aggregating AS was lost'


def test_an_as4_path_with_no_aggregator_beside_it_is_still_merged() -> None:
    """The aggregator rules must not stop the reconstruction when no AGGREGATOR was sent."""
    path = path_of(wire(segment(SEQUENCE.ID, [MAPPABLE, int(AS_TRANS)], 2), segment(SEQUENCE.ID, [NON_MAPPABLE], 4)))

    assert flattened(path) == [[MAPPABLE, NON_MAPPABLE]], 'the merge stopped happening'
