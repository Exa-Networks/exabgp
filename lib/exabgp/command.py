# encoding: utf-8
"""
command.py

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

class CommandError (Exception):
	pass

syslog_name_value = {
	'LOG_EMERG'    : syslog.LOG_EMERG,
	'LOG_ALERT'    : syslog.LOG_ALERT,
	'LOG_CRIT'     : syslog.LOG_CRIT,
	'LOG_ERR'      : syslog.LOG_ERR,
	'LOG_WARNING'  : syslog.LOG_WARNING,
	'LOG_NOTICE'   : syslog.LOG_NOTICE,
	'LOG_INFO'     : syslog.LOG_INFO,
	'LOG_DEBUG'    : syslog.LOG_DEBUG,
}

syslog_value_name = {
	syslog.LOG_EMERG    : 'LOG_EMERG',
	syslog.LOG_ALERT    : 'LOG_ALERT',
	syslog.LOG_CRIT     : 'LOG_CRIT',
	syslog.LOG_ERR      : 'LOG_ERR',
	syslog.LOG_WARNING  : 'LOG_WARNING',
	syslog.LOG_NOTICE   : 'LOG_NOTICE',
	syslog.LOG_INFO     : 'LOG_INFO',
	syslog.LOG_DEBUG    : 'LOG_DEBUG',
}



class NoneDict (dict):
	def __getitem__ (self,name):
		return None
nonedict = NoneDict()

class value (object):
	location = os.path.normpath(sys.argv[0]) if sys.argv[0].startswith('/') else os.path.normpath(os.path.join(os.getcwd(),sys.argv[0]))

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
		path = os.path.expanduser(value.unquote(path))
		paths = [
			os.path.normpath(os.path.join(os.path.join(os.sep,*os.path.join(value.location.split(os.sep)[:-3])),path)),
			os.path.normpath(os.path.join('/','etc','exabgp','exabgp.conf',path)),
			os.path.normpath(path)
		]
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
	def resolver(path):
		paths = [
			os.path.normpath(path),
			os.path.normpath(os.path.join(os.path.join(os.sep,*os.path.join(value.location.split(os.sep)[:-3])),path)),
			os.path.normpath(os.path.join(os.path.join(os.sep,*os.path.join(value.location.split(os.sep)[:-3])),'etc','exabgp','dns','resolv.conf')),
			os.path.normpath(os.path.join('/','etc','exabgp','resolv.conf',path)),
		]
		for resolver in paths:
			if os.path.exists(resolver):
				with open(resolver) as r:
					if 'nameserver' in (line.strip().split(None,1)[0].lower() for line in r.readlines()):
						return resolver
		raise TypeError('resolv.conf can not be found')

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
		'file'          : (value.unquote,value.quote,'',         'file where profiling information is saved (none means stdout). ExaBGP does not overwrite existing files'),
	},
	'pdb' : {
		'enable'        : (value.boolean,value.lower,'false',    'on program fault, start pdb the python interactive debugger'),
		'file'          : (value.unquote,value.quote,'',         'file where profiling information is saved (none means stdout). ExaBGP does not overwrite existing files'),
	},
	'daemon' : {
#		'identifier'    : (value.unquote,value.nop,'ExaBGP',     'a name for the log (to diferenciate multiple instances more easily)'),
		'pid'           : (value.unquote,value.quote,'',         'where to save the pid if we manage it'),
		'user'          : (value.user,value.quote,'nobody',      'user to run as'),
		'daemonize'     : (value.boolean,value.lower,'false',    'should we run in the background'),
	},
	'log' : {
		'enable'        : (value.boolean,value.lower,'true',     'enable logging'),
		'level'         : (value.syslog_value,value.syslog_name,'LOG_INFO', 'log message with at least the priority SYSLOG.<level>'),
		'destination'   : (value.unquote,value.quote,'stdout',   'where logging should log'),
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
	},
	'bgp' : {
		'minimal'       : (value.boolean,value.lower,'false',    'when negociating multiprotocol, try to announce as few AFI/SAFI pair as possible'),
	},
	# Here for internal use
	'internal' : {
		'name'    : (value.nop,value.nop,'ExaBGP', 'name'),
		'version' : (value.nop,value.nop,version,  'version'),
	},
	# Here for internal use
	'debug' : {
		'memory' : (value.boolean,value.lower,'false','command line option --memory'),
		'configuration' : (value.boolean,value.lower,'false','undocumented option: raise when parsing configuration errors')
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


def _command (conf):
	location = os.path.join(os.sep,*os.path.join(value.location.split(os.sep)))
	while location:
		location, directory = os.path.split(location)
		if directory == 'lib':
			break

	_conf_paths = []
	if conf:
		_conf_paths.append(os.path.abspath(os.path.normpath(conf)))
	if location:
		_conf_paths.append(os.path.normpath(os.path.join(location,'etc','exabgp','exabgp.conf')))
	_conf_paths.append(os.path.normpath(os.path.join('/','etc','exabgp','exabgp.conf')))

	command = Store()
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
					# raise and set the default
					conf = value.unquote(ini.get(proxy_section,option,nonedict))
					# name without an = or : in the configuration and no value
					if conf == None:
						conf = default[option][2]
			except (ConfigParser.NoSectionError,ConfigParser.NoOptionError):
				conf = default[option][2]
			try:
				command.setdefault(section,Store())[option] = convert(conf)
			except TypeError:
				raise CommandError('invalid value for %s.%s : %s' % (section,option,conf))

	return command

__command = None

def load (conf=None):
	global __command
	if __command:
		return __command
	if conf is None:
		raise RuntimeError('You can not have an import using load() before main() initialised it')
	__command = _command(conf)
	return __command

def default ():
	for section in sorted(defaults):
		if section in ('internal','debug'):
			continue
		for option in sorted(defaults[section]):
			values = defaults[section][option]
			default = "'%s'" % values[2] if values[1] in (value.list,value.path,value.quote,value.syslog) else values[2]
			yield 'exabgp.%s.%s %s: %s. default (%s)' % (section,option,' '*(20-len(section)-len(option)),values[3],default)

def ini (diff=False):
	for section in sorted(__command):
		if section in ('internal','debug'):
			continue
		header = '\n[exabgp.%s]' % section
		for k in sorted(__command[section]):
			v = __command[section][k]
			if diff and defaults[section][k][0](defaults[section][k][2]) == v:
				continue
			if header:
				print header
				header = ''
			print '%s = %s' % (k,defaults[section][k][1](v))

def env (diff=False):
	print
	for section,values in __command.items():
		if section in ('internal','debug'):
			continue
		for k,v in values.items():
			if diff and defaults[section][k][0](defaults[section][k][2]) == v:
				continue
			if defaults[section][k][1] == value.quote:
				print "exabgp.%s.%s='%s'" % (section,k,v)
				continue
			print "exabgp.%s.%s=%s" % (section,k,defaults[section][k][1](v))
