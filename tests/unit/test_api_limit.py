"""Tests for exabgp.reactor.api.command.limit module.

Tests the neighbor selector parsing functions, including v6 bracket syntax.
"""

from __future__ import annotations

from exabgp.reactor.api.command.limit import extract_neighbors, match_neighbor, match_neighbors


class TestExtractNeighbors:
    """Tests for extract_neighbors() function."""

    # === v6 Bracket Syntax ===

    def test_bracket_single_ip(self) -> None:
        """Test bracket syntax with single IP selector."""
        cmd = 'peer [10.0.0.1] announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_bracket_multiple_ips(self) -> None:
        """Test bracket syntax with multiple IP selectors."""
        cmd = 'peer [10.0.0.1, 10.0.0.2] announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1'], ['neighbor 10.0.0.2']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_bracket_ip_with_selector_keys(self) -> None:
        """Test bracket syntax with IP and selector key-value pairs."""
        cmd = 'peer [10.0.0.1 router-id 1.2.3.4, 10.0.0.2] announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1', 'router-id 1.2.3.4'], ['neighbor 10.0.0.2']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_bracket_multiple_selector_keys(self) -> None:
        """Test bracket syntax with multiple selector keys per entry."""
        cmd = 'peer [10.0.0.1 router-id 1.2.3.4 peer-as 65000] announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1', 'router-id 1.2.3.4', 'peer-as 65000']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_bracket_with_wildcard(self) -> None:
        """Test bracket syntax with wildcard selector."""
        cmd = 'peer [10.0.0.1 local-as 65000, *] announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1', 'local-as 65000'], ['neighbor *']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_bracket_preserves_full_command(self) -> None:
        """Test that remaining command includes all arguments."""
        cmd = 'peer [10.0.0.1] announce route 1.0.0.0/8 next-hop 1.1.1.1 as-path [65000 65001]'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1']]
        assert remaining == 'announce route 1.0.0.0/8 next-hop 1.1.1.1 as-path [65000 65001]'

    # === Legacy (non-bracket) syntax ===

    def test_legacy_single_peer(self) -> None:
        """Test legacy single peer format."""
        cmd = 'peer 10.0.0.1 announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_legacy_neighbor_keyword(self) -> None:
        """Test legacy neighbor keyword (v4 format)."""
        cmd = 'neighbor 10.0.0.1 announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_legacy_with_selector_keys(self) -> None:
        """Test legacy format with selector keys."""
        cmd = 'peer 10.0.0.1 router-id 1.2.3.4 announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor 10.0.0.1', 'router-id 1.2.3.4']]
        assert remaining == 'announce route 1.0.0.0/8'

    def test_legacy_wildcard(self) -> None:
        """Test legacy wildcard format."""
        cmd = 'peer * announce route 1.0.0.0/8'
        defs, remaining = extract_neighbors(cmd)
        assert defs == [['neighbor *']]
        assert remaining == 'announce route 1.0.0.0/8'

    # === Non-peer commands ===

    def test_non_peer_command(self) -> None:
        """Test that non-peer commands return empty definitions."""
        cmd = 'daemon shutdown'
        defs, remaining = extract_neighbors(cmd)
        assert defs == []
        assert remaining == 'daemon shutdown'

    def test_single_word_command(self) -> None:
        """Test single-word commands."""
        cmd = 'shutdown'
        defs, remaining = extract_neighbors(cmd)
        assert defs == []
        assert remaining == 'shutdown'


class TestMatchNeighbor:
    """Tests for match_neighbor() function."""

    def test_match_exact_ip(self) -> None:
        """Test exact IP match."""
        description = ['neighbor 10.0.0.1']
        name = 'neighbor 10.0.0.1 peer-as 65000 router-id 1.2.3.4'
        assert match_neighbor(description, name) is True

    def test_match_with_router_id(self) -> None:
        """Test match with router-id selector."""
        description = ['neighbor 10.0.0.1', 'router-id 1.2.3.4']
        name = 'neighbor 10.0.0.1 peer-as 65000 router-id 1.2.3.4'
        assert match_neighbor(description, name) is True

    def test_no_match_wrong_router_id(self) -> None:
        """Test no match when router-id doesn't match."""
        description = ['neighbor 10.0.0.1', 'router-id 9.9.9.9']
        name = 'neighbor 10.0.0.1 peer-as 65000 router-id 1.2.3.4'
        assert match_neighbor(description, name) is False

    def test_wildcard_matches_all(self) -> None:
        """Test wildcard matches any peer."""
        description = ['neighbor *']
        name = 'neighbor 10.0.0.1 peer-as 65000'
        assert match_neighbor(description, name) is True

    def test_peer_wildcard_matches_all(self) -> None:
        """Test 'peer *' wildcard also matches."""
        description = ['peer *']
        name = 'neighbor 10.0.0.1 peer-as 65000'
        assert match_neighbor(description, name) is True


class TestMatchNeighbors:
    """Tests for match_neighbors() function."""

    def test_empty_descriptions_returns_all(self) -> None:
        """Test that empty descriptions return all peers."""
        peers = ['peer1', 'peer2', 'peer3']
        result = match_neighbors(peers, [])
        assert result == ['peer1', 'peer2', 'peer3']

    def test_match_single_description(self) -> None:
        """Test matching single description."""
        peers = [
            'neighbor 10.0.0.1 peer-as 65000',
            'neighbor 10.0.0.2 peer-as 65001',
        ]
        descriptions = [['neighbor 10.0.0.1']]
        result = match_neighbors(peers, descriptions)
        assert result == ['neighbor 10.0.0.1 peer-as 65000']

    def test_match_multiple_descriptions(self) -> None:
        """Test matching multiple descriptions (OR logic)."""
        peers = [
            'neighbor 10.0.0.1 peer-as 65000',
            'neighbor 10.0.0.2 peer-as 65001',
            'neighbor 10.0.0.3 peer-as 65002',
        ]
        descriptions = [['neighbor 10.0.0.1'], ['neighbor 10.0.0.2']]
        result = match_neighbors(peers, descriptions)
        assert 'neighbor 10.0.0.1 peer-as 65000' in result
        assert 'neighbor 10.0.0.2 peer-as 65001' in result
        assert len(result) == 2

    def test_no_duplicates_in_result(self) -> None:
        """Test that matching peers aren't duplicated."""
        peers = ['neighbor 10.0.0.1 peer-as 65000 router-id 1.2.3.4']
        # Both descriptions match the same peer
        descriptions = [['neighbor 10.0.0.1'], ['router-id 1.2.3.4']]
        result = match_neighbors(peers, descriptions)
        assert len(result) == 1
