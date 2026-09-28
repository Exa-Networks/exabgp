"""The grammar imports nothing of the legacy parser, so deleting the legacy parser leaves it whole.

The imports are read from the source, a function level import included. Only the direct
imports are checked: every exabgp module reaches `Configuration` through the reactor, and
`Configuration` imports the legacy sections until they are removed (phase 6).
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / 'src'
GRAMMAR = 'exabgp.configuration.grammar'
# what the grammar may use of exabgp.configuration, beside itself
ALLOWED = ('exabgp.configuration.settings',)


def _path(module: str) -> Path | None:
    base = SRC.joinpath(*module.split('.'))
    for candidate in (base.with_suffix('.py'), base / '__init__.py'):
        if candidate.is_file():
            return candidate
    return None


def _package(module: str, path: Path) -> str:
    return module if path.name == '__init__.py' else module.rpartition('.')[0]


def _absolute(module: str, path: Path, node: ast.ImportFrom) -> str:
    if not node.level:
        return node.module or ''
    parts = _package(module, path).split('.')
    base = '.'.join(parts[: len(parts) - node.level + 1])
    return f'{base}.{node.module}' if node.module else base


def _imports(module: str) -> set[str]:
    path = _path(module)
    assert path is not None, module
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), str(path))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            source = _absolute(module, path, node)
            for alias in node.names:
                name = f'{source}.{alias.name}'
                found.add(name if _path(name) else source)
    return {name for name in found if name.startswith('exabgp') and _path(name)}


def _grammar_modules() -> list[str]:
    return sorted(
        '.'.join(path.relative_to(SRC).with_suffix('').parts).removesuffix('.__init__')
        for path in (SRC / 'exabgp' / 'configuration' / 'grammar').rglob('*.py')
    )


def _legacy(module: str) -> bool:
    if not module.startswith('exabgp.configuration'):
        return False
    return not (module == GRAMMAR or module.startswith(GRAMMAR + '.') or module in ALLOWED)


def test_the_grammar_imports_no_legacy_module() -> None:
    legacy = [f'{module} imports {name}' for module in _grammar_modules() for name in _imports(module) if _legacy(name)]
    assert not legacy, '\n'.join(legacy)


def test_the_imports_are_found() -> None:
    found = {name for module in _grammar_modules() for name in _imports(module)}
    assert 'exabgp.configuration.settings' in found
    assert 'exabgp.bgp.message.update.nlri.flow' in found
    assert _legacy('exabgp.configuration.static.route')
    assert not _legacy('exabgp.configuration.grammar.nodes')
