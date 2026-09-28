"""test_suggestions.py

Tests for the Levenshtein distance and suggestion functions of the configuration grammar
(grammar/error.py: distance and suggest, once _levenshtein and _find_similar of section.py).

suggest() has the fixed limits MAX_SUGGESTION_DISTANCE (2) and MAX_SUGGESTIONS (3).

Created by Claude Code on 2025-11-25.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import pytest

from exabgp.configuration.configuration import Configuration
from exabgp.configuration.grammar.error import MAX_SUGGESTION_DISTANCE, MAX_SUGGESTIONS, distance, suggest


class TestLevenshtein:
    """Tests for Levenshtein distance calculation."""

    def test_identical_strings(self):
        """Identical strings have distance 0."""
        assert distance('hello', 'hello') == 0
        assert distance('', '') == 0
        assert distance('a', 'a') == 0

    def test_empty_string(self):
        """Distance to empty string is length of other string."""
        assert distance('hello', '') == 5
        assert distance('', 'world') == 5
        assert distance('abc', '') == 3

    def test_single_insertion(self):
        """Single character insertion has distance 1."""
        assert distance('hell', 'hello') == 1
        assert distance('cat', 'cats') == 1

    def test_single_deletion(self):
        """Single character deletion has distance 1."""
        assert distance('hello', 'hell') == 1
        assert distance('cats', 'cat') == 1

    def test_single_substitution(self):
        """Single character substitution has distance 1."""
        assert distance('cat', 'bat') == 1
        assert distance('hello', 'hallo') == 1

    def test_multiple_edits(self):
        """Multiple edits are counted correctly."""
        assert distance('kitten', 'sitting') == 3
        assert distance('saturday', 'sunday') == 3

    def test_case_sensitive(self):
        """Levenshtein is case-sensitive."""
        assert distance('Hello', 'hello') == 1
        assert distance('ABC', 'abc') == 3

    def test_common_typos(self):
        """Common configuration typos."""
        # Missing letter
        assert distance('neighbor', 'neighbr') == 1
        # Swapped letters
        assert distance('router-id', 'rotuer-id') == 2
        # Extra letter
        assert distance('peer-as', 'peer-aas') == 1
        # Wrong letter
        assert distance('local-as', 'local-az') == 1


class TestFindSimilar:
    """Tests for finding similar strings."""

    def test_empty_target(self):
        """Empty target returns empty list."""
        assert suggest('', ['hello', 'world']) == []

    def test_empty_candidates(self):
        """Empty candidates returns empty list."""
        assert suggest('hello', []) == []

    def test_exact_match(self):
        """Exact match is returned first (distance 0)."""
        candidates = ['hello', 'help', 'world']
        result = suggest('hello', candidates)
        assert 'hello' in result
        assert result[0] == 'hello'

    def test_close_matches(self):
        """Close matches within MAX_SUGGESTION_DISTANCE are returned."""
        candidates = ['neighbor', 'next-hop', 'local-as', 'peer-as']
        result = suggest('neighbr', candidates)
        assert 'neighbor' in result

    def test_no_matches_beyond_distance(self):
        """Strings beyond MAX_SUGGESTION_DISTANCE are not returned."""
        candidates = ['completely', 'different', 'words']
        result = suggest('hello', candidates)
        assert result == []

    def test_max_results_limit(self):
        """Results are limited to MAX_SUGGESTIONS."""
        candidates = ['aa', 'ab', 'ac', 'ad', 'ae']
        result = suggest('a', candidates)
        assert len(result) <= MAX_SUGGESTIONS

    def test_the_limits(self):
        """suggest() keeps the limits _find_similar was called with."""
        assert MAX_SUGGESTION_DISTANCE == 2
        assert MAX_SUGGESTIONS == 3

    def test_sorted_by_distance(self):
        """Results are sorted by distance (closest first)."""
        candidates = ['hello', 'helo', 'hallo', 'hxllo']
        result = suggest('hello', candidates)
        # 'hello' (0), 'helo' (1), 'hallo' (1), 'hxllo' (1)
        assert result[0] == 'hello'

    def test_case_insensitive(self):
        """Search is case-insensitive."""
        candidates = ['NEIGHBOR', 'LOCAL-AS', 'PEER-AS']
        result = suggest('neighbor', candidates)
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
        result = suggest('peer-adress', neighbor_commands)
        assert 'peer-address' in result

        # Typo: rotuer-id (swapped letters)
        result = suggest('rotuer-id', neighbor_commands)
        assert 'router-id' in result

        # Typo: holdtime (missing hyphen)
        result = suggest('holdtime', neighbor_commands)
        assert 'hold-time' in result

        # Typo: descripion (missing 't')
        result = suggest('descripion', neighbor_commands)
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
        result = suggest('addpath', capability_commands)
        assert 'add-path' in result

        # Typo: graceful-retart (missing 's')
        result = suggest('graceful-retart', capability_commands)
        assert 'graceful-restart' in result


NEIGHBOR = """\
neighbor 127.0.0.1 {
    router-id 1.2.3.4;
    local-address 127.0.0.1;
    local-as 65000;
    peer-as 65001;
    %s
}
"""


class TestConfigurationSuggestions:
    """A misspelt keyword in a configuration is refused, and the error offers the keyword meant."""

    @pytest.mark.parametrize(
        'statement,meant',
        [
            ('peer-adress 127.0.0.2;', 'peer-address'),
            ('rotuer-id 1.2.3.4;', 'router-id'),
            ('holdtime 180;', 'hold-time'),
            ('descripion text;', 'description'),
            ('capability { addpath send; }', 'add-path'),
            ('capability { graceful-retart 10; }', 'graceful-restart'),
        ],
    )
    def test_a_misspelt_keyword_is_suggested(self, statement: str, meant: str) -> None:
        configuration = Configuration([NEIGHBOR % statement], text=True)

        assert not configuration.reload()
        error = str(configuration.error)
        assert f'did you mean: {meant}' in error
        assert error.startswith('line ')  # the error names where the typo is

    def test_a_misspelt_section_is_suggested(self) -> None:
        configuration = Configuration(['neighbr 127.0.0.1 {\n}\n'], text=True)

        assert not configuration.reload()
        assert 'did you mean: neighbor' in str(configuration.error)
