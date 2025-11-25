"""section.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import Union
from typing import List
from string import ascii_letters
from string import digits

from exabgp.configuration.core.error import Error


def _levenshtein(s1: str, s2: str) -> int:
    """Calculate Levenshtein (edit) distance between two strings.

    Returns the minimum number of single-character edits (insertions,
    deletions, substitutions) needed to transform s1 into s2.
    """
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
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


def _find_similar(target: str, candidates: List[str], max_distance: int = 2, max_results: int = 3) -> List[str]:
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
    known: dict[Union[str, tuple], object] = dict()  # command/section and code to handle it
    default: dict[Union[str, tuple], object] = (
        dict()
    )  # command/section has a a defult value, use it if no data was provided
    action: dict[Union[str, tuple], str] = {}  # how to handle this command ( append, add, assign, route )
    assign: dict[str, str] = {}  # configuration to class variable lookup for setattr

    def __init__(self, tokerniser, scope, error):
        Error.__init__(self)
        self.tokeniser = tokerniser
        self.scope = scope
        self.error = error
        self._names = []

    def clear(self):
        self._names = []

    @classmethod
    def register(cls, name, action, afi=''):
        def inner(function):
            identifier = (afi, name) if afi else name
            if identifier in cls.known:
                raise RuntimeError('more than one registration per command attempted')
            cls.known[identifier] = function
            cls.action[identifier] = action
            return function

        return inner

    def check_name(self, name):
        if any(False if c in ascii_letters + digits + '.-_' else True for c in name):
            self.throw(f'invalid character in name for {self.name} ')
        if name in self._names:
            self.throw(f'the name "{name}" already exists in {self.name}')
        self._names.append(name)

    def pre(self):
        return True

    def post(self):
        return True

    def parse(self, name, command):  # noqa: C901
        identifier = command if command in self.known else (self.name, command)
        if identifier not in self.known:
            # Get simple string options (filter out tuple identifiers like ('ipv4', 'unicast'))
            simple_options = sorted([k for k in self.known if isinstance(k, str)])

            # Find similar commands for "did you mean?" suggestions
            suggestions = _find_similar(command, simple_options)

            # Build error message
            msg = f"unknown command '{command}'"
            if suggestions:
                msg += f'\n  Did you mean: {", ".join(suggestions)}?'
            if simple_options:
                msg += f'\n  Valid options: {", ".join(simple_options)}'

            return self.error.set(msg)

        try:
            if command in self.default:
                insert = self.known[identifier](self.tokeniser.iterate, self.default[command])
            else:
                insert = self.known[identifier](self.tokeniser.iterate)

            action = self.action.get(identifier, '')

            if action == 'set-command':
                self.scope.set(command, insert)
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

        return True
