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

import importlib
import os
import pkgutil

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


def _populate_the_registries() -> None:
    """Import every attribute module, so the registries are whole before collection.

    The registries fill by import side effect, and the property tests parametrise from
    them at collection time.  A test module which imports only what it names therefore
    sweeps a half empty registry and reports a clean run over a fraction of the codes:
    PrefixSid held only TLV 1 and 3 until sr/srv6/l2service and l3service were imported,
    which is how 5 and 6 went unswept.  Silent under-coverage is worse than a failure.
    """
    import exabgp.bgp.message.update.attribute as package

    for _finder, name, _is_package in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            importlib.import_module(name)
        except ImportError:
            # a module which cannot be imported is a problem for its own tests, not a
            # reason to stop filling the registries the property tests parametrise from
            continue


_populate_the_registries()
