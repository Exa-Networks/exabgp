"""section.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Any, Callable, TypeVar, TYPE_CHECKING
from string import ascii_letters
from string import digits

from exabgp.configuration.core.error import Error
from exabgp.configuration.core.scope import Scope
from exabgp.configuration.core.parser import Parser

if TYPE_CHECKING:
    from exabgp.configuration.schema import Container, Completion
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
    action: dict[str | tuple[Any, ...], str] = {}  # how to handle this command ( append, add, assign, route )
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
    def register(cls, name: str, action: str, afi: str = '') -> Callable[[F], F]:
        def inner(function: F) -> F:
            identifier: str | tuple[str, str] = (afi, name) if afi else name
            if identifier in cls.known:
                raise RuntimeError('more than one registration per command attempted')
            cls.known[identifier] = function
            cls.action[identifier] = action
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

    def parse(self, name: str, command: str) -> bool:  # noqa: C901
        """Parse a command and apply its action.

        Parser lookup priority:
        1. self.known dict (explicit registration) - backwards compatible
        2. Schema validator (auto-generated from Leaf/LeafList)
        3. Error if neither found
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
                # Priority 2: Try schema validator
                validator = self._validator_from_schema(command)
                if validator is not None:
                    insert = validator.validate(self.parser.tokeniser)
                else:
                    # Priority 3: Unknown command - show suggestions
                    simple_options = sorted([k for k in self.known if isinstance(k, str)])
                    suggestions = _find_similar(command, simple_options)

                    msg = f"unknown command '{command}'"
                    if suggestions:
                        msg += f'\n  Did you mean: {", ".join(suggestions)}?'
                    if simple_options:
                        msg += f'\n  Valid options: {", ".join(simple_options)}'

                    return self.error.set(msg)

            # Get action (from schema or dict)
            action = self._action_from_schema(command) or self.action.get(identifier, '')

            if action == 'set-command':
                self.scope.set_value(command, insert)
            elif action == 'extend-name':
                self.scope.extend(name, insert)
            elif action == 'append-name':
                self.scope.append(name, insert)
            elif action == 'append-command':
                self.scope.append(command, insert)
            elif action == 'extend-command':
                self.scope.extend(command, insert)
            elif action == 'attribute-add':
                self.scope.attribute_add(name, insert)
            elif action == 'nlri-set':
                self.scope.nlri_assign(name, self.assign[command], insert)
            elif action == 'nlri-add':
                for adding in insert:
                    self.scope.nlri_add(name, command, adding)
            elif action == 'nlri-nexthop':
                self.scope.nlri_nexthop(name, insert)
            elif action == 'nexthop-and-attribute':
                ip, attribute = insert
                if ip:
                    self.scope.nlri_nexthop(name, ip)
                if attribute:
                    self.scope.attribute_add(name, attribute)
            elif action == 'append-route':
                self.scope.extend_routes(insert)
            elif action == 'nop':
                pass
            else:
                raise RuntimeError(f'name {name} command {command} has no action set')
            return True
        except ValueError as exc:
            return self.error.set(str(exc))

    # Schema-based methods

    schema: 'Container | None' = None  # Override in subclasses with schema definitions

    @classmethod
    def _action_from_schema(cls, command: str) -> str | None:
        """Get action for command from schema.

        Args:
            command: The command name to look up

        Returns:
            Action string from schema, or None if schema not defined
            or command not found in schema children.
        """
        if cls.schema is None:
            return None

        from exabgp.configuration.schema import Leaf, LeafList

        child = cls.schema.children.get(command)
        if isinstance(child, (Leaf, LeafList)):
            return child.action
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
