"""Export ExaBGP configuration schema as JSON Schema.

This command outputs the configuration schema in JSON Schema format (2020-12),
useful for IDE integration, validation tools, and documentation. It is printed from
the data model of the configuration grammar, as `exabgp configuration syntax --json`.

Usage:
    exabgp schema export              # Output full schema to stdout
    exabgp schema export --compact    # Minified JSON output
    exabgp schema export neighbor     # Export specific section
"""

from __future__ import annotations

import argparse
import json
import sys

from exabgp.configuration.grammar.describe import find, json_document
from exabgp.configuration.grammar.nodes import Block
from exabgp.configuration.grammar.tree.root import ROOT

# the sections exported by name: the top ones, then those of a neighbor
TOP = ('neighbor', 'process', 'template')


def setargs(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        'action',
        nargs='?',
        default='export',
        choices=['export'],
        help='Action to perform (default: export)',
    )
    sub.add_argument(
        'section',
        nargs='?',
        default=None,
        help='Specific section to export (neighbor, process, template, etc.)',
    )
    sub.add_argument(
        '--compact',
        action='store_true',
        help='Output minified JSON (no indentation)',
    )


def section_block(section: str) -> Block | None:
    """The block of a section: a top one, or one of a neighbor (`capability`, `static`, ...)."""
    for path in ([section], ['neighbor', section]):
        try:
            return find(ROOT, path)
        except ValueError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    setargs(parser)
    return cmdline(parser.parse_args())


def cmdline(cmdarg: argparse.Namespace) -> int:
    if cmdarg.action != 'export':
        sys.stderr.write(f'Unknown action: {cmdarg.action}\n')
        return 1

    block = ROOT
    if cmdarg.section:
        found = section_block(cmdarg.section)
        if found is None:
            neighbor = find(ROOT, ['neighbor'])
            available = [*TOP, *(child.keyword for child in neighbor.blocks())]
            sys.stderr.write(f'Unknown section: {cmdarg.section}\n')
            sys.stderr.write(f'Available sections: {", ".join(available)}\n')
            return 1
        block = found

    title = f'ExaBGP {cmdarg.section} configuration' if cmdarg.section else 'ExaBGP configuration'
    document = json_document(block, title)
    separators = (',', ':') if cmdarg.compact else None
    sys.stdout.write(json.dumps(document, indent=None if cmdarg.compact else 2, separators=separators) + '\n')
    sys.stdout.flush()
    return 0


if __name__ == '__main__':
    sys.exit(main())
