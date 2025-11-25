"""test_suggestions.py

Tests for the Levenshtein distance and suggestion functions in section.py.

Created by Claude Code on 2025-11-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.configuration.core.section import _levenshtein, _find_similar


class TestLevenshtein:
    """Tests for Levenshtein distance calculation."""

    def test_identical_strings(self):
        """Identical strings have distance 0."""
        assert _levenshtein('hello', 'hello') == 0
        assert _levenshtein('', '') == 0
        assert _levenshtein('a', 'a') == 0

    def test_empty_string(self):
        """Distance to empty string is length of other string."""
        assert _levenshtein('hello', '') == 5
        assert _levenshtein('', 'world') == 5
        assert _levenshtein('abc', '') == 3

    def test_single_insertion(self):
        """Single character insertion has distance 1."""
        assert _levenshtein('hell', 'hello') == 1
        assert _levenshtein('cat', 'cats') == 1

    def test_single_deletion(self):
        """Single character deletion has distance 1."""
        assert _levenshtein('hello', 'hell') == 1
        assert _levenshtein('cats', 'cat') == 1

    def test_single_substitution(self):
        """Single character substitution has distance 1."""
        assert _levenshtein('cat', 'bat') == 1
        assert _levenshtein('hello', 'hallo') == 1

    def test_multiple_edits(self):
        """Multiple edits are counted correctly."""
        assert _levenshtein('kitten', 'sitting') == 3
        assert _levenshtein('saturday', 'sunday') == 3

    def test_case_sensitive(self):
        """Levenshtein is case-sensitive."""
        assert _levenshtein('Hello', 'hello') == 1
        assert _levenshtein('ABC', 'abc') == 3

    def test_common_typos(self):
        """Common configuration typos."""
        # Missing letter
        assert _levenshtein('neighbor', 'neighbr') == 1
        # Swapped letters
        assert _levenshtein('router-id', 'rotuer-id') == 2
        # Extra letter
        assert _levenshtein('peer-as', 'peer-aas') == 1
        # Wrong letter
        assert _levenshtein('local-as', 'local-az') == 1


class TestFindSimilar:
    """Tests for finding similar strings."""

    def test_empty_target(self):
        """Empty target returns empty list."""
        assert _find_similar('', ['hello', 'world']) == []

    def test_empty_candidates(self):
        """Empty candidates returns empty list."""
        assert _find_similar('hello', []) == []

    def test_exact_match(self):
        """Exact match is returned first (distance 0)."""
        candidates = ['hello', 'help', 'world']
        result = _find_similar('hello', candidates)
        assert 'hello' in result
        assert result[0] == 'hello'

    def test_close_matches(self):
        """Close matches within max_distance are returned."""
        candidates = ['neighbor', 'next-hop', 'local-as', 'peer-as']
        result = _find_similar('neighbr', candidates, max_distance=2)
        assert 'neighbor' in result

    def test_no_matches_beyond_distance(self):
        """Strings beyond max_distance are not returned."""
        candidates = ['completely', 'different', 'words']
        result = _find_similar('hello', candidates, max_distance=2)
        assert result == []

    def test_max_results_limit(self):
        """Results are limited to max_results."""
        candidates = ['aa', 'ab', 'ac', 'ad', 'ae']
        result = _find_similar('a', candidates, max_distance=2, max_results=3)
        assert len(result) <= 3

    def test_sorted_by_distance(self):
        """Results are sorted by distance (closest first)."""
        candidates = ['hello', 'helo', 'hallo', 'hxllo']
        result = _find_similar('hello', candidates, max_distance=2)
        # 'hello' (0), 'helo' (1), 'hallo' (1), 'hxllo' (1)
        assert result[0] == 'hello'

    def test_case_insensitive(self):
        """Search is case-insensitive."""
        candidates = ['NEIGHBOR', 'LOCAL-AS', 'PEER-AS']
        result = _find_similar('neighbor', candidates, max_distance=0)
        assert 'NEIGHBOR' in result

    def test_configuration_typos(self):
        """Tests for common ExaBGP configuration typos."""
        neighbor_commands = [
            'router-id',
            'local-address',
            'peer-address',
            'local-as',
            'peer-as',
            'hold-time',
            'passive',
            'description',
        ]

        # Typo: peer-adress (missing 'd')
        result = _find_similar('peer-adress', neighbor_commands, max_distance=2)
        assert 'peer-address' in result

        # Typo: rotuer-id (swapped letters)
        result = _find_similar('rotuer-id', neighbor_commands, max_distance=2)
        assert 'router-id' in result

        # Typo: holdtime (missing hyphen)
        result = _find_similar('holdtime', neighbor_commands, max_distance=2)
        assert 'hold-time' in result

        # Typo: descripion (missing 't')
        result = _find_similar('descripion', neighbor_commands, max_distance=2)
        assert 'description' in result

    def test_capability_typos(self):
        """Tests for common capability typos."""
        capability_commands = [
            'add-path',
            'asn4',
            'graceful-restart',
            'multi-session',
            'operational',
            'route-refresh',
            'extended-message',
        ]

        # Typo: addpath (missing hyphen)
        result = _find_similar('addpath', capability_commands, max_distance=2)
        assert 'add-path' in result

        # Typo: graceful-retart (missing 's')
        result = _find_similar('graceful-retart', capability_commands, max_distance=2)
        assert 'graceful-restart' in result
