"""The grammar makes of every input what the legacy parser made of it, as frozen in config_grammar.frozen."""

from __future__ import annotations

from config_grammar.frozen import load, read

MAX_REPORTED = 20  # the first inputs which differ are what matter


def test_the_grammar_reads_every_input_as_the_legacy_parser_did() -> None:
    frozen = load()
    current = read()

    missing = sorted(name for key, (_, name) in current.items() if key not in frozen)
    assert not missing, 'inputs never frozen, regenerate config_grammar.frozen:\n' + '\n'.join(missing[:MAX_REPORTED])
    assert len(frozen) == len(current), 'inputs frozen which no test has any more, regenerate config_grammar.frozen'
    different = sorted(name for key, (value, name) in current.items() if frozen[key] != value)
    assert not different, 'read differently than frozen:\n' + '\n'.join(different[:MAX_REPORTED])
