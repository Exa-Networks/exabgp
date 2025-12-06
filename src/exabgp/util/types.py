"""Central type definitions for ExaBGP.

This module provides type aliases that are both runtime-compatible and
mypy-compatible. The main reason for this module is that mypy doesn't
fully support the PEP 688 Buffer protocol yet.

See: https://peps.python.org/pep-0688/
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # For type checking, use a Union that mypy understands fully
    # bytes and memoryview both support len(), indexing, iteration
    Buffer = bytes | memoryview
else:
    # At runtime, use the actual PEP 688 Buffer protocol
    from collections.abc import Buffer

__all__ = ['Buffer']
