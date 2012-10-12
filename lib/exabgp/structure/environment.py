# encoding: utf-8
"""
environment.py

Created by Thomas Mangin on 2011-11-29.
Copyright (c) 2011 Exa Networks. All rights reserved.
"""

# XXX: raised exception not caught
# XXX: reloading mid-program not possible
# XXX: validation for path, file, etc not correctly test (ie surely buggy)

import os
import sys
import syslog
import pwd

from exabgp.version import version

class EnvError (Exception):
	pass

class LOG:
	EMERG    = syslog.LOG_EMERG,
	ALERT    = syslog.LOG_ALERT,
	CRIT     = syslog.LOG_CRIT,
	CRITICAL = syslog.LOG_CRIT,
	ERR      = syslog.LOG_ERR,
	ERROR    = syslog.LOG_ERR,
	WARNING  = syslog.LOG_WARNING,
	NOTICE   = syslog.LOG_NOTICE,
	INFO     = syslog.LOG_INFO,
	DEBUG    = syslog.LOG_DEBUG,

syslog_name_value = {
	'EMERG'    : LOG.EMERG,
	'ALERT'    : LOG.ALERT,
	'CRIT'     : LOG.CRIT,
	'CRITICAL' : LOG.CRIT,
	'ERR'      : LOG.ERR,
	'ERROR'    : LOG.ERR,
	'WARNING'  : LOG.WARNING,
	'NOTICE'   : LOG.NOTICE,
	'INFO'     : LOG.INFO,
	'DEBUG'    : LOG.DEBUG,
}

syslog_value_name = {
	LOG.EMERG    : 'EMERG',
	LOG.ALERT    : 'ALERT',
	LOG.CRIT     : 'CRIT',
	LOG.ERR      : 'ERR',
	LOG.WARNING  : 'WARNING',
	LOG.NOTICE   : 'NOTICE',
	LOG.INFO     : 'INFO',
	LOG.DEBUG    : 'DEBUG',
}



class NoneDict (dict):
	def __getitem__ (self,name):
		return None
nonedict = NoneDict()

class value (object):
	location = os.path.normpath(sys.argv[0]) if sys.argv[0].startswith('/') else os.path.normpath(os.path.join(os.getcwd(),sys.argv[0]))

	@staticmethod
	def root (path):
		roots = value.location.split(os.sep)
		location = []
		for index in range(len(roots)-1,-1,-1):
			if roots[index] == 'lib':
				if index:
					location = roots[:index]
				break
		root = os.path.join(*location)
		paths = [
			os.path.normpath(os.path.join(os.path.join(os.sep,root,path))),
			os.path.normpath(os.path.expanduser(value.unquote(path))),
			os.path.normpath(os.path.join('/',path)),
		]
		return paths

	@staticmethod
	def integer (_):
		return int(_)

	@staticmethod
	def lowunquote (_):
		return _.strip().strip('\'"').lower()

	@staticmethod
	def unquote (_):
		 return _.strip().strip('\'"')

	@staticmethod
	def quote (_):
		 return "'%s'" % str(_)

	@staticmethod
	def nop (_):
		return _

	@staticmethod
	def boolean (_):
		return _.lower() in ('1','yes','on','enable','true')

	@staticmethod
	def methods (_):
		return _.upper().split()

	@staticmethod
	def list (_):
		return "'%s'" % ' '.join(_)

	@staticmethod
	def lower (_):
		return str(_).lower()

	@staticmethod
	def user (_):
		# XXX: incomplete
		try:
			pwd.getpwnam(_)
			# uid = answer[2]
		except KeyError:
			raise TypeError('user %s is not found on this system' % _)
		return _

	@staticmethod
	def folder(path):
		paths = self.root(path)
		options = [path for path in paths if os.path.exists(path)]
		if not options: raise TypeError('%s does not exists' % path)
		first = options[0]
		if not first: raise TypeError('%s does not exists' % first)
		return first

	@staticmethod
	def path (path):
		split = sys.argv[0].split('lib/exabgp')
		if len(split) > 1:
			prefix = os.sep.join(split[:1])
			if prefix and path.startswith(prefix):
				path = path[len(prefix):]
		home = os.path.expanduser('~')
		if path.startswith(home):
			return "'~%s'" % path[len(home):]
		return "'%s'" % path

	@staticmethod
	def conf(path):
		first = value.folder(path)
		if not os.path.isfile(first): raise TypeError('%s is not a file' % path)
		return first

	@staticmethod
	def exe (path):
		first = value.conf(path)
		if not os.access(first, os.X_OK): raise TypeError('%s is not an executable' % first)
		return first

	@staticmethod
	def syslog (path):
		path = value.unquote(path)
		if path in ('stdout','stderr'):
			return path
		if path.startswith('host:'):
			return path
		return path

	@staticmethod
	def redirector (name):
		if name == 'url' or name.startswith('icap://'):
			return name
		raise TypeError('invalid redirector protocol %s, options are url or header' % name)

	@staticmethod
	def syslog_int (log):
		if log not in syslog_name_value:
			raise TypeError('invalid log level %s' % log)
		return syslog_name_value[log]

	@staticmethod
	def syslog_value (log):
		if log not in syslog_name_value:
			raise TypeError('invalid log level %s' % log)
		return syslog_name_value[log]

	@staticmethod
	def syslog_name (log):
		if log not in syslog_value_name:
			raise TypeError('invalid log level %s' % log)
		return syslog_value_name[log]

defaults = {
	'profile' : {
		'enable'        : (value.boolean,value.lower,'false',    'toggle profiling of the code'),
		'file'          : (value.unquote,value.quote,'',         'profiling result file, none means stdout, no overwriting'),
	},
	'pdb' : {
		'enable'        : (value.boolean,value.lower,'false',    'on program fault, start pdb the python interactive debugger'),
	},
	'daemon' : {
#		'identifier'    : (value.unquote,value.nop,'ExaBGP',     'a name for the log (to diferenciate multiple instances more easily)'),
		'pid'           : (value.unquote,value.quote,'',         'where to save the pid if we manage it'),
		'user'          : (value.user,value.quote,'nobody',      'user to run as'),
		'daemonize'     : (value.boolean,value.lower,'false',    'should we run in the background'),
	},
	'log' : {
		'enable'        : (value.boolean,value.lower,'true',     'enable logging'),
		'level'         : (value.syslog_value,value.syslog_name,'INFO', 'log message with at least the priority SYSLOG.<level>'),
		'destination'   : (value.unquote,value.quote,'stdout', 'where logging should log\n' \
		                  '                                  syslog (or no setting) sends the data to the local syslog syslog\n' \
		                  '                                  host:<location> sends the data to a remote syslog server\n' \
		                  '                                  stdout sends the data to stdout\n' \
		                  '                                  stderr sends the data to stderr\n' \
		                  '                                  <filename> send the data to a file' \
		),
		'all'           : (value.boolean,value.lower,'false',    'report debug information for everything'),
		'configuration' : (value.boolean,value.lower,'false',    'report command parsing'),
		'supervisor'    : (value.boolean,value.lower,'true',     'report signal received, command reload'),
		'daemon'        : (value.boolean,value.lower,'true',     'report pid change, forking, ...'),
		'processes'     : (value.boolean,value.lower,'true',     'report handling of forked processes'),
		'network'       : (value.boolean,value.lower,'true',     'report networking information (TCP/IP, network state,...)'),
		'packets'       : (value.boolean,value.lower,'false',    'report BGP packets sent and received'),
		'rib'           : (value.boolean,value.lower,'false',    'report change in locally configured routes'),
		'message'       : (value.boolean,value.lower,'false',    'report changes in route announcement on config reload'),
		'timers'        : (value.boolean,value.lower,'false',    'report keepalives timers'),
		'routes'        : (value.boolean,value.lower,'false',    'report received routes'),
		'parser'        : (value.boolean,value.lower,'false',    'report BGP message parsing details'),
		'short'         : (value.boolean,value.lower,'false',    'use short log format (not prepended with time,level,pid and source)'),
	},
	'tcp' : {
		'timeout' : (value.integer,value.nop,'1',  'time we will wait on select (can help with unstable BGP multihop)\n'
		                                           '%sVERY dangerous use only if you understand BGP very well.' % (' '* 34)),
	},
	# Here for internal use
	'internal' : {
		'name'    : (value.nop,value.nop,'ExaBGP', 'name'),
		'version' : (value.nop,value.nop,version,  'version'),
	},
	# Here for internal use
	'debug' : {
		'memory' : (value.boolean,value.lower,'false','command line option --memory'),
		'configuration' : (value.boolean,value.lower,'false','undocumented option: raise when parsing configuration errors'),
		'selfcheck' : (value.unquote,value.quote,'','does a self check on the configuration file'),
		'route' : (value.unquote,value.quote,'','decode the route using the configuration')
	},
}

import ConfigParser

class Store (dict):
	def __getitem__ (self,key):
		return dict.__getitem__(self,key.replace('_','-'))
	def __setitem__ (self,key,value):
		return dict.__setitem__(self,key.replace('_','-'),value)
	def __getattr__ (self,key):
		return dict.__getitem__(self,key.replace('_','-'))
	def __setattr__ (self,key,value):
		return dict.__setitem__(self,key.replace('_','-'),value)


def _env (conf):
	location = os.path.join(os.sep,*os.path.join(value.location.split(os.sep)))
	while location:
		location, directory = os.path.split(location)
		if directory == 'lib':
			break

	_conf_paths = []
	if conf:
		_conf_paths.append(os.path.abspath(os.path.normpath(conf)))
	if location:
		_conf_paths.append(os.path.normpath(os.path.join(location,'etc','exabgp','exabgp.env')))
	_conf_paths.append(os.path.normpath(os.path.join('/','etc','exabgp','exabgp.env')))

	env = Store()
	ini = ConfigParser.ConfigParser()

	ini_files = [path for path in _conf_paths if os.path.exists(path)]
	if ini_files:
		ini.read(ini_files[0])

	for section in defaults:
		default = defaults[section]

		for option in default:
			convert = default[option][0]
			try:
				proxy_section = 'exabgp.%s' % section
				env_name = '%s.%s' % (proxy_section,option)
				rep_name = env_name.replace('.','_')

				if env_name in os.environ:
					conf = os.environ.get(env_name)
				elif rep_name in os.environ:
					conf = os.environ.get(rep_name)
				else:
					conf = value.unquote(ini.get(proxy_section,option,nonedict))
					# name without an = or : in the configuration and no value
					if conf == None:
						conf = default[option][2]
			except (ConfigParser.NoSectionError,ConfigParser.NoOptionError):
				conf = default[option][2]
			try:
				env.setdefault(section,Store())[option] = convert(conf)
			except TypeError:
				raise EnvError('invalid value for %s.%s : %s' % (section,option,conf))

	return _compatibility(env)


__env = None

def load (conf=None):
	global __env
	if __env:
		return __env
	if conf is None:
		raise RuntimeError('You can not have an import using load() before main() initialised it')
	__env = _env(conf)
	return __env

def default ():
	for section in sorted(defaults):
		if section in ('internal','debug'):
			continue
		for option in sorted(defaults[section]):
			values = defaults[section][option]
			default = "'%s'" % values[2] if values[1] in (value.list,value.path,value.quote,value.syslog) else values[2]
			yield 'exabgp.%s.%s %s: %s. default (%s)' % (section,option,' '*(20-len(section)-len(option)),values[3],default)

def iter_ini (diff=False):
	for section in sorted(__env):
		if section in ('internal','debug'):
			continue
		header = '\n[exabgp.%s]' % section
		for k in sorted(__env[section]):
			v = __env[section][k]
			if diff and defaults[section][k][0](defaults[section][k][2]) == v:
				continue
			if header:
				yield header
				header = ''
			yield '%s = %s' % (k,defaults[section][k][1](v))

def iter_env (diff=False):
	for section,values in __env.items():
		if section in ('internal','debug'):
			continue
		for k,v in values.items():
			if diff and defaults[section][k][0](defaults[section][k][2]) == v:
				continue
			if defaults[section][k][1] == value.quote:
				yield "exabgp.%s.%s='%s'" % (section,k,v)
				continue
			yield "exabgp.%s.%s=%s" % (section,k,defaults[section][k][1](v))


# Compatibility with 2.0.x
def _compatibility (env):
	profile = os.environ.get('PROFILE','')
	if profile:
		env.profile.enable=True
	if profile and profile.lower() not in ['1','true','yes','on','enable']:
		env.profile.file=profile

	# PDB : still compatible as a side effect of the code structure

	syslog = os.environ.get('SYSLOG','')
	if syslog != '':
		env.log.destination=syslog

	if os.environ.get('DEBUG_SUPERVISOR','').lower() in ['1','yes']:
		env.log.supervisor = True
	if os.environ.get('DEBUG_DAEMON','').lower() in ['1','yes']:
		env.log.daemon = True
	if os.environ.get('DEBUG_PROCESSES','').lower() in ['1','yes']:
		env.log.processes = True
	if os.environ.get('DEBUG_CONFIGURATION','').lower() in ['1','yes']:
		env.log.configuration = True
	if os.environ.get('DEBUG_WIRE','').lower() in ['1','yes']:
		env.log.network = True
		env.log.packets = True
	if os.environ.get('DEBUG_MESSAGE','').lower() in ['1','yes']:
		env.log.message = True
	if os.environ.get('DEBUG_RIB','').lower() in ['1','yes']:
		env.log.rib = True
	if os.environ.get('DEBUG_TIMER','').lower() in ['1','yes']:
		env.log.timers = True
	if os.environ.get('DEBUG_PARSER','').lower() in ['1','yes']:
		env.log.parser = True
	if os.environ.get('DEBUG_ROUTE','').lower() in ['1','yes']:
		env.log.routes = True
	if os.environ.get('DEBUG_ROUTES','').lower() in ['1','yes']: # DEPRECATED even in 2.0.x
		env.log.routes = True
	if os.environ.get('DEBUG_ALL','').lower() in ['1','yes']:
		env.log.all = True
	if os.environ.get('DEBUG_CORE','').lower() in ['1','yes']:
		env.log.supervisor = True
		env.log.daemon = True
		env.log.processes = True
		env.log.message = True
		env.log.timer = True
		env.log.routes = True
		env.log.parser = False

	pid = os.environ.get('PID','')
	if pid:
		env.daemon.pid = pid

	import pwd

	try:
		me = pwd.getpwuid(os.getuid()).pw_name
		user = os.environ.get('USER','')
		if user and user != 'root' and user != me and env.daemon.user == 'nobody':
			env.daemon.user = user
	except KeyError:
		pass

	daemon = os.environ.get('DAEMONIZE','').lower() in ['1','yes']
	if daemon:
		env.daemon.daemonize = True
		env.log.enable = False

	return env
