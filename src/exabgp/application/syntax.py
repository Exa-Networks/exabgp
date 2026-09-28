"""Show what the configuration accepts, from the grammar which reads it.

Usage:
    exabgp configuration syntax                    # every section
    exabgp configuration syntax neighbor family    # one section
    exabgp configuration syntax --json neighbor    # as a JSON Schema
    exabgp configuration syntax --yang             # as a YANG module
"""

from __future__ import annotations

import argparse
import json
import sys

from exabgp.configuration.grammar.describe import find, json_document, syntax, yang_module
from exabgp.configuration.grammar.render import INDENT
from exabgp.configuration.grammar.tree.root import ROOT


def setargs(sub: argparse.ArgumentParser) -> None:
    sub.add_argument('section', nargs='*', help='the keywords leading to a section: neighbor, neighbor family, ...')
    output = sub.add_mutually_exclusive_group()
    output.add_argument('--json', action='store_true', help='print the JSON Schema of the values instead')
    output.add_argument('--yang', action='store_true', help='print the YANG module of the values instead')


def cmdline(cmdarg: argparse.Namespace) -> int:
    try:
        block = find(ROOT, cmdarg.section)
    except ValueError as exc:
        sys.stderr.write(f'{exc}\n')
        return 1
    if cmdarg.json:
        title = ' '.join(['ExaBGP', *cmdarg.section, 'configuration'])
        sys.stdout.write(json.dumps(json_document(block, title), indent=2) + '\n')
        return 0
    if cmdarg.yang:
        sys.stdout.write('\n'.join(yang_module(block)) + '\n')
        return 0
    lines = syntax(block)
    if block is not ROOT:
        name = f' {block.name.hint()}' if block.name is not None else ''
        lines = [f'{" ".join(cmdarg.section)}{name} {{', *(INDENT + line for line in lines), '}']
    sys.stdout.write('\n'.join(lines) + '\n')
    return 0
