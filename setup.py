#!/usr/bin/env python3
# encoding: utf-8
"""setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

import platform
import os
import sys
import tomllib
import setuptools

# Build metadata comes from the project, not a runtime module which requires package imports.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'pyproject.toml'), 'rb') as reader:
    version = tomllib.load(reader)['project']['version']
download_url = f'https://github.com/Exa-Networks/exabgp/archive/{version}.tar.gz'

# without this sys.path change then this does fail
# sudo -H pip install git+https://github.com/Exa-Networks/exabgp.git

sys.path.append(os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]), 'src'))


def filesOf(directory):
    return [
        os.path.join(directory, fname)
        for fname in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, fname))
    ]


data_files = [
    ('etc/exabgp/examples', filesOf('etc/exabgp')),
    ('etc/exabgp/examples/run', filesOf('etc/exabgp/run')),
]


if platform.system() != 'NetBSD':
    if sys.argv[-1] == 'systemd':
        data_files.append(('/usr/lib/systemd/system', filesOf('etc/systemd')))

if 'systemd' in sys.argv:
    if os.path.exists('/usr/lib/systemd/system'):
        data_files.append(('/usr/lib/systemd/system', filesOf('etc/systemd')))
    if os.path.exists('/lib/systemd/system'):
        data_files.append(('/lib/systemd/system', filesOf('etc/systemd')))


def compiled_modules():
    """The files mypyc compiles: [tool.exabgp.mypyc] in pyproject.toml, as qa/bin/build_mypyc does.

    A directory is every module under it, a pattern what it matches, and a package's
    __init__.py is never compiled (compiled, the package loses its __path__).
    """
    import glob
    import tomllib

    root = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(root, 'pyproject.toml'), 'rb') as reader:
        settings = tomllib.load(reader)['tool']['exabgp']['mypyc']
    patterns = settings['modules']
    excluded = {os.path.join('src', name) for name in settings.get('exclude', [])}
    files = []
    for pattern in patterns:
        full = os.path.join(root, 'src', pattern)
        if '*' in pattern:
            paths = sorted(glob.glob(full))
        elif os.path.isdir(full):
            paths = sorted(glob.glob(os.path.join(full, '**', '*.py'), recursive=True))
        else:
            paths = [full]
        for path in paths:
            name = os.path.relpath(path, root)
            if os.path.basename(path) != '__init__.py' and name not in excluded:
                files.append(name)
    return files


def extensions():
    """The whole implementation compiled with mypyc when EXABGP_MYPYC=1 (doc/user/compiled-build.md).

    Without it, the wheel is the pure Python one, and needs nothing but setuptools.
    """
    if os.environ.get('EXABGP_MYPYC', '').lower() not in ('1', 'true', 'yes'):
        return []
    from mypyc.build import mypycify

    root = os.path.dirname(os.path.abspath(__file__))
    os.environ['MYPYPATH'] = os.path.join(root, 'stubs')
    # --no-warn-unused-configs: the compiled modules need not import exabgp.vendoring, which
    # a [[tool.mypy.overrides]] section names
    options = ['--config-file', os.path.join(root, 'pyproject.toml'), '--no-warn-unused-configs']
    return mypycify([*options, *compiled_modules()], opt_level='3')


setuptools.setup(
    packages=setuptools.find_namespace_packages(where='src'),
    package_dir={'': 'src'},
    download_url=download_url,
    data_files=data_files,
    ext_modules=extensions(),
)
