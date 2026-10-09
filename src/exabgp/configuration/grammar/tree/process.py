"""process.py

    process <name> {
        run <program> [<argument> ...];
        encoder text|json;
        respawn true|false;
        on-exit withdraw|keep;
    }

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.configuration.grammar.context import ReadContext
from exabgp.configuration.grammar.nodes import Block, Keep, Leaf
from exabgp.configuration.grammar.section import Section, Values
from exabgp.configuration.grammar.types.basic import Bool, Choice, Program, SectionName
from exabgp.configuration.settings import Encoder, OnExit, ProcessSettings


class ProcessSection(Section[ProcessSettings]):
    builds = ProcessSettings

    def build(self, name: str, values: Values, context: ReadContext) -> ProcessSettings:
        return ProcessSettings(**values)


PROCESS = Block(
    'process',
    field='processes',
    section=ProcessSection(),
    keep=Keep.NAMED,
    name=SectionName('process'),
    doc='an external program exabgp runs and talks to over the API',
    missing='unset process sections: {names}',
    children=(
        Leaf('run', Program(), field='run', mandatory=True, doc='the program to run, with its arguments'),
        Leaf(
            'encoder',
            Choice(Encoder, 'encoder'),
            field='encoder',
            default=Encoder.TEXT,
            doc='how messages to the program are written',
        ),
        Leaf('respawn', Bool(bare=True), field='respawn', default=True, doc='restart the program when it exits'),
        Leaf(
            'on-exit',
            Choice(OnExit, 'on-exit'),
            field='on_exit',
            doc=(
                'what happens to the routes the program announced when it exits; unset, they are '
                'kept for a program using API 4 and withdrawn otherwise'
            ),
        ),
    ),
)
