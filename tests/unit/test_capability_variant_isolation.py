#!/usr/bin/env python3
# encoding: utf-8
"""test_capability_variant_isolation.py

Regression tests for F6: Capability.klass() used to write the wire code it
resolved directly onto the shared class object (`kls.ID = what`). RouteRefresh
is registered under both an RFC code (0x02) and a Cisco code (0x80);
MultiSession under both 0x44 (RFC) and 0x83 (Cisco). Because both codes
resolve to the *same* class object, one peer's OPEN carrying the Cisco code
rewrote what every other already-established peer's capability instance
reported in str()/json() -- a process-wide, peer-triggerable display/API
corruption (wire encoding was never affected: packing keys off the registry
dict key, not `.ID`).

The fix records the variant on the *instance* in Capability.unpack(), which
knows the code actually received, instead of mutating the class in klass().

Created for ExaBGP testing framework
License: 3-clause BSD
"""

from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import RouteRefresh
from exabgp.bgp.message.open.capability import LinkLocalNextHop
from exabgp.bgp.message.open.capability.capability import CapabilityCode
from exabgp.bgp.message.open.capability.ms import MultiSession


# ==============================================================================
# Instance isolation -- the actual regression
# ==============================================================================


def test_route_refresh_instance_isolated_across_sessions() -> None:
    """A RouteRefresh instance unpacked under the RFC code must keep reporting
    RFC even after a *later* unpack under the Cisco code, for a different
    session, creates a second instance that reports Cisco.

    The ordering matters: asserting A only before B exists would miss the bug,
    since the corruption is that creating B retroactively rewrites A.
    """
    session_a: Capabilities = Capabilities()
    session_b: Capabilities = Capabilities()

    instance_a = Capability.unpack(CapabilityCode(CapabilityCode.ROUTE_REFRESH), session_a, b'')
    assert isinstance(instance_a, RouteRefresh)
    assert str(instance_a) == 'Route Refresh'
    assert instance_a.json() == '{ "name": "route-refresh", "variant": "RFC" }'

    instance_b = Capability.unpack(CapabilityCode(CapabilityCode.ROUTE_REFRESH_CISCO), session_b, b'')
    assert isinstance(instance_b, RouteRefresh)
    assert str(instance_b) == 'Cisco Route Refresh'
    assert instance_b.json() == '{ "name": "route-refresh", "variant": "Cisco" }'

    # instance_a must STILL report RFC now that instance_b (Cisco) exists.
    assert str(instance_a) == 'Route Refresh'
    assert instance_a.json() == '{ "name": "route-refresh", "variant": "RFC" }'


def test_multisession_instance_isolated_across_sessions() -> None:
    """Same isolation requirement for MultiSession (0x44 RFC / 0x83 Cisco)."""
    session_a: Capabilities = Capabilities()
    session_b: Capabilities = Capabilities()

    instance_a = Capability.unpack(CapabilityCode(CapabilityCode.MULTISESSION), session_a, b'\x00')
    assert isinstance(instance_a, MultiSession)
    assert ' (RFC)' in str(instance_a)
    assert '"variant": "RFC"' in instance_a.json()

    instance_b = Capability.unpack(CapabilityCode(CapabilityCode.MULTISESSION_CISCO), session_b, b'\x00')
    assert isinstance(instance_b, MultiSession)
    assert ' (RFC)' not in str(instance_b)
    assert '"variant": "Cisco"' in instance_b.json()

    # instance_a must STILL report RFC now that instance_b (Cisco) exists.
    assert ' (RFC)' in str(instance_a)
    assert '"variant": "RFC"' in instance_a.json()


# ==============================================================================
# Class object must never be mutated
# ==============================================================================


def test_route_refresh_class_object_not_mutated() -> None:
    """After unpacking both variants, the class-level ID must still equal the
    class-definition value (the RFC code). A future refactor that reintroduces
    `kls.ID = what` in klass() would flip this to the Cisco code.
    """
    before = RouteRefresh.__dict__.get('ID')

    session: Capabilities = Capabilities()
    Capability.unpack(CapabilityCode(CapabilityCode.ROUTE_REFRESH_CISCO), session, b'')

    after = RouteRefresh.__dict__.get('ID')
    assert before == after == Capability.CODE.ROUTE_REFRESH


def test_multisession_class_object_not_mutated() -> None:
    before = MultiSession.__dict__.get('ID')

    session: Capabilities = Capabilities()
    Capability.unpack(CapabilityCode(CapabilityCode.MULTISESSION_CISCO), session, b'\x00')

    after = MultiSession.__dict__.get('ID')
    assert before == after == Capability.CODE.MULTISESSION


# ==============================================================================
# Negative space
# ==============================================================================


def test_single_code_capability_still_reports_correctly() -> None:
    """A capability registered under only one code (no RFC/Cisco split) must
    keep working: this fix must not regress the common case.
    """
    session: Capabilities = Capabilities()
    instance = Capability.unpack(CapabilityCode(CapabilityCode.LINK_LOCAL_NEXTHOP), session, b'')
    assert isinstance(instance, LinkLocalNextHop)
    assert str(instance) == 'Link-Local NextHop'
    assert instance.ID == Capability.CODE.LINK_LOCAL_NEXTHOP


def test_route_refresh_wire_encoding_unchanged() -> None:
    """Packing must still key off the registry dict key, not `.ID` -- moving
    the variant write to the instance must not change a single byte on the
    wire for either variant.
    """
    caps_rfc = Capabilities()
    caps_rfc[Capability.CODE.ROUTE_REFRESH] = RouteRefresh()
    assert caps_rfc.pack_capabilities() == b'\x04\x02\x02\x02\x00'

    caps_cisco = Capabilities()
    caps_cisco[Capability.CODE.ROUTE_REFRESH_CISCO] = RouteRefresh()
    assert caps_cisco.pack_capabilities() == b'\x04\x02\x02\x80\x00'


def test_multisession_wire_encoding_unchanged() -> None:
    caps_rfc = Capabilities()
    caps_rfc[Capability.CODE.MULTISESSION] = MultiSession()
    assert caps_rfc.pack_capabilities() == b'\x05\x02\x03\x44\x01\x00'

    caps_cisco = Capabilities()
    caps_cisco[Capability.CODE.MULTISESSION_CISCO] = MultiSession()
    assert caps_cisco.pack_capabilities() == b'\x05\x02\x03\x83\x01\x00'


# ==============================================================================
# Equality contract: variant IS part of identity
# ==============================================================================


def test_route_refresh_equality_is_id_sensitive() -> None:
    """RouteRefresh.__eq__ compares by `.ID` (self.ID == other.ID), and that is
    unchanged by this fix. Before the fix, this comparison was accidentally
    trivial: since neither side ever carried an instance-level ID, both `self.ID`
    and `other.ID` read the *same* mutable class attribute at comparison time --
    whatever klass() had most recently written -- so `self.ID == other.ID` was
    True for any two RouteRefresh instances regardless of which variant either
    one actually represented. Now that unpack() records the ID per instance,
    equality actually distinguishes RFC from Cisco, matching what __str__/json()
    already reported. This test pins that: don't let a future change make
    equality variant-blind again without a deliberate decision.
    """
    session_a: Capabilities = Capabilities()
    session_b: Capabilities = Capabilities()

    rfc_instance = Capability.unpack(CapabilityCode(CapabilityCode.ROUTE_REFRESH), session_a, b'')
    cisco_instance = Capability.unpack(CapabilityCode(CapabilityCode.ROUTE_REFRESH_CISCO), session_b, b'')

    assert rfc_instance.ID != cisco_instance.ID
    assert rfc_instance != cisco_instance
    assert rfc_instance == RouteRefresh()  # bare instance falls back to the RFC class default
    assert cisco_instance != RouteRefresh()
    assert rfc_instance != object()
