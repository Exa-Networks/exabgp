"""Each part of a neighbor has one codec, which owns its statements and prints only them."""

from __future__ import annotations

from collections import Counter

import pytest

from config_grammar.forms import DOCUMENTS, all_forms
from exabgp.configuration.grammar.context import PrintContext
from exabgp.configuration.grammar.read import read_text
from exabgp.configuration.grammar.section import Codec
from exabgp.configuration.grammar.tree.codecs import CODECS, NEIGHBOR_FIELDS
from exabgp.configuration.grammar.tree.neighbor import NEIGHBOR, TEMPLATE

VALID = [form.document() for form in all_forms() if form.valid] + [text for text, valid in DOCUMENTS if valid]


def test_every_field_of_a_neighbor_has_one_owner() -> None:
    owners = Counter(field for codec in CODECS for field in codec.fields)
    owners.update(NEIGHBOR_FIELDS)
    assert [field for field, count in owners.items() if count > 1] == []
    assert set(owners) == {child.field for child in NEIGHBOR.children}


def test_a_template_has_the_fields_of_a_neighbor() -> None:
    (template,) = TEMPLATE.blocks()
    assert {child.field for child in template.children} == {child.field for child in NEIGHBOR.children}


def test_every_codec_is_run() -> None:
    assert {type(codec) for codec in CODECS} == set(Codec.__subclasses__())


@pytest.mark.parametrize('document', VALID)
def test_a_codec_prints_only_its_own_fields(document: str) -> None:
    for settings in read_text(document).neighbors:
        context = PrintContext()
        for codec in CODECS:
            printed = set(codec.unresolve(settings, context))
            assert printed <= set(codec.fields), f'{type(codec).__name__} prints {printed - set(codec.fields)}'
