#!/usr/bin/env python3
"""test_environment_naming.py

The dotted setting name is the primary form: exabgp.api.ack is what the code looks for
first, exabgp_api_ack is the fallback for the shells whose export builtin refuses a name
which is not an identifier.

These tests pin that behaviour down, both in the environment parsing code and in the
shells the documentation writes examples for.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

import pytest


def _repository_root() -> str:
    """The repository, even when the tests are running from a copy of it.

    mutmut copies the tree into ./mutants and rewrites the modules it mutates with an
    in-process trampoline which reads MUTANT_UNDER_TEST.  These tests launch `exabgp` as
    a subprocess, which the trampoline is not prepared for, and a subprocess would not
    carry the mutant anyway.  Run the real launcher: what is under test here is how a
    setting is named, not how an NLRI decodes.
    """
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if os.path.basename(root) == 'mutants':
        return os.path.dirname(root)
    return root


ROOT = _repository_root()
EXABGP = os.path.join(ROOT, 'sbin', 'exabgp')

DOTTED = 'exabgp.api.ack'
UNDERSCORE = 'exabgp_api_ack'


def setting(environment: dict[str, str], name: str = 'api.ack') -> str:
    """Return the value exabgp resolves for a setting, as reported by `exabgp env -e`."""
    result = subprocess.run(
        [EXABGP, 'env', '-e'],
        capture_output=True,
        text=True,
        env={**os.environ, 'exabgp_log_enable': 'false', **environment},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    for line in result.stdout.split('\n'):
        if line.startswith(f'exabgp.{name}='):
            return line.split('=', 1)[1]
    raise AssertionError(f'exabgp.{name} missing from the environment listing')


class TestSettingNames:
    """Both spellings reach the code, the dotted one wins."""

    def test_default(self):
        assert setting({}) == 'true'

    def test_dotted_name_is_read(self):
        assert setting({DOTTED: 'false'}) == 'false'

    def test_underscore_name_is_read(self):
        assert setting({UNDERSCORE: 'false'}) == 'false'

    def test_dotted_name_takes_precedence(self):
        # both set, disagreeing: the dotted name is the one which counts
        assert setting({DOTTED: 'false', UNDERSCORE: 'true'}) == 'false'
        assert setting({DOTTED: 'true', UNDERSCORE: 'false'}) == 'true'


class TestShellSyntax:
    """What a shell will accept for each spelling.

    A dotted name is a valid environment variable, and every shell can pass one to a
    command. What no POSIX shell accepts is `export` (or a bare assignment) with a name
    which is not an identifier, hence the underscore fallback in the code.
    """

    @pytest.mark.parametrize('shell', ['bash', 'zsh', 'sh', 'dash', 'ksh'])
    def test_export_never_sets_a_dotted_name(self, shell):
        """`export exabgp.api.ack=false` leaves the variable unset.

        Worse than a hard failure: bash prints "not a valid identifier" and carries on, so a
        script keeps running with the default value. This is why the documentation passes a
        dotted name with env rather than exporting it.
        """
        if not shutil.which(shell):
            pytest.skip(f'{shell} is not installed')
        script = f"export {DOTTED}=false; {sys.executable} -c \"import os; print(os.environ.get('{DOTTED}', 'unset'))\""
        result = subprocess.run([shell, '-c', script], capture_output=True, text=True)
        assert 'false' not in result.stdout, f'{shell} exported a dotted name: {result.stdout!r}'

    @pytest.mark.parametrize('shell', ['bash', 'zsh', 'sh', 'dash', 'ksh'])
    def test_export_accepts_the_underscore_name(self, shell):
        if not shutil.which(shell):
            pytest.skip(f'{shell} is not installed')
        result = subprocess.run(
            [shell, '-c', f'export {UNDERSCORE}=false; echo reached'],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert 'reached' in result.stdout

    @pytest.mark.parametrize('shell', ['bash', 'zsh', 'sh', 'dash', 'ksh'])
    def test_env_passes_a_dotted_name(self, shell):
        if not shutil.which(shell):
            pytest.skip(f'{shell} is not installed')
        script = f"env '{DOTTED}=false' {sys.executable} -c \"import os; print(os.environ['{DOTTED}'])\""
        result = subprocess.run([shell, '-c', script], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
        assert result.stdout.strip() == 'false'

    def test_env_form_reaches_exabgp(self):
        """The form the documentation uses: env 'exabgp.api.ack=false' exabgp ..."""
        if not shutil.which('sh'):
            pytest.skip('sh is not installed')
        result = subprocess.run(
            ['sh', '-c', f"env '{DOTTED}=false' exabgp_log_enable=false {EXABGP} env -e"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert f'{DOTTED}=false' in result.stdout
