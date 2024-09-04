#!/usr/bin/env python3
# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

import importlib
import platform
import os
import sys
import setuptools
from distutils.core import setup

# from setuptools.config import read_configuration
# conf_dict = read_configuration('./setup.cfg', find_others=True)

sys.path.append(os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]), 'lib/exabgp'))
exabgp_version = importlib.import_module('version')


def filesOf(directory):
    files = []
    for l, d, fs in os.walk(directory):
        if not d:
            for f in fs:
                files.append(os.path.join(l, f))
    return files


data_files = [
    ('etc/exabgp/examples', filesOf('etc/exabgp')),
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
    download_url='https://github.com/Exa-Networks/exabgp/archive/%s.tar.gz' % exabgp_version.version.split('-')[0],
    data_files=data_files,
)
