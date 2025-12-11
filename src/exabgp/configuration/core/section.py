"""section.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from string import ascii_letters, digits
from typing import TYPE_CHECKING, Any, Callable, TypeVar

from exabgp.configuration.core.action import apply_action
from exabgp.configuration.core.error import Error
from exabgp.configuration.core.parser import Parser
from exabgp.configuration.core.scope import Scope
from exabgp.configuration.schema import ActionKey, ActionOperation, ActionTarget
from exabgp.protocol.family import AFI, SAFI

if TYPE_CHECKING:
    from exabgp.configuration.schema import Completion, Container
    from exabgp.configuration.validator import Validator

F = TypeVar('F', bound=Callable[..., Any])


def _levenshtein(s1: str, s2: str) -> int:
    """Calculate Levenshtein (edit) distance between two strings.

    Returns the minimum number of single-character edits (insertions,
    deletions, substitutions) needed to transform s1 into s2.
    """
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def _find_similar(target: str, candidates: list[str], max_distance: int = 2, max_results: int = 3) -> list[str]:
    """Find similar strings using Levenshtein distance.

    Args:
        target: The string to find similar matches for
        candidates: List of valid strings to compare against
        max_distance: Maximum edit distance to consider a match (default: 2)
        max_results: Maximum number of suggestions to return (default: 3)

    Returns:
        List of similar strings sorted by edit distance (closest first)
    """
    if not target or not candidates:
        return []

    scored = []
    target_lower = target.lower()
    for candidate in candidates:
        dist = _levenshtein(target_lower, candidate.lower())
        if dist <= max_distance:
            scored.append((dist, candidate))

    # Sort by distance (closest first), then alphabetically
    scored.sort(key=lambda x: (x[0], x[1]))
    return [s[1] for s in scored[:max_results]]


class Section(Error):
    name = 'undefined'
    known: dict[str | tuple[Any, ...], Any] = {}  # command/section and code to handle it
    default: dict[
        str | tuple[Any, ...], Any
    ] = {}  # command/section has a a defult value, use it if no data was provided
    action: dict[str | tuple[Any, ...], tuple[ActionTarget, ActionOperation, ActionKey]] = {}  # action enums tuple
    assign: dict[str, str] = {}  # configuration to class variable lookup for setattr

    def __init__(self, parser: Parser, scope: Scope, error: Error) -> None:
        Error.__init__(self)
        self.parser = parser
        self.scope = scope
        self.error = error
        self._names: list[str] = []

    def clear(self) -> None:
        self._names = []

    @classmethod
    def register_family(
        cls,
        afi: AFI,
        safi: SAFI,
        target: ActionTarget,
        operation: ActionOperation,
        key: ActionKey = ActionKey.COMMAND,
    ) -> Callable[[F], F]:
        """Register a handler for an AFI/SAFI family combination."""

        def inner(function: F) -> F:
            afi_name = '' if afi == AFI.undefined else afi.name()
            safi_name = safi.name()
            identifier: str | tuple[str, str] = (afi_name, safi_name) if afi_name else safi_name
            if identifier in cls.known:
                raise RuntimeError('more than one registration per command attempted')
            cls.known[identifier] = function
            cls.action[identifier] = (target, operation, key)
            return function

        return inner

    @classmethod
    def register_command(
        cls,
        command: str,
        target: ActionTarget,
        operation: ActionOperation,
        key: ActionKey = ActionKey.COMMAND,
    ) -> Callable[[F], F]:
        """Register a handler for a simple command (no AFI/SAFI)."""

        def inner(function: F) -> F:
            if command in cls.known:
                raise RuntimeError('more than one registration per command attempted')
            cls.known[command] = function
            cls.action[command] = (target, operation, key)
            return function

        return inner

    def check_name(self, name: str) -> None:
        if any(False if c in ascii_letters + digits + '.-_' else True for c in name):
            self.throw(f'invalid character in name for {self.name} ')
        if name in self._names:
            self.throw(f'the name "{name}" already exists in {self.name}')
        self._names.append(name)

    def pre(self) -> bool:
        return True

    def post(self) -> bool:
        return True

    def _get_stateful_validator(self, command: str) -> 'Validator[Any] | None':
        """Get a stateful validator for commands requiring instance state.

        Override in subclasses (like ParseFamily, ParseNextHop) to inject
        instance-level state (e.g., _seen set for deduplication) into validators.

        Args:
            command: The command name being parsed

        Returns:
            StatefulValidator wrapping the schema validator, or None to use default
        """
        return None

    def parse(self, name: str, command: str) -> bool:  # noqa: C901
        """Parse a command and apply its action.

        Parser lookup priority:
        1. self.known dict (explicit registration) - backwards compatible
        2. Stateful validator (from _get_stateful_validator hook)
        3. Schema validator (auto-generated from Leaf/LeafList)
        4. Error if none found
        """
        identifier = command if command in self.known else (self.name, command)

        try:
            # Priority 1: Try known dict first (backwards compatible)
            if identifier in self.known:
                if command in self.default:
                    insert = self.known[identifier](self.parser.tokeniser, self.default[command])
                else:
                    insert = self.known[identifier](self.parser.tokeniser)
            else:
                # Priority 2: Try stateful validator (for sections with deduplication)
                validator = self._get_stateful_validator(command)

                # Priority 3: Try schema validator
                if validator is None:
                    validator = self._validator_from_schema(command)
                if validator is not None:
                    insert = validator.validate(self.parser.tokeniser)
                else:
                    # Priority 4: Unknown command - show suggestions
                    simple_options = sorted([k for k in self.known if isinstance(k, str)])
                    suggestions = _find_similar(command, simple_options)

                    msg = f"unknown command '{command}'"
                    if suggestions:
                        msg += f'\n  Did you mean: {", ".join(suggestions)}?'
                    if simple_options:
                        msg += f'\n  Valid options: {", ".join(simple_options)}'

                    return self.error.set(msg)

            # Unified action dispatch - get action enums from schema or decorator registration
            action_enums = self._action_enums_from_schema(command)
            if action_enums is not None:
                target, operation, key, field_name = action_enums
            else:
                # Try decorator-registered actions (@Section.register)
                action_tuple = self.action.get(identifier)
                if action_tuple is not None:
                    target, operation, key = action_tuple
                    field_name = None
                else:
                    raise RuntimeError(f'name {name} command {command} has no action set')

            # Use assign dict to get field name, with schema field_name as fallback
            resolved_field = self.assign.get(command, field_name)
            apply_action(target, operation, key, self.scope, name, command, insert, resolved_field)
            return True
        except ValueError as exc:
            return self.error.set(str(exc))

    # Schema-based methods

    schema: 'Container | None' = None  # Override in subclasses with schema definitions

    @classmethod
    def _action_enums_from_schema(
        cls, command: str
    ) -> 'tuple[ActionTarget, ActionOperation, ActionKey, str | None] | None':
        """Get action enums for command from schema.

        Args:
            command: The command name to look up

        Returns:
            Tuple of (target, operation, key, field_name) from schema,
            or None if schema not defined or command not found.
        """
        if cls.schema is None:
            return None

        from exabgp.configuration.schema import Leaf, LeafList

        child = cls.schema.children.get(command)
        if isinstance(child, (Leaf, LeafList)):
            target, operation, key = child.get_action_enums()
            field_name = child.field_name if hasattr(child, 'field_name') else None
            return (target, operation, key, field_name)
        return None

    @classmethod
    def _validator_from_schema(cls, command: str) -> 'Validator[Any] | None':
        """Get validator for command from schema.

        Args:
            command: The command name to look up

        Returns:
            Validator from schema Leaf/LeafList, or None if not found
        """
        if cls.schema is None:
            return None

        from exabgp.configuration.schema import Leaf, LeafList

        child = cls.schema.children.get(command)
        if isinstance(child, (Leaf, LeafList)):
            return child.get_validator()
        return None

    @classmethod
    def get_schema_completions(cls) -> list['Completion']:
        """Get completions from this section's schema.

        Returns:
            List of Completion objects for commands and subsections.
            Empty list if no schema defined.
        """
        if cls.schema is None:
            return []

        from exabgp.configuration.schema import get_completions

        return get_completions(cls.schema, [])

    @classmethod
    def get_schema_value_completions(cls, command: str, partial: str = '') -> list[str]:
        """Get value completions for an enumeration command.

        Args:
            command: The command name
            partial: Partial value typed so far

        Returns:
            List of matching value strings.
            Empty list if command not found or not an enumeration.
        """
        if cls.schema is None:
            return []

        from exabgp.configuration.schema import get_value_completions

        return get_value_completions(cls.schema, [command], partial)

    @classmethod
    def has_schema(cls) -> bool:
        """Check if this section has a schema defined."""
        return cls.schema is not None

    @classmethod
    def get_subsection_keywords(cls) -> list[str]:
        """Get subsection keywords from schema Container children.

        Returns:
            List of keywords that represent subsections (Container children).
            Empty list if no schema defined.
        """
        if cls.schema is None:
            return []

        from exabgp.configuration.schema import Container

        return [name for name, child in cls.schema.children.items() if isinstance(child, Container)]
