"""Each AS_PATH segment says what kind it is: ordered or not, a confederation's or not.

The code asks the segment (ORDERED, CONFED) where it tested its class. Those two fields are
then what decides how a path is counted, prepended to and stripped of its confederation, so
they are held here to what RFC 4271 4.3 and RFC 5065 3 define each segment type to be.

Created by Thomas Mangin on 2026-10-28.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.update.attribute.aspath import CONFED_SEQUENCE, CONFED_SET, SEQUENCE, SET, ASPath, Segment


@pytest.mark.parametrize(
    ('segment', 'code', 'ordered', 'confed'),
    [
        (SET, 1, False, False),
        (SEQUENCE, 2, True, False),
        (CONFED_SEQUENCE, 3, True, True),
        (CONFED_SET, 4, False, True),
    ],
)
def test_each_segment_type_is_what_the_rfc_says(segment: type[Segment], code: int, ordered: bool, confed: bool) -> None:
    assert segment.ID == code
    assert segment.ORDERED is ordered
    assert segment.CONFED is confed


def test_a_path_is_stripped_of_its_confederation_segments_only() -> None:
    path = ASPath.make_aspath(
        [CONFED_SEQUENCE([ASN(65001)]), CONFED_SET([ASN(65002)]), SEQUENCE([ASN(1), ASN(2)]), SET([ASN(3)])]
    )

    assert path.has_confed()
    stripped = path.without_confed()
    assert not stripped.has_confed()
    assert [segment.ID for segment in stripped.aspath] == [SEQUENCE.ID, SET.ID]
