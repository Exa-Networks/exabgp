# encoding: utf-8
"""
environment.py

Created by Thomas Mangin on 2011-11-29.
Copyright (c) 2011-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os

import configparser as ConfigParser

from exabgp.environment import base
from exabgp.environment import parsing
from exabgp.environment.base import ENVFILE
from exabgp.environment.hashtable import HashTable
from exabgp.environment.hashtable import GlobalHashTable


class NoneDict(dict):
    def __getitem__(self, name):
        return None


nonedict = NoneDict()


class Env(object):
    _setup = False

    # the configuration to be set by the program
    definition = {}

    # one copy of the global configuration
    _env = GlobalHashTable()

    @classmethod
    def default(cls):
        for section in sorted(cls.definition):
            if section in ('internal', 'debug'):
                continue
            for option in sorted(cls.definition[section]):
                values = cls.definition[section][option]
                default = (
                    "'%s'" % values['value']
                    if values['write'] in (parsing.list, parsing.path, parsing.quote, parsing.syslog_name)
                    else values['value']
                )
                yield '%s.%s.%s %s %s. default (%s)' % (
                    base.APPLICATION,
                    section,
                    option,
                    ' ' * (18 - len(section) - len(option)),
                    values['help'],
                    default,
                )

    @classmethod
    def iter_ini(cls, diff=False):
        for section in sorted(cls._env):
            if section in ('internal', 'debug'):
                continue
            header = '\n[%s.%s]' % (base.APPLICATION, section)
            for k in sorted(cls._env[section]):
                v = cls._env[section][k]
                func = cls.definition[section][k]['read']
                value = cls.definition[section][k]['value']
                if diff and func(value) == v:
                    continue
                if header:
                    yield header
                    header = ''
                yield '%s = %s' % (k, cls.definition[section][k]['write'](v))

    @classmethod
    def iter_env(cls, diff=False):
        for section, values in cls._env.items():
            if section in ('internal', 'debug'):
                continue
            for k, v in values.items():
                func = cls.definition[section][k]['read']
                value = cls.definition[section][k]['value']
                if diff and func(value) == v:
                    continue
                if cls.definition[section][k]['write'] == parsing.quote:
                    yield "%s.%s.%s='%s'" % (base.APPLICATION, section, k, v)
                    continue
                yield '%s.%s.%s=%s' % (
                    base.APPLICATION,
                    section,
                    k,
                    cls.definition[section][k]['write'](v),
                )

    @classmethod
    def setup(cls, configuration):
        if cls._setup:
            return {}
        cls._setup = True
        cls.definition = configuration

        ini = ConfigParser.ConfigParser()

        _conf_paths = [
            ENVFILE,
        ]

        ini_files = [path for path in _conf_paths if os.path.exists(path)]
        if ini_files:
            ini.read(ini_files[0])

        for section in cls.definition:
            default = cls.definition[section]

            for option in default:
                convert = default[option]['read']
                try:
                    proxy_section = '%s.%s' % (base.APPLICATION, section)
                    env_name = '%s.%s' % (proxy_section, option)
                    rep_name = env_name.replace('.', '_')

                    if env_name in os.environ:
                        conf = os.environ.get(env_name)
                    elif rep_name in os.environ:
                        conf = os.environ.get(rep_name)
                    else:
                        conf = parsing.unquote(ini.get(proxy_section, option, vars=nonedict))
                        # name without an = or : in the configuration and no value
                        if conf is None:
                            conf = default[option]['value']
                except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                    conf = default[option]['value']
                try:
                    cls._env.setdefault(section, HashTable())[option] = convert(conf)
                except TypeError:
                    raise ValueError('invalid value for %s.%s : %s' % (section, option, conf))

    @classmethod
    def settings(cls):
        return cls._env
