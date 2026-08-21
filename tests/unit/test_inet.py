#!/usr/bin/env python3
# encoding: utf-8
"""Comprehensive tests for INET NLRI (IPv4/IPv6 Unicast and Multicast)

Created for comprehensive test coverage improvement
"""

import pytest
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.notification import Notify
from exabgp.protocol.ip import IP


class TestINETFeedback:
    """Test feedback validation for INET routes"""

    def test_feedback_announce_without_nexthop(self) -> None:
        """Test feedback when nexthop is missing for ANNOUNCE"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        nlri.cidr = CIDR(IP.pton('192.168.1.0'), 24)
        nlri.nexthop = None

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert 'inet nlri next-hop missing' in feedback

    def test_feedback_announce_with_nexthop(self) -> None:
        """Test feedback when nexthop is set for ANNOUNCE"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        nlri.cidr = CIDR(IP.pton('192.168.1.0'), 24)
        nlri.nexthop = IP.create('10.0.0.1')

        feedback = nlri.feedback(Action.ANNOUNCE)
        assert feedback == ''

    def test_feedback_withdraw_no_nexthop_required(self) -> None:
        """Test feedback for WITHDRAW doesn't require nexthop"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.WITHDRAW)
        nlri.cidr = CIDR(IP.pton('192.168.1.0'), 24)
        nlri.nexthop = None

        feedback = nlri.feedback(Action.WITHDRAW)
        assert feedback == ''


class TestINETIndex:
    """Test index generation for INET routes"""

    def test_index_with_pathinfo(self) -> None:
        """Test index generation with path info"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        nlri.cidr = CIDR(IP.pton('192.168.1.0'), 24)
        nlri.path_info = PathInfo(b'\x00\x00\x00\x01')

        index = nlri.index()

        assert isinstance(index, bytes)
        assert len(index) > 0

    def test_index_without_pathinfo(self) -> None:
        """Test index generation without path info"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        nlri.cidr = CIDR(IP.pton('192.168.1.0'), 24)
        nlri.path_info = PathInfo.NOPATH

        index = nlri.index()

        assert isinstance(index, bytes)
        assert b'no-pi' in index


class TestINETJSON:
    """Test JSON serialization for INET routes"""

    def test_json_compact_mode(self) -> None:
        """Test JSON in compact mode"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        nlri.cidr = CIDR(IP.pton('192.168.1.0'), 24)

        json_str = nlri.json(announced=True, compact=True)

        assert isinstance(json_str, str)
        assert '192.168.1.0' in json_str or '192.168.1.0/24' in json_str

    def test_json_non_compact_mode(self) -> None:
        """Test JSON in non-compact mode"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        nlri.cidr = CIDR(IP.pton('192.168.1.0'), 24)

        json_str = nlri.json(announced=True, compact=False)

        assert isinstance(json_str, str)
        assert '{' in json_str
        assert '}' in json_str


class TestINETUnpackErrors:
    """Test error handling in INET unpacking"""

    def test_unpack_insufficient_data_for_pathinfo(self) -> None:
        """Test unpacking with insufficient data for path info"""
        # Try to unpack with addpath but insufficient data (less than 4 bytes)
        # wire data comes from the peer, so a truncated path-id is a Notify, not a ValueError
        with pytest.raises(Notify) as exc_info:
            INET.unpack_nlri(AFI.ipv4, SAFI.unicast, b'\x18\xc0\xa8', Action.UNSET, addpath=True)

        assert 'path-information' in str(exc_info.value)

    def test_unpack_with_labels_insufficient_data(self) -> None:
        """Test unpacking with labels but insufficient data"""
        # When parsing labels for SAFI that has labels, we need enough data
        # This tests various error paths in label parsing
        invalid_data = b'\x20\x00\x00\x01'  # mask=32, minimal label data

        # This may raise Notify for various reasons depending on data
        try:
            INET.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, invalid_data, Action.UNSET, addpath=False)
        except (Notify, ValueError, IndexError):
            # Expected to raise some kind of error
            pass

    def test_unpack_no_data_for_mask(self) -> None:
        """Test unpacking with no data but non-zero mask"""
        # mask != 0 but no data remaining
        # This tests line 138: if not bgp and mask
        invalid_data = b'\x18'  # mask=24 but no following data

        with pytest.raises(Notify) as exc_info:
            INET.unpack_nlri(AFI.ipv4, SAFI.unicast, invalid_data, Action.UNSET, addpath=False)

        assert 'not enough data' in str(exc_info.value)

    def test_unpack_insufficient_network_data(self) -> None:
        """Test unpacking with insufficient network address data"""
        # mask requires more bytes than available
        # This tests line 143: if len(bgp) < size
        invalid_data = b'\x18\xc0\xa8'  # mask=24 requires 3 bytes, but only 2 provided

        with pytest.raises(Notify) as exc_info:
            INET.unpack_nlri(AFI.ipv4, SAFI.unicast, invalid_data, Action.UNSET, addpath=False)

        assert 'could not decode nlri' in str(exc_info.value)


class TestINETPathInfo:
    """Test _pathinfo class method"""

    def test_pathinfo_with_addpath(self) -> None:
        """Test _pathinfo extracts path info when addpath is True"""
        data = b'\x00\x00\x00\x42' + b'\x18\xc0\xa8\x01'  # path_id=66 + route data

        pathinfo, remaining = INET._pathinfo(data, addpath=True)

        assert pathinfo != PathInfo.NOPATH
        assert remaining == b'\x18\xc0\xa8\x01'

    def test_pathinfo_without_addpath(self) -> None:
        """Test _pathinfo returns NOPATH when addpath is False"""
        data = b'\x18\xc0\xa8\x01'  # route data

        pathinfo, remaining = INET._pathinfo(data, addpath=False)

        assert pathinfo == PathInfo.NOPATH
        assert remaining == data


class TestINETUnpackLabels:
    """Test unpacking INET with labels"""

    def test_unpack_with_withdraw_label(self) -> None:
        """RFC 3107 withdraw label 0x800000, which carries no bottom of stack bit

        This built the label as FOUR bytes, b'\\x00\\x80\\x00\\x00', so the decoder
        read the first three as 0x008000 and the value the test is named for
        never appeared on the wire. It then asserted only that the result was an
        INET with the action it was given, neither of which could fail, over a
        route which decoded to 0.0.0.0/0.

        A test named for a case, not exercising the case, asserting nothing that
        could tell. Found by the session working main.
        """
        withdraw_label = b'\x80\x00\x00'  # three bytes: label 0x800000
        # mask 48 = 24 bits of label plus 24 of prefix
        data = b'\x30' + withdraw_label + b'\xc0\xa8\x01'

        nlri, leftover = INET.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, data, Action.WITHDRAW, addpath=False)

        assert isinstance(nlri, INET)
        assert nlri.action == Action.WITHDRAW
        # the assertions which say the stack was read as one label and the prefix
        # survived it, rather than being eaten as more labels
        assert str(nlri.cidr) == '192.168.1.0/24'
        assert nlri.labels.labels == [0x800000 >> 4]
        assert leftover == b''

    def test_a_withdraw_label_does_not_terminate_a_stack_below_the_top(self) -> None:
        """The sentinel describes the whole stack, not a label inside one

        Accepting it at any depth is what let an unterminated first label read
        the route distinguisher and find a false terminator in its zero bytes.
        """
        from exabgp.bgp.message.notification import Notify

        # first label has no bottom of stack bit, second is the withdraw value.
        # The prefix ends in an EVEN byte on purpose: the gate can only catch a
        # stack which never terminates, and prefix bytes whose low bit happens to
        # be set still read as a bottom of stack label. That residual ambiguity is
        # in the encoding, not in this check, and it is why the first label having
        # no terminator is the thing worth refusing.
        data = b'\x48' + b'\x00\x00\x10' + b'\x80\x00\x00' + b'\xc0\xa8\x02'
        with pytest.raises(Notify):
            INET.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, data, Action.WITHDRAW, addpath=False)

    def test_unpack_with_null_label(self) -> None:
        """Test unpacking route with null label (0x000000)"""
        # Label 0x000000 is special (next-hop)
        null_label = b'\x00\x00\x00\x00'
        data = b'\x38' + null_label + b'\xc0\xa8\x01'

        nlri, leftover = INET.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, data, Action.ANNOUNCE, addpath=False)

        assert isinstance(nlri, INET)

    def test_unpack_with_bottom_of_stack_label(self) -> None:
        """Test unpacking label with bottom-of-stack bit set"""
        # Bottom of stack bit is the LSB of the label (bit 0)
        # Label with BOS: last byte has bit 0 set
        # Format: mask + 3-byte label + IP address
        # Label value 100 = 0x64, shifted left by 4 = 0x640, with BOS (bit 0) = 0x641
        bos_label = b'\x00\x06\x41'  # Label 100 with BOS bit
        # Mask = 24 (label) + 24 (for /24 prefix) = 48
        data = b'\x30' + bos_label + b'\xc0\xa8\x01\x00'

        nlri, leftover = INET.unpack_nlri(AFI.ipv4, SAFI.nlri_mpls, data, Action.ANNOUNCE, addpath=False)

        assert isinstance(nlri, INET)
        assert hasattr(nlri, 'labels')


class TestINETUnpackMulticast:
    """Test unpacking INET multicast routes"""

    def test_unpack_ipv4_multicast(self) -> None:
        """Test unpacking IPv4 multicast route"""
        # Simple IPv4 multicast prefix
        data = b'\x18\xc0\xa8\x01'  # 192.168.1.0/24

        nlri, leftover = INET.unpack_nlri(AFI.ipv4, SAFI.multicast, data, Action.ANNOUNCE, addpath=False)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.multicast
        assert nlri.cidr.prefix() == '192.168.1.0/24'

    def test_unpack_ipv6_multicast(self) -> None:
        """Test unpacking IPv6 multicast route"""
        # IPv6 prefix ff00::/8
        data = b'\x08\xff'

        nlri, leftover = INET.unpack_nlri(AFI.ipv6, SAFI.multicast, data, Action.ANNOUNCE, addpath=False)

        assert nlri.afi == AFI.ipv6
        assert nlri.safi == SAFI.multicast


class TestINETCreationVariants:
    """Test creating INET with different AFI/SAFI combinations"""

    def test_create_ipv4_unicast(self) -> None:
        """Test creating IPv4 unicast INET"""
        nlri = INET(AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.unicast

    def test_create_ipv6_unicast(self) -> None:
        """Test creating IPv6 unicast INET"""
        nlri = INET(AFI.ipv6, SAFI.unicast, Action.ANNOUNCE)

        assert nlri.afi == AFI.ipv6
        assert nlri.safi == SAFI.unicast

    def test_create_ipv4_multicast(self) -> None:
        """Test creating IPv4 multicast INET"""
        nlri = INET(AFI.ipv4, SAFI.multicast, Action.ANNOUNCE)

        assert nlri.afi == AFI.ipv4
        assert nlri.safi == SAFI.multicast

    def test_create_ipv6_multicast(self) -> None:
        """Test creating IPv6 multicast INET"""
        nlri = INET(AFI.ipv6, SAFI.multicast, Action.ANNOUNCE)

        assert nlri.afi == AFI.ipv6
        assert nlri.safi == SAFI.multicast


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
