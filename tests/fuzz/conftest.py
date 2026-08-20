"""Hypothesis profiles for the fuzz suite.

The property tests serve two purposes which want opposite settings.

As part of test_everything they are a gate: they must pass or fail on what the code does,
not on which examples Hypothesis happened to draw. A random seed there means a commit is
blocked by a bug someone else introduced last month, or waved through because the draw
was kind. The gate profile is therefore derandomized: the same examples every run.

Hunting for new bugs wants the opposite, many more examples and a different seed each
time. That is the hunt profile, run by ./qa/bin/fuzz_hunt rather than by the gate.

    HYPOTHESIS_PROFILE=hunt uv run pytest tests/fuzz

A failure found by the hunt profile is reproduced by passing the seed it printed to
--hypothesis-seed, and belongs in tests/unit as a plain test once it is understood.
"""

from __future__ import annotations

import os

from hypothesis import HealthCheck, settings

GATE_EXAMPLES = 200
HUNT_EXAMPLES = 2000

settings.register_profile(
    'gate',
    max_examples=GATE_EXAMPLES,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    print_blob=True,
)

settings.register_profile(
    'hunt',
    max_examples=HUNT_EXAMPLES,
    derandomize=False,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
    print_blob=True,
)

settings.load_profile(os.environ.get('HYPOTHESIS_PROFILE', 'gate'))
