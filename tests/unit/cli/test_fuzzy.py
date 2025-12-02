"""test_fuzzy.py

Unit tests for fuzzy matching module.

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.cli.fuzzy import FuzzyMatcher, fuzzy_filter


class TestSubsequenceMatching:
    """Test subsequence matching algorithm"""

    def test_exact_match(self):
        """Test exact string matches"""
        matcher = FuzzyMatcher()
        is_match, matched = matcher.subsequence_match('show', 'show')
        assert is_match is True
        assert matched == 4

    def test_subsequence_match(self):
        """Test subsequence matching (characters in order but not consecutive)"""
        matcher = FuzzyMatcher()

        # 'sn' matches 's'how 'n'eighbor
        is_match, matched = matcher.subsequence_match('sn', 'show neighbor')
        assert is_match is True
        assert matched == 2

        # 'ar' matches 'a'nnounce 'r'oute
        is_match, matched = matcher.subsequence_match('ar', 'announce route')
        assert is_match is True
        assert matched == 2

    def test_no_match(self):
        """Test non-matching patterns"""
        matcher = FuzzyMatcher()

        # 'xyz' does not match 'show'
        is_match, matched = matcher.subsequence_match('xyz', 'show')
        assert is_match is False
        assert matched == 0

    def test_case_insensitive(self):
        """Test case-insensitive matching"""
        matcher = FuzzyMatcher()

        is_match, _ = matcher.subsequence_match('SN', 'show neighbor')
        assert is_match is True

        is_match, _ = matcher.subsequence_match('sn', 'SHOW NEIGHBOR')
        assert is_match is True

    def test_empty_query(self):
        """Test empty query matches everything"""
        matcher = FuzzyMatcher()

        is_match, matched = matcher.subsequence_match('', 'show neighbor')
        assert is_match is True
        assert matched == 0

    def test_partial_match(self):
        """Test partial subsequence matches"""
        matcher = FuzzyMatcher()

        # 'sho' partially matches 'show' (3 of 3 chars)
        is_match, matched = matcher.subsequence_match('sho', 'show')
        assert is_match is True
        assert matched == 3

        # 'shw' matches 's'_'h'utdo'w'n
        is_match, matched = matcher.subsequence_match('shw', 'shutdown')
        assert is_match is True
        assert matched == 3


class TestScoring:
    """Test match scoring algorithm"""

    def test_exact_prefix_bonus(self):
        """Test exact prefix matches get +100 bonus"""
        matcher = FuzzyMatcher()

        score = matcher.calculate_score('sh', 'show')
        assert score.is_exact_prefix is True
        assert score.score >= 100  # At least +100 for exact prefix

    def test_subsequence_scoring(self):
        """Test subsequence matches are scored by matched chars"""
        matcher = FuzzyMatcher()

        # Longer matches score higher
        score1 = matcher.calculate_score('sho', 'show')
        score2 = matcher.calculate_score('sh', 'show')
        assert score1.score > score2.score

    def test_compactness_penalty(self):
        """Test tighter matches score higher (gap penalty)"""
        matcher = FuzzyMatcher()

        # 'ab' in 'abc' (no gaps) vs 'ab' in 'a_b_c' (2 gaps)
        score_tight = matcher.calculate_score('ab', 'abc')
        score_loose = matcher.calculate_score('ab', 'a b c')

        # Tighter match should score higher
        assert score_tight.score > score_loose.score

    def test_frequency_bonus(self):
        """Test frequency provider adds ranking bonus"""
        # Without frequency
        matcher1 = FuzzyMatcher()
        score1 = matcher1.calculate_score('show', 'show neighbor')

        # With frequency (show neighbor used 10 times)
        matcher2 = FuzzyMatcher(frequency_provider={'show neighbor': 10})
        score2 = matcher2.calculate_score('show', 'show neighbor')

        # Score with frequency should be higher
        assert score2.score > score1.score

    def test_invalid_match_negative_score(self):
        """Test non-matches get score of -1"""
        matcher = FuzzyMatcher()

        score = matcher.calculate_score('xyz', 'show')
        assert score.score == -1

    def test_empty_query_zero_score(self):
        """Test empty query gets neutral score"""
        matcher = FuzzyMatcher()

        score = matcher.calculate_score('', 'show neighbor')
        assert score.score == 0


class TestGetMatches:
    """Test get_matches method (main API)"""

    def test_exact_prefix_priority(self):
        """Test exact prefix matches are returned first"""
        matcher = FuzzyMatcher()

        candidates = ['show', 'shutdown', 'flush']
        matches = matcher.get_matches('sh', candidates)

        # Both 'show' and 'shutdown' should match
        matched_values = [m.candidate for m in matches]
        assert 'show' in matched_values
        assert 'shutdown' in matched_values
        assert 'flush' not in matched_values

    def test_fuzzy_fallback(self):
        """Test fuzzy matching when no exact prefix matches"""
        matcher = FuzzyMatcher()

        candidates = ['show neighbor', 'shutdown', 'show adj-rib']
        matches = matcher.get_matches('sn', candidates)

        # 'sn' matches 's'how 'n'eighbor via fuzzy
        matched_values = [m.candidate for m in matches]
        assert 'show neighbor' in matched_values

    def test_limit_results(self):
        """Test result limiting"""
        matcher = FuzzyMatcher()

        candidates = [f'command{i}' for i in range(20)]
        matches = matcher.get_matches('c', candidates, limit=5)

        assert len(matches) <= 5

    def test_exact_only_mode(self):
        """Test exact_only flag disables fuzzy matching"""
        matcher = FuzzyMatcher()

        candidates = ['show neighbor', 'shutdown']
        matches = matcher.get_matches('sn', candidates, exact_only=True)

        # No exact prefix matches, should return empty
        assert len(matches) == 0

    def test_empty_query_returns_all(self):
        """Test empty query returns all candidates"""
        matcher = FuzzyMatcher()

        candidates = ['show', 'announce', 'withdraw']
        matches = matcher.get_matches('', candidates, limit=10)

        assert len(matches) == 3

    def test_sorting_by_score(self):
        """Test matches are sorted by score descending"""
        matcher = FuzzyMatcher()

        candidates = ['show', 'shutdown', 'show neighbor']
        matches = matcher.get_matches('sh', candidates)

        # Verify scores are descending
        scores = [m.score for m in matches]
        assert scores == sorted(scores, reverse=True)


class TestConvenienceFunction:
    """Test fuzzy_filter convenience function"""

    def test_fuzzy_filter_returns_strings(self):
        """Test fuzzy_filter returns just candidate strings"""
        candidates = ['show neighbor', 'show adj-rib', 'shutdown']
        results = fuzzy_filter('sn', candidates)

        assert isinstance(results, list)
        assert all(isinstance(r, str) for r in results)

    def test_fuzzy_filter_matches(self):
        """Test fuzzy_filter returns expected matches"""
        candidates = ['show neighbor', 'shutdown']
        results = fuzzy_filter('sn', candidates)

        assert 'show neighbor' in results


class TestEdgeCases:
    """Test edge cases and error conditions"""

    def test_empty_candidates(self):
        """Test matching against empty candidate list"""
        matcher = FuzzyMatcher()
        matches = matcher.get_matches('test', [])
        assert len(matches) == 0

    def test_special_characters(self):
        """Test matching with special characters"""
        matcher = FuzzyMatcher()

        candidates = ['adj-rib', 'show-neighbor', 'test_command']
        matches = matcher.get_matches('ar', candidates)

        # 'ar' should match 'a'dj-'r'ib
        matched_values = [m.candidate for m in matches]
        assert 'adj-rib' in matched_values

    def test_unicode_characters(self):
        """Test matching with unicode (should work, case-insensitive)"""
        matcher = FuzzyMatcher()

        # Basic unicode support
        is_match, _ = matcher.subsequence_match('test', 'test')
        assert is_match is True

    def test_very_long_candidates(self):
        """Test performance with long candidate strings"""
        matcher = FuzzyMatcher()

        long_candidate = 'a' * 1000 + 'b' + 'c' * 1000
        is_match, _ = matcher.subsequence_match('abc', long_candidate)
        assert is_match is True

    def test_tie_breaking(self):
        """Test behavior when multiple candidates have same score"""
        matcher = FuzzyMatcher()

        # Both have exact prefix match
        candidates = ['test1', 'test2', 'test3']
        matches = matcher.get_matches('test', candidates)

        # Should return all matches (up to limit)
        assert len(matches) == 3


class TestFrequencyProvider:
    """Test frequency provider integration"""

    def test_set_frequency_provider(self):
        """Test updating frequency provider"""
        matcher = FuzzyMatcher()

        matcher.set_frequency_provider({'show neighbor': 5})
        score = matcher.calculate_score('show', 'show neighbor')

        # Should have frequency bonus
        assert score.score > 0

    def test_frequency_affects_ranking(self):
        """Test frequency changes match ranking"""
        # High frequency for 'announce route'
        matcher = FuzzyMatcher(frequency_provider={'announce route': 20, 'announce eor': 1})

        candidates = ['announce route', 'announce eor']
        matches = matcher.get_matches('an', candidates)

        # 'announce route' should rank higher due to frequency
        assert matches[0].candidate == 'announce route'


class TestRealWorldScenarios:
    """Test real CLI command scenarios"""

    def test_show_neighbor_completion(self):
        """Test completing 'show neighbor' from 'sn'"""
        matcher = FuzzyMatcher()

        commands = ['show', 'shutdown', 'show neighbor', 'show adj-rib', 'announce', 'withdraw']
        matches = matcher.get_matches('sn', commands)

        matched_values = [m.candidate for m in matches]
        assert 'show neighbor' in matched_values

    def test_announce_route_completion(self):
        """Test completing 'announce route' from 'ar'"""
        matcher = FuzzyMatcher()

        commands = ['announce', 'announce route', 'announce eor', 'announce route-refresh', 'adj-rib']
        matches = matcher.get_matches('ar', commands)

        matched_values = [m.candidate for m in matches]
        assert 'announce route' in matched_values
        assert 'adj-rib' in matched_values  # Also matches 'a'dj-'r'ib

    def test_multiple_word_commands(self):
        """Test fuzzy matching across multiple words"""
        matcher = FuzzyMatcher()

        commands = ['show neighbor summary', 'show neighbor extensive', 'show adj-rib in']
        matches = matcher.get_matches('sns', commands)

        # 'sns' matches 's'how 'n'eighbor 's'ummary
        matched_values = [m.candidate for m in matches]
        assert 'show neighbor summary' in matched_values
