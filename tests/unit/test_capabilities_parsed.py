"""Capabilities.parsed gives a capability as the class the registry decodes its code as.

Created by Thomas Mangin on 2026-10-28.
Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import sys

import pytest

from exabgp.bgp.message.open.capability.addpath import AddPath
from exabgp.bgp.message.open.capability.capabilities import Capabilities
from exabgp.bgp.message.open.capability.capability import Capability
from exabgp.bgp.message.open.capability.ms import MultiSession
from exabgp.bgp.message.open.capability.role import Role, RoleValue


def test_a_capability_present_is_given_as_its_class() -> None:
    capabilities = Capabilities()
    capabilities[Capability.CODE.ROLE] = Role(RoleValue.PROVIDER)

    role = capabilities.parsed(Capability.CODE.ROLE, Role)

    assert role is capabilities[Capability.CODE.ROLE]
    assert capabilities.role() == RoleValue.PROVIDER


def test_a_capability_absent_is_none() -> None:
    assert Capabilities().parsed(Capability.CODE.ADD_PATH, AddPath) is None
    assert Capabilities().role() == RoleValue.NO_ROLE


def test_a_class_registered_for_two_codes_is_found_under_either() -> None:
    capabilities = Capabilities()
    cisco = MultiSession()
    capabilities[Capability.CODE.MULTISESSION_CISCO] = cisco

    assert capabilities.parsed(Capability.CODE.MULTISESSION_CISCO, MultiSession) is cisco


@pytest.mark.skipif(sys.flags.optimize > 0, reason='checks an assert of ours, which -O removes')
def test_asking_for_a_class_the_code_is_not_decoded_as_is_our_bug() -> None:
    capabilities = Capabilities()
    capabilities[Capability.CODE.ROLE] = Role(RoleValue.PROVIDER)

    with pytest.raises(AssertionError, match='is not decoded as AddPath'):
        capabilities.parsed(Capability.CODE.ROLE, AddPath)


def test_the_four_octet_asn_must_be_there() -> None:
    with pytest.raises(KeyError):
        Capabilities().four_octet_asn()
