"""Configuration cross-reference validators.

Validates that references between configuration sections are valid
(e.g., process names, template names).

Created on 2025-12-03.
Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Reference:
    """A reference to another configuration element.

    Tracks where a reference is made for better error messages.
    """

    name: str
    line: int
    context: str  # e.g., "neighbor 192.168.1.1"


@dataclass
class ValidationError:
    """A validation error with context."""

    message: str
    line: int
    context: str


class CrossReferenceValidator:
    """Validates that all configuration references resolve correctly.

    This validator tracks definitions (process names, template names) and
    references to them, then validates that all references resolve.

    Example:
        validator = CrossReferenceValidator()

        # Track definitions
        validator.register_process('monitor', line=5)
        validator.register_template('peer-template', line=10)

        # Track references
        validator.reference_process('monitor', line=25, context='neighbor 1.2.3.4')
        validator.reference_template('peer-template', line=30, context='neighbor 5.6.7.8')

        # Validate
        errors = validator.validate()
        if errors:
            for error in errors:
                print(f"Line {error.line}: {error.message}")
    """

    def __init__(self) -> None:
        """Initialize the validator."""
        # Definitions: name -> line number
        self._processes: dict[str, int] = {}
        self._templates: dict[str, int] = {}

        # References: list of Reference objects
        self._process_refs: list[Reference] = []
        self._template_refs: list[Reference] = []

    def register_process(self, name: str, line: int) -> None:
        """Register a process definition.

        Args:
            name: Process name
            line: Line number where defined
        """
        if name in self._processes:
            # Duplicate process name - could warn but for now just track last
            pass
        self._processes[name] = line

    def register_template(self, name: str, line: int) -> None:
        """Register a template definition.

        Args:
            name: Template name
            line: Line number where defined
        """
        if name in self._templates:
            # Duplicate template name - could warn but for now just track last
            pass
        self._templates[name] = line

    def reference_process(self, name: str, line: int, context: str = '') -> None:
        """Record a reference to a process.

        Args:
            name: Process name being referenced
            line: Line number where referenced
            context: Context string (e.g., "neighbor 1.2.3.4")
        """
        self._process_refs.append(Reference(name, line, context))

    def reference_template(self, name: str, line: int, context: str = '') -> None:
        """Record a reference to a template.

        Args:
            name: Template name being referenced
            line: Line number where referenced
            context: Context string (e.g., "neighbor 1.2.3.4")
        """
        self._template_refs.append(Reference(name, line, context))

    def validate(self) -> list[ValidationError]:
        """Validate all references.

        Returns:
            List of ValidationError objects (empty if no errors)
        """
        errors: list[ValidationError] = []

        # Check process references
        for ref in self._process_refs:
            if ref.name not in self._processes:
                context = f' in {ref.context}' if ref.context else ''
                errors.append(
                    ValidationError(
                        message=f"Reference to undefined process '{ref.name}'{context}",
                        line=ref.line,
                        context=ref.context,
                    )
                )

        # Check template references
        for ref in self._template_refs:
            if ref.name not in self._templates:
                context = f' in {ref.context}' if ref.context else ''
                errors.append(
                    ValidationError(
                        message=f"Reference to undefined template '{ref.name}'{context}",
                        line=ref.line,
                        context=ref.context,
                    )
                )

        return errors

    def get_unused_processes(self) -> list[tuple[str, int]]:
        """Find processes that are defined but never referenced.

        Returns:
            List of (process_name, line_number) tuples
        """
        referenced = {ref.name for ref in self._process_refs}
        return [(name, line) for name, line in self._processes.items() if name not in referenced]

    def get_unused_templates(self) -> list[tuple[str, int]]:
        """Find templates that are defined but never referenced.

        Returns:
            List of (template_name, line_number) tuples
        """
        referenced = {ref.name for ref in self._template_refs}
        return [(name, line) for name, line in self._templates.items() if name not in referenced]

    def clear(self) -> None:
        """Clear all tracked definitions and references."""
        self._processes.clear()
        self._templates.clear()
        self._process_refs.clear()
        self._template_refs.clear()
