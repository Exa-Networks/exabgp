"""What the legacy parser made of every input of the grammar tests, kept now it is gone.

Every document of the forms corpus, every configuration file and every API command is read,
and what it produced is reduced to a digest: the outcome as canonical text (the processes
and the neighbors of `outcome.outcome`, or `rejected`), then hashed. The file maps a digest
of the input to a digest of the outcome, so it stays small.

It was written from the legacy parser, and the grammar is held to it: it is the proof the
behaviour was preserved when the legacy parser was removed. Regenerate it only for a change
of behaviour made on purpose, and say so in the commit:

    cd tests/unit && env exabgp_log_enable=false ../../.venv/bin/python -m config_grammar.frozen

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
from collections import deque
from typing import Any, Callable

from config_grammar.differential import (
    COMMANDS,
    CONFIGURATIONS,
    ROOT,
    Accepted,
    Outcome,
    grammar,
    grammar_command,
    grammar_file,
)
from config_grammar.forms import DOCUMENTS, all_forms
from exabgp.environment import getenv

FROZEN = os.path.join(ROOT, 'tests', 'unit', 'configuration', 'forms', 'expected', 'legacy.json')
DIGEST = 16  # hex characters kept of a sha256, plenty for some thousand inputs


def canonical(value: Any) -> Any:
    """`value` as JSON, every object by its repr: equal outcomes give equal text."""
    if isinstance(value, dict):
        return {key if isinstance(key, str) else repr(key): canonical(each) for key, each in value.items()}
    if isinstance(value, (list, tuple, deque)):
        return [canonical(each) for each in value]
    if isinstance(value, (set, frozenset)):
        return sorted(repr(each) for each in value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return canonical({field.name: getattr(value, field.name) for field in dataclasses.fields(value)})
    return repr(value)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:DIGEST]


def _portable(processes: dict[str, Any]) -> dict[str, Any]:
    """The processes with the program as named, not where this machine's PATH finds it."""
    found = {}
    for name, process in processes.items():
        run = process.get('run') or []
        found[name] = {**process, 'run': [os.path.basename(run[0]), *run[1:]] if run else run}
    return found


def outcome_digest(outcome: Outcome | list[Any] | str) -> str:
    """A configuration's Accepted or Rejected, or an API command's routes or `rejected`."""
    reduced: Any = 'rejected'
    if isinstance(outcome, Accepted):
        reduced = [canonical(_portable(outcome.processes)), canonical(outcome.neighbors)]
    elif isinstance(outcome, (list, str)):
        reduced = canonical(outcome)
    return digest(json.dumps(reduced, sort_keys=True))


def inputs() -> dict[str, Callable[[], Any]]:
    """Every input by name, with how the grammar reads it."""
    found: dict[str, Callable[[], Any]] = {}
    for document in [form.document() for form in all_forms()] + [document for document, _ in DOCUMENTS]:
        found[f'document {document}'] = lambda document=document: grammar(document)
    for configuration in CONFIGURATIONS:
        found[f'file {os.path.relpath(configuration, ROOT)}'] = lambda configuration=configuration: grammar_file(
            configuration
        )
    for action, line in COMMANDS:
        found[f'command {action} {line}'] = lambda action=action, line=line: grammar_command(action, line)
    return found


def read() -> dict[str, tuple[str, str]]:
    """The digest of each input, with the input, as the grammar reads it."""
    return {digest(name): (outcome_digest(reading()), name) for name, reading in inputs().items()}


def load() -> dict[str, str]:
    with open(FROZEN) as handle:
        frozen: dict[str, str] = json.load(handle)
    return frozen


def main() -> None:
    getenv().bgp.passive = False
    frozen = {key: value for key, (value, _) in sorted(read().items())}
    os.makedirs(os.path.dirname(FROZEN), exist_ok=True)
    with open(FROZEN, 'w') as handle:
        json.dump(frozen, handle, indent=0, sort_keys=True)
        handle.write('\n')
    print(f'{len(frozen)} inputs frozen in {os.path.relpath(FROZEN, ROOT)}')


if __name__ == '__main__':
    main()
