"""Every form of every declared keyword reads the same with the legacy parser and the grammar."""

from __future__ import annotations

import pytest

from config_grammar.differential import Accepted, agree, grammar, legacy
from config_grammar.forms import DOCUMENTS, Form, all_forms, declared_leaves, wrapper
from config_grammar.forms_neighbor import ANY_WORD
from exabgp.configuration.compare import difference


def _id(form: Form) -> str:
    return f'{"/".join(form.path)}: {form.statement}'


@pytest.mark.parametrize('form', all_forms(), ids=_id)
def test_a_form_reads_the_same_with_both_parsers(form: Form) -> None:
    document = form.document()
    old = legacy(document)
    new = grammar(document)

    assert agree(old, new), f'{document!r}\n{difference(old, new)}'
    if form.valid is not None:
        assert isinstance(old, Accepted) == form.valid, f'the corpus is wrong about {document!r}: legacy says {old}'


@pytest.mark.parametrize('document,valid', DOCUMENTS, ids=[repr(text) for text, _ in DOCUMENTS])
def test_a_document_reads_the_same_with_both_parsers(document: str, valid: bool) -> None:
    old = legacy(document)
    new = grammar(document)

    assert agree(old, new), f'{document!r}\n{difference(old, new)}'
    assert isinstance(old, Accepted) == valid, f'the corpus is wrong about {document!r}: legacy says {old}'


def test_every_declared_section_has_a_wrapper() -> None:
    for path, leaf in declared_leaves():
        assert wrapper(path, leaf.keyword), f'no wrapper for the section {"/".join(path)}'


def test_every_declared_leaf_has_forms() -> None:
    covered = {(form.path, form.keyword) for form in all_forms()}
    for path, leaf in declared_leaves():
        assert (path, leaf.keyword) in covered, f'{"/".join(path)} {leaf.keyword} has no form'


def test_every_declared_leaf_has_a_form_both_parsers_refuse() -> None:
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
    accepted = legacy('process p { run /bin/cat; }')
    changed = legacy('process p { run /bin/cat; respawn false; }')

    assert isinstance(accepted, Accepted) and isinstance(changed, Accepted)
    assert not agree(accepted, changed)
