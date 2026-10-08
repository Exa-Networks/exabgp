"""`rate-limit disable` is no limit, as 5.0 read it, so the line str(neighbor) prints reads back."""

from __future__ import annotations

import pytest

from exabgp.configuration.grammar.read import read_text

NEIGHBOR = 'neighbor 127.0.0.1 {{ router-id 10.0.0.1; local-address 127.0.0.1; local-as 65001; peer-as 65002; {line} }}'


def _rate_limit(line: str) -> int:
    (settings,) = read_text(NEIGHBOR.format(line=line)).neighbors
    return settings.rate_limit


@pytest.mark.parametrize('word', ['disable', 'disabled', 'DISABLE'])
def test_disable_is_no_limit(word: str) -> None:
    assert _rate_limit(f'rate-limit {word};') == 0


def test_a_number_is_still_a_number() -> None:
    assert _rate_limit('rate-limit 10;') == 10
    assert _rate_limit('rate-limit 0;') == 0


@pytest.mark.parametrize('word', ['enable', '-5', 'disables'])
def test_other_words_are_refused(word: str) -> None:
    with pytest.raises(ValueError, match='rate-limit'):
        _rate_limit(f'rate-limit {word};')


def test_the_printed_rate_limit_reads_back() -> None:
    from exabgp.configuration.configuration import Configuration

    configuration = Configuration([NEIGHBOR.format(line='')], text=True)
    assert configuration.reload()
    (neighbor,) = configuration.neighbors.values()
    printed = next(line.strip() for line in str(neighbor).splitlines() if line.strip().startswith('rate-limit'))
    assert printed == 'rate-limit disable;'
    assert _rate_limit(printed) == 0
