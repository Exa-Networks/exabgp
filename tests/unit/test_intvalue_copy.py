"""An IntValue is copied by being shared, so a deepcopy works compiled as it does not.

IntValue.value is Final. Compiled by mypyc 2.4, a Final attribute cannot be set, and
copy.deepcopy rebuilt the copy by setting it: `configuration validate -r`, which deep-copies
each neighbor, failed in the compiled build and in the one-file binary, with
"attribute 'value' of 'IntValue' objects is not writable". The value never changes, and
what a subclass adds (a name) comes from it, so the copy is the object itself.

The compiled stage of qa/bin/test_everything runs this against the mypyc build.

Created by Thomas Mangin on 2026-10-28.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI
from exabgp.util.intvalue import IntValue

CONFIGURATION = Path(__file__).parents[2] / 'etc' / 'exabgp' / 'conf-ipself6.conf'


@pytest.mark.parametrize('value', [IntValue(7), ASN(65000), AFI.ipv6, Capability.CODE.ROLE])
def test_an_int_value_is_its_own_copy(value: IntValue) -> None:
    assert copy.copy(value) is value
    assert copy.deepcopy(value) is value


def test_a_configured_neighbor_can_be_deep_copied() -> None:
    configuration = Configuration([str(CONFIGURATION)])
    assert configuration.reload() is True, configuration.error

    for neighbor in configuration.neighbors.values():
        copied = copy.deepcopy(neighbor)
        assert copied is not neighbor
        assert copied.session.peer_as == neighbor.session.peer_as
