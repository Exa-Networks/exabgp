"""Every form of every declared keyword is accepted or refused as the legacy parser did.

Whether a form is valid was recorded against the legacy parser while it existed (forms*.py);
what an accepted form makes is held to the frozen results (test_frozen.py).
"""

from __future__ import annotations

import pytest

from config_grammar.differential import Accepted, agree, grammar
from config_grammar.forms import DOCUMENTS, Form, all_forms, declared_leaves, wrapper
from config_grammar.forms_neighbor import ANY_WORD


def _id(form: Form) -> str:
    return f'{"/".join(form.path)}: {form.statement}'


JUDGED = [form for form in all_forms() if form.valid is not None]


@pytest.mark.parametrize('form', JUDGED, ids=_id)
def test_a_form_is_accepted_or_refused_as_the_legacy_parser_did(form: Form) -> None:
    document = form.document()
    found = grammar(document)
    assert isinstance(found, Accepted) == form.valid, f'{document!r}: the grammar says {found}'


@pytest.mark.parametrize('document,valid', DOCUMENTS, ids=[repr(text) for text, _ in DOCUMENTS])
def test_a_document_is_accepted_or_refused_as_the_legacy_parser_did(document: str, valid: bool) -> None:
    found = grammar(document)
    assert isinstance(found, Accepted) == valid, f'{document!r}: the grammar says {found}'


def test_every_declared_section_has_a_wrapper() -> None:
    for path, leaf in declared_leaves():
        assert wrapper(path, leaf.keyword), f'no wrapper for the section {"/".join(path)}'


def test_every_declared_leaf_has_forms() -> None:
    covered = {(form.path, form.keyword) for form in all_forms()}
    for path, leaf in declared_leaves():
        assert (path, leaf.keyword) in covered, f'{"/".join(path)} {leaf.keyword} has no form'


def test_every_declared_leaf_has_a_refused_form() -> None:
    refused = {(form.path, form.keyword) for form in all_forms() if form.valid is False}
    for path, leaf in declared_leaves():
        if path[:1] == ('template',):
            # the template forms are the neighbor ones, whose refusals are checked in a neighbor
            continue
        if (path, leaf.keyword) in ANY_WORD:
            continue
        assert (path, leaf.keyword) in refused, f'{"/".join(path)} {leaf.keyword} has no invalid form'


def test_the_comparison_can_fail() -> None:
    """A difference in what was built is seen, not only a difference in the verdict."""
    accepted = grammar('process p { run /bin/cat; }')
    changed = grammar('process p { run /bin/cat; respawn false; }')

    assert isinstance(accepted, Accepted) and isinstance(changed, Accepted)
    assert not agree(accepted, changed)
