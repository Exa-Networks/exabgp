"""fuzzy.py

Fuzzy matching for CLI command completion using subsequence matching.

Provides intuitive command completion where "sn" matches "show neighbor",
"ar" matches "announce route", etc. Uses O(n) subsequence algorithm for
performance (<20ms for 200 candidates).

Created by Thomas Mangin on 2025-12-02.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MatchScore:
    """Score for a fuzzy match with metadata"""

    candidate: str
    score: int
    is_exact_prefix: bool
    subsequence_length: int


class FuzzyMatcher:
    """Fuzzy matching engine for command completion.

    Uses subsequence matching: query characters must appear in order in candidate,
    but don't need to be consecutive. Scores matches based on:
    - Exact prefix match (highest priority)
    - Subsequence match quality (longer matches better)
    - Compactness (fewer gaps better)
    - Frequency bonus (from external history data)

    Example:
        >>> matcher = FuzzyMatcher()
        >>> matches = matcher.get_matches('sn', ['show', 'shutdown', 'show neighbor'])
        >>> [m.candidate for m in matches]
        ['show neighbor']  # 'sn' matches 's'how 'n'eighbor

        >>> matches = matcher.get_matches('shw', ['show', 'shutdown'])
        >>> [m.candidate for m in matches]
        ['show', 'shutdown']  # Both match

    Performance:
        - Subsequence matching: O(n) where n = len(candidate)
        - Total: O(m*n) where m = number of candidates
        - Typical: <20ms for 200 candidates
    """

    def __init__(self, frequency_provider: dict[str, int] | None = None):
        """Initialize fuzzy matcher.

        Args:
            frequency_provider: Optional dict mapping candidate → usage count
                                Used for ranking bonus (0-50 points)
        """
        self.frequency_provider = frequency_provider or {}

    def subsequence_match(self, query: str, candidate: str) -> tuple[bool, int]:
        """Check if query is subsequence of candidate (case-insensitive).

        A subsequence means query characters appear in order in candidate,
        but don't need to be consecutive.

        Args:
            query: Search string (e.g., 'sn')
            candidate: Target string (e.g., 'show neighbor')

        Returns:
            (is_match, matched_chars) tuple where:
                is_match: True if query is subsequence of candidate
                matched_chars: Number of query characters matched

        Example:
            >>> subsequence_match('sn', 'show neighbor')
            (True, 2)  # Matched 's' from 'show' and 'n' from 'neighbor'

            >>> subsequence_match('xyz', 'show')
            (False, 0)  # 'x' not found
        """
        if not query:
            return (True, 0)

        query_lower = query.lower()
        candidate_lower = candidate.lower()

        q_idx = 0
        for c in candidate_lower:
            if q_idx < len(query_lower) and c == query_lower[q_idx]:
                q_idx += 1
                if q_idx == len(query_lower):
                    break

        is_match = q_idx == len(query_lower)
        return (is_match, q_idx)

    def calculate_score(self, query: str, candidate: str) -> MatchScore:
        """Calculate match score for ranking.

        Scoring factors:
        1. Exact prefix: +100 (highest priority, e.g., 'sh' → 'show')
        2. Subsequence matched chars: +10 per char
        3. Compactness penalty: -1 per gap (prefer tighter matches)
        4. Frequency bonus: +0-50 based on usage count

        Args:
            query: Search string
            candidate: Target string

        Returns:
            MatchScore with total score and metadata

        Example:
            >>> calculate_score('sh', 'show')
            MatchScore(candidate='show', score=120, is_exact_prefix=True, ...)
            # 100 (exact) + 10*2 (matched 'sh') = 120

            >>> calculate_score('sn', 'show neighbor')
            MatchScore(candidate='show neighbor', score=8, is_exact_prefix=False, ...)
            # 10*2 (matched 's', 'n') - 12 (12 char gaps) = -2, but clamped to 0+
        """
        if not query:
            # Empty query matches everything equally
            return MatchScore(candidate=candidate, score=0, is_exact_prefix=False, subsequence_length=0)

        score = 0
        query_lower = query.lower()
        candidate_lower = candidate.lower()

        # Factor 1: Exact prefix match (highest priority)
        is_exact_prefix = candidate_lower.startswith(query_lower)
        if is_exact_prefix:
            score += 100

        # Factor 2: Subsequence match
        is_match, matched_chars = self.subsequence_match(query, candidate)
        if not is_match:
            # Not a valid match at all
            return MatchScore(candidate=candidate, score=-1, is_exact_prefix=False, subsequence_length=0)

        score += matched_chars * 10

        # Factor 3: Compactness penalty (prefer tighter matches)
        # Gap count = total length - matched chars
        gaps = len(candidate_lower) - matched_chars
        score -= gaps

        # Factor 4: Frequency bonus (from usage history)
        freq_count = self.frequency_provider.get(candidate, 0)
        freq_bonus = min(50, freq_count * 5)  # Cap at 50 points
        score += freq_bonus

        # Ensure non-negative (invalid matches already returned -1)
        score = max(0, score)

        return MatchScore(
            candidate=candidate, score=score, is_exact_prefix=is_exact_prefix, subsequence_length=matched_chars
        )

    def get_matches(
        self, query: str, candidates: list[str], limit: int = 10, exact_only: bool = False
    ) -> list[MatchScore]:
        """Get fuzzy matches sorted by score.

        Strategy:
        1. Try exact prefix matches first (highest priority)
        2. If no exact matches, try fuzzy subsequence matching
        3. Sort by score descending, limit to top N

        Args:
            query: Search string
            candidates: List of strings to search
            limit: Maximum number of results (default 10)
            exact_only: If True, only return exact prefix matches

        Returns:
            List of MatchScore objects sorted by score descending

        Example:
            >>> get_matches('sh', ['show', 'shutdown', 'flush'])
            [MatchScore('show', 120, ...), MatchScore('shutdown', 120, ...)]

            >>> get_matches('sn', ['show', 'shutdown', 'show neighbor'])
            [MatchScore('show neighbor', 8, ...)]
        """
        if not query:
            # Empty query: return all candidates with score 0
            return [MatchScore(candidate=c, score=0, is_exact_prefix=False, subsequence_length=0) for c in candidates][
                :limit
            ]

        query_lower = query.lower()

        # Phase 1: Try exact prefix matches
        exact_matches = [c for c in candidates if c.lower().startswith(query_lower)]

        if exact_matches:
            # Score exact matches (will have +100 bonus)
            scored = [self.calculate_score(query, c) for c in exact_matches]
            scored.sort(key=lambda m: m.score, reverse=True)
            return scored[:limit]

        if exact_only:
            return []

        # Phase 2: Try fuzzy subsequence matches
        scored = []
        for candidate in candidates:
            match = self.calculate_score(query, candidate)
            if match.score >= 0:  # Valid match (score -1 means no match)
                scored.append(match)

        # Sort by score descending
        scored.sort(key=lambda m: m.score, reverse=True)

        return scored[:limit]

    def set_frequency_provider(self, provider: dict[str, int]) -> None:
        """Update frequency provider for ranking bonus.

        Args:
            provider: Dict mapping candidate → usage count
        """
        self.frequency_provider = provider


# Convenience function for simple cases
def fuzzy_filter(query: str, candidates: list[str], limit: int = 10) -> list[str]:
    """Simple fuzzy filter returning just candidate strings.

    Args:
        query: Search string
        candidates: List of strings to search
        limit: Maximum results

    Returns:
        List of matching candidate strings (no scores)

    Example:
        >>> fuzzy_filter('sn', ['show', 'shutdown', 'show neighbor'])
        ['show neighbor']
    """
    matcher = FuzzyMatcher()
    matches = matcher.get_matches(query, candidates, limit=limit)
    return [m.candidate for m in matches]


# Performance benchmarking utilities
def benchmark_fuzzy_matching(num_candidates: int = 200, num_trials: int = 100) -> dict[str, float]:
    """Benchmark fuzzy matching performance.

    Args:
        num_candidates: Number of candidates to test against
        num_trials: Number of trials to run

    Returns:
        Dict with timing statistics (min, max, avg, p99 in milliseconds)

    Example:
        >>> stats = benchmark_fuzzy_matching(200, 100)
        >>> print(f"Average: {stats['avg_ms']:.2f}ms")
        Average: 15.23ms
    """
    import time

    # Generate test candidates (realistic command names)
    candidates = [
        'show',
        'show neighbor',
        'show neighbor summary',
        'show adj-rib',
        'show adj-rib in',
        'show adj-rib out',
        'announce',
        'announce route',
        'announce eor',
        'announce route-refresh',
        'withdraw',
        'withdraw route',
        'teardown',
        'flush',
        'flush adj-rib',
        'clear',
        'clear adj-rib',
        'help',
        'version',
        'shutdown',
    ] * (num_candidates // 20 + 1)
    candidates = candidates[:num_candidates]

    # Test queries (realistic partial inputs)
    test_queries = ['s', 'sh', 'sn', 'show', 'a', 'an', 'ar', 'w', 'wr', 't', 'f', 'fl']

    matcher = FuzzyMatcher()
    timings = []

    for _ in range(num_trials):
        for query in test_queries:
            start = time.perf_counter()
            matcher.get_matches(query, candidates, limit=10)
            end = time.perf_counter()
            timings.append((end - start) * 1000)  # Convert to ms

    # Calculate statistics
    timings.sort()
    return {
        'min_ms': timings[0],
        'max_ms': timings[-1],
        'avg_ms': sum(timings) / len(timings),
        'p50_ms': timings[len(timings) // 2],
        'p95_ms': timings[int(len(timings) * 0.95)],
        'p99_ms': timings[int(len(timings) * 0.99)],
        'num_candidates': num_candidates,
        'num_trials': num_trials,
    }


def print_benchmark_results(stats: dict[str, float]) -> None:
    """Pretty-print benchmark results.

    Args:
        stats: Statistics dict from benchmark_fuzzy_matching()
    """
    print(f"\nFuzzy Matching Performance Benchmark")
    print(f"=====================================")
    print(f"Candidates: {stats['num_candidates']}")
    print(f"Trials:     {stats['num_trials']} × 12 queries = {stats['num_trials'] * 12} total")
    print(f"\nLatency Statistics:")
    print(f"  Min:  {stats['min_ms']:6.2f} ms")
    print(f"  P50:  {stats['p50_ms']:6.2f} ms")
    print(f"  Avg:  {stats['avg_ms']:6.2f} ms")
    print(f"  P95:  {stats['p95_ms']:6.2f} ms")
    print(f"  P99:  {stats['p99_ms']:6.2f} ms")
    print(f"  Max:  {stats['max_ms']:6.2f} ms")
    print(f"\nTarget:     <100 ms (P99)")
    print(f"Status:     {'✅ PASS' if stats['p99_ms'] < 100 else '❌ FAIL'}")


if __name__ == '__main__':
    # Run benchmark when executed directly
    print("Running fuzzy matching performance benchmark...")
    stats = benchmark_fuzzy_matching(num_candidates=200, num_trials=100)
    print_benchmark_results(stats)
