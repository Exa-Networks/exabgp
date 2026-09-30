"""Central type definitions for ExaBGP.

This module provides type aliases that are both runtime-compatible and
mypy-compatible. The main reason for this module is that mypy doesn't
fully support the PEP 688 Buffer protocol yet.

See: https://peps.python.org/pep-0688/
"""

# A Union that mypy understands fully: bytes and memoryview both support len(), indexing
# and iteration. The same at run time, where it only ever appears in annotations: it was
# collections.abc.Buffer there, behind `if TYPE_CHECKING`, which mypyc compiles as
# unreachable code (the compiled module raised at import).
Buffer = bytes | memoryview

__all__ = ['Buffer']
