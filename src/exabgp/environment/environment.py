"""environment.py

Created by Thomas Mangin on 2011-11-29.
Copyright (c) 2011-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import os
from typing import Any, ClassVar, Dict, Iterator, List, Optional

import configparser as ConfigParser

from exabgp.environment import base
from exabgp.environment import parsing
from exabgp.environment.base import ENVFILE
from exabgp.environment.hashtable import HashTable
from exabgp.environment.hashtable import GlobalHashTable


class NoneDict(dict):
    def __getitem__(self, name: str) -> None:
        return None


nonedict: NoneDict = NoneDict()


class Env:
    _setup: ClassVar[bool] = False

    # the configuration to be set by the program
    definition: ClassVar[Dict[str, Dict[str, Any]]] = {}

    # one copy of the global configuration
    _env: ClassVar[GlobalHashTable] = GlobalHashTable()

    @classmethod
    def default(cls) -> Iterator[str]:
        for section in sorted(cls.definition):
            if section in ('internal', 'debug'):
                continue
            for option in sorted(cls.definition[section]):
                values: Dict[str, Any] = cls.definition[section][option]
                default: Any = (
                    "'{}'".format(values['value'])
                    if values['write'] in (parsing.list, parsing.path, parsing.quote, parsing.syslog_name)
                    else values['value']
                )
                yield f'{base.APPLICATION}.{section}.{option} {" " * (18 - len(section) - len(option))} {values["help"]}. default ({default})'

    @classmethod
    def iter_ini(cls, diff: bool = False) -> Iterator[str]:
        for section in sorted(cls._env):
            if section in ('internal', 'debug'):
                continue
            header: str = f'\n[{base.APPLICATION}.{section}]'
            for k in sorted(cls._env[section]):
                v: Any = cls._env[section][k]
                func: Any = cls.definition[section][k]['read']
                value: Any = cls.definition[section][k]['value']
                if diff and func(value) == v:
                    continue
                if header:
                    yield header
                    header = ''
                yield f'{k} = {cls.definition[section][k]["write"](v)}'

    @classmethod
    def iter_env(cls, diff: bool = False) -> Iterator[str]:
        for section, values in cls._env.items():
            if section in ('internal', 'debug'):
                continue
            for k, v in values.items():
                func: Any = cls.definition[section][k]['read']
                value: Any = cls.definition[section][k]['value']
                if diff and func(value) == v:
                    continue
                if cls.definition[section][k]['write'] == parsing.quote:
                    yield f"{base.APPLICATION}.{section}.{k}='{v}'"
                    continue
                yield f'{base.APPLICATION}.{section}.{k}={cls.definition[section][k]["write"](v)}'

    @classmethod
    def setup(cls, configuration: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if cls._setup:
            return {}
        cls._setup = True
        cls.definition = configuration

        ini: ConfigParser.ConfigParser = ConfigParser.ConfigParser()

        _conf_paths: List[str] = [
            ENVFILE,
        ]

        ini_files: List[str] = [path for path in _conf_paths if os.path.exists(path)]
        if ini_files:
            ini.read(ini_files[0])

        for section in cls.definition:
            default: Dict[str, Any] = cls.definition[section]

            for option in default:
                convert: Any = default[option]['read']
                try:
                    proxy_section: str = f'{base.APPLICATION}.{section}'
                    env_name: str = f'{proxy_section}.{option}'
                    rep_name: str = env_name.replace('.', '_')

                    conf: Optional[str]
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
                    raise ValueError(f'invalid value for {section}.{option} : {conf}') from None

        # Backward compatibility and alias handling
        if 'tcp' in cls._env:
            # Handle exabgp_tcp_connections as an alias for exabgp_tcp_attempts
            connections_env: Optional[str] = os.environ.get('exabgp.tcp.connections') or os.environ.get(
                'exabgp_tcp_connections'
            )
            if connections_env:
                cls._env['tcp']['attempts'] = int(connections_env)

            # Backward compatibility: convert tcp.once to tcp.attempts if tcp.attempts not explicitly set
            once_env: Optional[str] = os.environ.get('exabgp.tcp.once') or os.environ.get('exabgp_tcp_once')
            attempts_env: Optional[str] = os.environ.get('exabgp.tcp.attempts') or os.environ.get('exabgp_tcp_attempts')

            # Only apply backward compatibility if tcp.attempts wasn't explicitly set
            if once_env and not attempts_env and not connections_env:
                if cls._env['tcp']['once']:
                    cls._env['tcp']['attempts'] = 1
                else:
                    cls._env['tcp']['attempts'] = 0
        return None

    @classmethod
    def settings(cls) -> GlobalHashTable:
        return cls._env

    @classmethod
    def __getattr__(cls, name: str) -> HashTable:
        # Allow attribute-style access to configuration sections (e.g., Env.log, Env.debug)
        # Returns HashTable which supports dynamic attribute access
        from typing import cast

        return cast(HashTable, cls._env[name])
