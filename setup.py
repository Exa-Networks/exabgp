#!/usr/bin/env python3
# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

import platform
import os
import sys
import setuptools
from distutils.core import setup


# less magic for readers than adding src/exabgp to sys.path and using importlib

get_version = os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]), 'src/exabgp/version.py')
version = os.popen(f'{sys.executable} {get_version}').read()

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


setuptools.setup(
    download_url='https://github.com/Exa-Networks/exabgp/archive/%s.tar.gz' % version.split('-')[0],
    data_files=data_files,
)
