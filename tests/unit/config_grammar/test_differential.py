"""Every configuration in the repository reads the same with the legacy parser and the grammar."""

from __future__ import annotations

import glob
import os

import pytest

from config_grammar.differential import agree, grammar_file, legacy_file
from exabgp.configuration.compare import difference

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
CONFIGURATIONS = sorted(
    glob.glob(os.path.join(ROOT, 'etc', 'exabgp', '*.conf'))
    + glob.glob(os.path.join(ROOT, 'tests', 'unit', 'configuration', 'fixtures', '**', '*.conf'), recursive=True)
)


@pytest.mark.parametrize('path', CONFIGURATIONS, ids=lambda path: os.path.relpath(path, ROOT))
def test_a_configuration_reads_the_same_with_both_parsers(path: str) -> None:
    new = grammar_file(path)
    old = legacy_file(path)

    assert agree(old, new), f'{path}\n{difference(old, new)}'


def test_the_configurations_were_found() -> None:
    assert len(CONFIGURATIONS) > 100
