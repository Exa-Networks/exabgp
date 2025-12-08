#!/usr/bin/env python3
# encoding: utf-8
"""Tests for _normalize_nlri_type() and configuration parsing with MPLS labels

This test file was created to catch issues with NLRI type normalization,
specifically the bug where Label NLRIs were incorrectly downgraded to INET
because _normalize_nlri_type() checked for the non-existent _labels_packed
attribute instead of the correct _has_labels attribute.

Key test scenarios:
1. Label NLRI should NOT be downgraded to INET
2. IPVPN NLRI should NOT be downgraded when it has RD
3. Settings pattern correctly passes labels through from_settings()
4. Configuration parsing preserves NLRI type through the full pipeline
"""

import pytest

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri import CIDR, INET, IPVPN, Label
from exabgp.bgp.message.update.nlri.qualifier import Labels, RouteDistinguisher
from exabgp.bgp.message.update.nlri.settings import INETSettings
from exabgp.configuration.static.route import ParseStaticRoute
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP


class TestNormalizeNlriTypeLabel:
    """Test _normalize_nlri_type() preserves Label NLRI with labels."""

    def test_label_with_labels_preserved(self) -> None:
        """Label NLRI with labels should not be downgraded to INET.

        This was the original bug: _normalize_nlri_type() checked for
        _labels_packed which doesn't exist in packed-bytes-first Label.
        The fix uses _has_labels instead.
        """
        # Create Label with labels
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        nlri = Label.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.nlri_mpls,
            Action.ANNOUNCE,
            labels=Labels.make_labels([800001]),
        )

        # Verify initial state
        assert isinstance(nlri, Label)
        assert nlri._has_labels is True
        assert nlri.labels != Labels.NOLABEL

        # Apply normalization
        result = ParseStaticRoute._normalize_nlri_type(nlri)

        # Should remain Label, not be downgraded to INET
        assert isinstance(result, Label)
        assert not isinstance(result, IPVPN)  # Should not be IPVPN
        assert result._has_labels is True
        assert result.labels == nlri.labels

    def test_label_without_labels_downgraded_to_inet(self) -> None:
        """Label NLRI without labels (NOLABEL) should be downgraded to INET.

        When a Label NLRI has no actual labels, it's effectively an INET route
        and should be normalized to INET for consistency.
        """
        # Create Label without labels (NOLABEL)
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        nlri = Label.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.nlri_mpls,
            Action.ANNOUNCE,
            labels=None,  # No labels
        )

        # Verify initial state
        assert isinstance(nlri, Label)
        assert nlri._has_labels is False
        assert nlri.labels == Labels.NOLABEL

        # Apply normalization
        result = ParseStaticRoute._normalize_nlri_type(nlri)

        # Should be downgraded to INET (exact type check)
        assert type(result) is INET  # noqa: E721


class TestNormalizeNlriTypeIPVPN:
    """Test _normalize_nlri_type() preserves IPVPN NLRI with RD."""

    def test_ipvpn_with_rd_preserved(self) -> None:
        """IPVPN NLRI with RD should not be downgraded."""
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        rd = RouteDistinguisher.make_from_elements('65000', 1)
        nlri = IPVPN.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.mpls_vpn,
            Action.ANNOUNCE,
            labels=Labels.make_labels([800001]),
            rd=rd,
        )

        # Verify initial state
        assert isinstance(nlri, IPVPN)
        assert nlri._has_rd is True

        # Apply normalization
        result = ParseStaticRoute._normalize_nlri_type(nlri)

        # Should remain IPVPN
        assert isinstance(result, IPVPN)
        assert result.rd == rd

    def test_ipvpn_without_rd_downgraded(self) -> None:
        """IPVPN NLRI without RD should be downgraded to Label or INET."""
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        nlri = IPVPN.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.mpls_vpn,
            Action.ANNOUNCE,
            labels=Labels.make_labels([800001]),
            rd=None,  # No RD
        )

        # Verify initial state
        assert isinstance(nlri, IPVPN)
        assert nlri._has_rd is False
        assert nlri._has_labels is True

        # Apply normalization
        result = ParseStaticRoute._normalize_nlri_type(nlri)

        # Should be downgraded to Label (has labels but no RD)
        assert isinstance(result, Label)
        assert not isinstance(result, IPVPN)


class TestNormalizeNlriTypeINET:
    """Test _normalize_nlri_type() handles INET NLRI correctly."""

    def test_inet_unchanged(self) -> None:
        """INET NLRI should pass through unchanged."""
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        nlri = INET.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.unicast,
            Action.ANNOUNCE,
        )

        # Verify initial state
        assert type(nlri) is INET  # noqa: E721

        # Apply normalization
        result = ParseStaticRoute._normalize_nlri_type(nlri)

        # Should remain INET
        assert type(result) is INET  # noqa: E721


class TestLabelFromSettings:
    """Test Label.from_settings() correctly includes labels."""

    def test_from_settings_includes_labels(self) -> None:
        """Label created via from_settings() should include labels in _packed."""
        settings = INETSettings()
        settings.cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        settings.afi = AFI.ipv4
        settings.safi = SAFI.nlri_mpls
        settings.action = Action.ANNOUNCE
        settings.nexthop = IP.from_string('198.51.100.1')
        settings.labels = Labels.make_labels([800001])

        nlri = Label.from_settings(settings)

        # Verify the Label has labels
        assert isinstance(nlri, Label)
        assert nlri._has_labels is True
        assert nlri.labels != Labels.NOLABEL

        # Verify _packed contains label bytes
        # Label 800001 = 0xC35011 (bottom-of-stack bit set)
        assert b'\xc3\x50\x11' in nlri._packed

    def test_from_settings_without_labels(self) -> None:
        """Label created via from_settings() without labels should have _has_labels=False."""
        settings = INETSettings()
        settings.cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        settings.afi = AFI.ipv4
        settings.safi = SAFI.nlri_mpls
        settings.action = Action.ANNOUNCE
        settings.nexthop = IP.from_string('198.51.100.1')
        settings.labels = None  # No labels

        nlri = Label.from_settings(settings)

        # Verify the Label has no labels
        assert isinstance(nlri, Label)
        assert nlri._has_labels is False
        assert nlri.labels == Labels.NOLABEL


class TestIPVPNFromSettings:
    """Test IPVPN.from_settings() correctly includes labels and RD."""

    def test_from_settings_includes_labels_and_rd(self) -> None:
        """IPVPN created via from_settings() should include both labels and RD."""
        settings = INETSettings()
        settings.cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        settings.afi = AFI.ipv4
        settings.safi = SAFI.mpls_vpn
        settings.action = Action.ANNOUNCE
        settings.nexthop = IP.from_string('198.51.100.1')
        settings.labels = Labels.make_labels([800001])
        settings.rd = RouteDistinguisher.make_from_elements('65000', 1)

        nlri = IPVPN.from_settings(settings)

        # Verify the IPVPN has labels and RD
        assert isinstance(nlri, IPVPN)
        assert nlri._has_labels is True
        assert nlri._has_rd is True
        assert nlri.labels != Labels.NOLABEL


class TestLabelHasLabelsAttribute:
    """Test _has_labels attribute exists and is correctly set."""

    def test_label_has_has_labels_attribute(self) -> None:
        """Label class should have _has_labels attribute (not _labels_packed)."""
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        nlri = Label.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.nlri_mpls,
            Action.ANNOUNCE,
            labels=Labels.make_labels([800001]),
        )

        # _has_labels should exist
        assert hasattr(nlri, '_has_labels')

        # _labels_packed should NOT exist (old attribute from before packed-bytes-first)
        assert not hasattr(nlri, '_labels_packed')

    def test_ipvpn_inherits_has_labels(self) -> None:
        """IPVPN should inherit _has_labels from Label."""
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        rd = RouteDistinguisher.make_from_elements('65000', 1)
        nlri = IPVPN.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.mpls_vpn,
            Action.ANNOUNCE,
            labels=Labels.make_labels([800001]),
            rd=rd,
        )

        # _has_labels should exist (inherited from Label)
        assert hasattr(nlri, '_has_labels')
        assert nlri._has_labels is True


class TestLabelPreservationThroughNormalization:
    """Integration tests for label preservation through the full normalization pipeline."""

    def test_label_roundtrip_through_normalization(self) -> None:
        """Labels should be preserved when NLRI goes through normalization."""
        # Create Label with specific label value
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        original_labels = Labels.make_labels([800001])
        nlri = Label.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.nlri_mpls,
            Action.ANNOUNCE,
            labels=original_labels,
        )

        # Record original label bytes
        original_packed = nlri._packed

        # Apply normalization
        result = ParseStaticRoute._normalize_nlri_type(nlri)

        # Labels should be preserved
        assert result.labels == original_labels
        assert result._packed == original_packed

    def test_ipvpn_labels_preserved_through_normalization(self) -> None:
        """Labels should be preserved in IPVPN through normalization."""
        cidr = CIDR.make_cidr(bytes([198, 51, 100, 100]), 32)
        original_labels = Labels.make_labels([800001])
        rd = RouteDistinguisher.make_from_elements('65000', 1)

        nlri = IPVPN.from_cidr(
            cidr,
            AFI.ipv4,
            SAFI.mpls_vpn,
            Action.ANNOUNCE,
            labels=original_labels,
            rd=rd,
        )

        # Apply normalization
        result = ParseStaticRoute._normalize_nlri_type(nlri)

        # Should still be IPVPN with same labels
        assert isinstance(result, IPVPN)
        assert result.labels == original_labels


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
