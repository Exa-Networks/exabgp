# encoding: utf-8
"""
environment.py

Created by Thomas Mangin on 2011-11-29.
Copyright (c) 2011-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# XXX: raised exception not caught
# XXX: reloading mid-program not possible
# XXX: validation for path, file, etc not correctly test (ie surely buggy)


import os
import sys
import pwd
import syslog

from exabgp.protocol.ip import IP
from exabgp.util.ip import isip


# ===================================================================== NoneDict
#


class NoneDict(dict):
    def __getitem__(self, name):
        return None


nonedict = NoneDict()


# ================================================================== environment
# XXX: FIXME: Upper case for class !


class environment(object):
    # class returned on issues
    class Error(Exception):
        pass

    application = 'unset'

    # the configuration to be set by the program
    configuration = {}

    # the final parsed settings
    _settings = None

    location = (
        os.path.normpath(sys.argv[0])
        if sys.argv[0].startswith('/')
        else os.path.normpath(os.path.join(os.getcwd(), sys.argv[0]))
    )
    log_levels = ['EMERG', 'ALERT', 'CRIT', 'CRITICAL', 'ERR', 'ERROR', 'WARNING', 'NOTICE', 'INFO', 'DEBUG']

    @staticmethod
    def setup(conf):
        if environment._settings:
            # nosetest is performing the setup multiple times, so we can not raise anymore
            # raise RuntimeError('You already initialised the environment')
            return environment._settings
        environment._settings = _env(conf)
        return environment._settings

    @staticmethod
    def settings():
        if not environment._settings:
            raise RuntimeError('You can not have an import using settings() before main() initialised environment')
        return environment._settings

    @staticmethod
    def root(path):
        roots = environment.location.split(os.sep)
        location = []
        for index in range(len(roots) - 1, -1, -1):
            if roots[index] == 'lib':
                if index:
                    location = roots[:index]
                break
        root = os.path.join(*location)
        paths = [
            os.path.normpath(os.path.join(os.path.join(os.sep, root, path))),
            os.path.normpath(os.path.expanduser(environment.unquote(path))),
            os.path.normpath(os.path.join('/', path)),
        ]
        return paths

    @staticmethod
    def integer(_):
        return int(_)

    @staticmethod
    def real(_):
        return float(_)

    @staticmethod
    def lowunquote(_):
        return _.strip().strip('\'"').lower()

    @staticmethod
    def unquote(_):
        return _.strip().strip('\'"')

    @staticmethod
    def quote(_):
        return "'%s'" % str(_)

    @staticmethod
    def quote_list(_):
        return "'%s'" % ' '.join([str(x) for x in _])

    @staticmethod
    def nop(_):
        return _

    @staticmethod
    def boolean(_):
        return _.lower() in ('1', 'yes', 'on', 'enable', 'true')

    @staticmethod
    def api(_):
        encoder = _.lower()
        if encoder not in ('text', 'json'):
            raise TypeError('invalid encoder')
        return encoder

    @staticmethod
    def methods(_):
        return _.upper().split()

    @staticmethod
    def list(_):
        return "'%s'" % ' '.join(_)

    @staticmethod
    def lower(_):
        return str(_).lower()

    @staticmethod
    def ip(_):
        if isip(_):
            return _
        raise TypeError('ip %s is invalid' % _)

    @staticmethod
    def ip_list(_):
        ips = []
        for ip in _.split(' '):
            if not ip:
                continue
            elif isip(ip):
                ips.append(IP.create(ip))
            else:
                raise TypeError('ip %s is invalid' % ip)
        return ips

    @staticmethod
    def user(_):
        # XXX: incomplete
        try:
            pwd.getpwnam(_)
            # uid = answer[2]
        except KeyError:
            raise TypeError('user %s is not found on this system' % _)
        return _

    @staticmethod
    def folder(path):
        paths = environment.root(path)
        options = [p for p in paths if os.path.exists(path)]
        if not options:
            raise TypeError('%s does not exists' % path)
        first = options[0]
        if not first:
            raise TypeError('%s does not exists' % first)
        return first

    @staticmethod
    def path(path):
        split = sys.argv[0].split('lib/exabgp')
        if len(split) > 1:
            prefix = os.sep.join(split[:1])
            if prefix and path.startswith(prefix):
                path = path[len(prefix) :]
        home = os.path.expanduser('~')
        if path.startswith(home):
            return "'~%s'" % path[len(home) :]
        return "'%s'" % path

    @staticmethod
    def conf(path):
        first = environment.folder(path)
        if not os.path.isfile(first):
            raise TypeError('%s is not a file' % path)
        return first

    @staticmethod
    def exe(path):
        first = environment.conf(path)
        if not os.access(first, os.X_OK):
            raise TypeError('%s is not an executable' % first)
        return first

    @staticmethod
    def syslog(path):
        path = environment.unquote(path)
        if path in ('stdout', 'stderr'):
            return path
        if path.startswith('host:'):
            return path
        return path

    @staticmethod
    def redirector(name):
        if name == 'url' or name.startswith('icap://'):
            return name
        raise TypeError('invalid redirector protocol %s, options are url or header' % name)

    @staticmethod
    def syslog_value(log):
        if log not in environment.log_levels:
            if log == 'CRITICAL':
                log = 'CRIT'
            if log == 'ERROR':
                log = 'ERR'
            raise TypeError('invalid log level %s' % log)
        return getattr(syslog, 'LOG_%s' % log)

    @staticmethod
    def syslog_name(log):
        for name in environment.log_levels:
            if name == 'CRITICAL':
                name = 'CRIT'
            if name == 'ERROR':
                name = 'ERR'
            if getattr(syslog, 'LOG_%s' % name) == log:
                return name
        raise TypeError('invalid log level %s' % log)

    @staticmethod
    def umask_read(_):
        return int(_, 8)

    @staticmethod
    def umask_write(_):
        return "'%s'" % (oct(_))

    @staticmethod
    def default():
        for section in sorted(environment.configuration):
            if section in ('internal', 'debug'):
                continue
            for option in sorted(environment.configuration[section]):
                values = environment.configuration[section][option]
                default = (
                    "'%s'" % values['value']
                    if values['write'] in (environment.list, environment.path, environment.quote, environment.syslog)
                    else values['value']
                )
                yield '%s.%s.%s %s: %s. default (%s)' % (
                    environment.application,
                    section,
                    option,
                    ' ' * (20 - len(section) - len(option)),
                    values['help'],
                    default,
                )

    @staticmethod
    def iter_ini(diff=False):
        for section in sorted(environment._settings):
            if section in ('internal', 'debug'):
                continue
            header = '\n[%s.%s]' % (environment.application, section)
            for k in sorted(environment._settings[section]):
                v = environment._settings[section][k]
                if (
                    diff
                    and environment.configuration[section][k]['read'](environment.configuration[section][k]['value'])
                    == v
                ):
                    continue
                if header:
                    yield header
                    header = ''
                yield '%s = %s' % (k, environment.configuration[section][k]['write'](v))

    @staticmethod
    def iter_env(diff=False):
        for section, values in environment._settings.items():
            if section in ('internal', 'debug'):
                continue
            for k, v in values.items():
                if (
                    diff
                    and environment.configuration[section][k]['read'](environment.configuration[section][k]['value'])
                    == v
                ):
                    continue
                if environment.configuration[section][k]['write'] == environment.quote:
                    yield "%s.%s.%s='%s'" % (environment.application, section, k, v)
                    continue
                yield "%s.%s.%s=%s" % (
                    environment.application,
                    section,
                    k,
                    environment.configuration[section][k]['write'](v),
                )


# ========================================================================= _env
#

from exabgp.vendoring.six.moves import configparser as ConfigParser
from exabgp.util.hashtable import HashTable


def _env(conf):
    here = os.path.join(os.sep, os.path.join(*environment.location.split(os.sep)))

    location, directory = os.path.split(here)
    while directory:
        if directory == 'lib':
            location = os.path.join(location, 'lib')
            break
        location, directory = os.path.split(location)
    # we did not break - ie, we did not find the location in the normal path.
    else:
        # let's try to see if we are running from the QA folder (for unittesting)
        location, directory = os.path.split(here)
        while directory:
            if directory == 'dev':
                location = os.path.join(location, 'lib')
                break
            location, directory = os.path.split(location)
        else:
            # oh ! bad, let set the path to something ...
            location = '/lib'

    _conf_paths = []
    if conf:
        _conf_paths.append(os.path.abspath(os.path.normpath(conf)))
    if location:
        _conf_paths.append(
            os.path.normpath(os.path.join(location, 'etc', environment.application, '%s.env' % environment.application))
        )
    _conf_paths.append(
        os.path.normpath(os.path.join('/', 'etc', environment.application, '%s.env' % environment.application))
    )

    env = HashTable()
    ini = ConfigParser.ConfigParser()

    ini_files = [path for path in _conf_paths if os.path.exists(path)]
    if ini_files:
        ini.read(ini_files[0])

    for section in environment.configuration:
        default = environment.configuration[section]

        for option in default:
            convert = default[option]['read']
            try:
                proxy_section = '%s.%s' % (environment.application, section)
                env_name = '%s.%s' % (proxy_section, option)
                rep_name = env_name.replace('.', '_')

                if env_name in os.environ:
                    conf = os.environ.get(env_name)
                elif rep_name in os.environ:
                    conf = os.environ.get(rep_name)
                else:
                    if sys.version_info[0] < 3:
                        conf = environment.unquote(ini.get(proxy_section, option, nonedict))
                    else:
                        conf = environment.unquote(ini.get(proxy_section, option, vars=nonedict))
                    # name without an = or : in the configuration and no value
                    if conf is None:
                        conf = default[option]['value']
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
                conf = default[option]['value']
            try:
                env.setdefault(section, HashTable())[option] = convert(conf)
            except TypeError:
                raise environment.Error('invalid value for %s.%s : %s' % (section, option, conf))

    return env
