# encoding: utf-8
"""
exabgp.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import os
import sys
import syslog

from exabgp.version import version
# import before the fork to improve copy on write memory savings
from exabgp.structure.supervisor import Supervisor

import string

def is_hex (s):
	return all(c in string.hexdigits for c in s)

def __exit(memory,code):
	if memory:
		from exabgp.memory import objgraph
		print "memory utilisation"
		print
		print objgraph.show_most_common_types(limit=20)
		print
		print
		print "generating memory utilisation graph"
		print
		obj = objgraph.by_type('Supervisor')
		objgraph.show_backrefs([obj], max_depth=10)
	sys.exit(code)


def help (comment=''):
	sys.stdout.write('usage:\n exabgp [options] <bgp configuration file1> <more optional configuration files>\n')
	sys.stdout.write('\n')
	sys.stdout.write('  -h, --help      : this help\n')
	sys.stdout.write('  -c, --conf      : configuration folder\n')
	sys.stdout.write('  -e, --env       : configuration file with environment value (ini format)\n')
	sys.stdout.write(' -fi, --full-ini  : display the configuration using the ini format\n')
	sys.stdout.write(' -fe, --full-env  : display the configuration using the env format\n')
	sys.stdout.write(' -di, --diff-ini  : display non-default configurations values using the ini format\n')
	sys.stdout.write(' -de, --diff-env  : display non-default configurations values using the env format\n')
	sys.stdout.write('  -d, --debug     : turn on all subsystems debugging\n'
	                 '                    shortcut for exabgp.log.all=true exabgp.log.level=DEBUG\n'
	                 '                    one of : EMERG,ALERT,CRITICAL,ERROR,WARNING,NOTICE,INFO,DEBUG\n')
	sys.stdout.write('  -p, --pdb       : start the python debugger on serious logging and on SIGTERM\n'
	                 '                    shortcut for exabgp.pdb.enable=true\n')
	sys.stdout.write('  -m, --memory    : display memory usage information on exit\n')
	sys.stdout.write('  -t, --test      : perform a configuration validity check only\n')
	sys.stdout.write(' --decode <route> : decode a the raw route packet in hexadecimal string')
	sys.stdout.write(' --profile <file> : enable profiling\n'
	                 '                    shortcut for exabgp.profile.enable=true exabgp.profle=file=<file>\n')

	sys.stdout.write('\n')
	sys.stdout.write('ExaBGP will automatically look for its configuration file (in windows ini format)\n')
	sys.stdout.write(' - in the etc/exabgp folder located within the extracted tar.gz \n')
	sys.stdout.write(' - in /etc/exabgp/exabgp.env\n')
	sys.stdout.write('\n')
	sys.stdout.write('Individual configuration options can be set using environment variables, such as :\n')
	sys.stdout.write('   > env exabgp.daemon.daemonize=true ./sbin/exabgp\n')
	sys.stdout.write('or > env exabgp.daemon.daemonize=true ./sbin/exabgp\n')
	sys.stdout.write('or > export exabgp.daemon.daemonize=true; ./sbin/exabgp\n')
	sys.stdout.write('\n')
	sys.stdout.write('Multiple environment values can be set\n')
	sys.stdout.write('and the order of preference is :\n')
	sys.stdout.write(' - 1 : command line environment value using dot separated notation\n')
	sys.stdout.write(' - 2 : exported value from the shell using dot separated notation\n')
	sys.stdout.write(' - 3 : command line environment value using underscore separated notation\n')
	sys.stdout.write(' - 4 : exported value from the shell using underscore separated notation\n')
	sys.stdout.write(' - 5 : the value in the ini configuration file\n')
	sys.stdout.write(' - 6 : the built-in defaults\n')
	sys.stdout.write('\n')
	sys.stdout.write('For example :\n')
	sys.stdout.write('> env exabgp.profile.enable=true \\\n')
	sys.stdout.write('      exabgp.profile.file=~/profile.log  \\\n')
	sys.stdout.write('      exabgp.log.packets=true \\\n')
	sys.stdout.write('      exabgp.log.destination=host:127.0.0.1 \\\n')
	sys.stdout.write('      exabgp.daemon.user=wheel \\\n')
	sys.stdout.write('      exabgp.daemon.daemonize=true \\\n')
	sys.stdout.write('      exabgp.daemon.pid=/var/run/exabpg.pid \\\n')
	sys.stdout.write('   ./bin/exabgp ./etc/bgp/configuration.txt\n')
	sys.stdout.write('\n')
	sys.stdout.write('Valid configuration options are :\n')
	sys.stdout.write('\n')

	from exabgp.structure.environment import environment

	for line in environment.default():
			sys.stdout.write(' - %s\n' % line)
	sys.stdout.write('\n')
	sys.stdout.write(comment)
	sys.stdout.write('\n')

def main ():
	main = int(sys.version[0])
	secondary = int(sys.version[2])

	if main != 2 or secondary < 5:
		sys.exit('This program can not work (is not tested) with your python version (< 2.5 or >= 3.0)')

	next = ''
	arguments = {
		'decode' : '',
		'folder' : '',
		'file' : [],
		'env' : 'exabgp.env',
	}

	parse_error = ''

	for arg in sys.argv[1:]:
		if next:
			if next == 'decode':
				if is_hex(arg):
					arguments[next] += arg
					continue
				next = ''
			else:
				arguments[next] = arg
				next = ''
				continue
		if arg in ['-c','--conf']:
			next = 'folder'
			continue
		if arg in ['-e','--env']:
			next = 'env'
			continue
		if arg in ['--profile',]:
			next = 'profile'
			continue
		if arg in ['--decode',]:
			next = 'decode'
			continue
		if arg.startswith('-'):
			continue
		arguments['file'].append(arg)
		continue

	if arguments['folder']:
		etc = os.path.realpath(os.path.normpath(arguments['folder']))
	else:
		etc = os.path.realpath(os.path.normpath(os.environ.get('ETC','etc')))
	os.environ['ETC'] = etc

	if not arguments['env'].startswith('/'):
		envfile = '%s/%s' % (etc,arguments['env'])
	else:
		envfile = arguments['env']

	from exabgp.structure.environment import environment

	environment.application = 'exabgp'
	environment.configuration = {
		'profile' : {
			'enable'        : (environment.boolean,environment.lower,'false',    'toggle profiling of the code'),
			'file'          : (environment.unquote,environment.quote,'',         'profiling result file, none means stdout, no overwriting'),
		},
		'pdb' : {
			'enable'        : (environment.boolean,environment.lower,'false',    'on program fault, start pdb the python interactive debugger'),
		},
		'daemon' : {
	#		'identifier'    : (environment.unquote,environment.nop,'ExaBGP',     'a name for the log (to diferenciate multiple instances more easily)'),
			'pid'           : (environment.unquote,environment.quote,'',         'where to save the pid if we manage it'),
			'user'          : (environment.user,environment.quote,'nobody',      'user to run as'),
			'daemonize'     : (environment.boolean,environment.lower,'false',    'should we run in the background'),
		},
		'log' : {
			'enable'        : (environment.boolean,environment.lower,'true',     'enable logging'),
			'level'         : (environment.syslog_value,environment.syslog_name,'INFO', 'log message with at least the priority SYSLOG.<level>'),
			'destination'   : (environment.unquote,environment.quote,'stdout', 'where logging should log\n' \
			                  '                                  syslog (or no setting) sends the data to the local syslog syslog\n' \
			                  '                                  host:<location> sends the data to a remote syslog server\n' \
			                  '                                  stdout sends the data to stdout\n' \
			                  '                                  stderr sends the data to stderr\n' \
			                  '                                  <filename> send the data to a file' \
			),
			'all'           : (environment.boolean,environment.lower,'false',    'report debug information for everything'),
			'configuration' : (environment.boolean,environment.lower,'false',    'report command parsing'),
			'supervisor'    : (environment.boolean,environment.lower,'true',     'report signal received, command reload'),
			'daemon'        : (environment.boolean,environment.lower,'true',     'report pid change, forking, ...'),
			'processes'     : (environment.boolean,environment.lower,'true',     'report handling of forked processes'),
			'network'       : (environment.boolean,environment.lower,'true',     'report networking information (TCP/IP, network state,...)'),
			'packets'       : (environment.boolean,environment.lower,'false',    'report BGP packets sent and received'),
			'rib'           : (environment.boolean,environment.lower,'false',    'report change in locally configured routes'),
			'message'       : (environment.boolean,environment.lower,'false',    'report changes in route announcement on config reload'),
			'timers'        : (environment.boolean,environment.lower,'false',    'report keepalives timers'),
			'routes'        : (environment.boolean,environment.lower,'false',    'report received routes'),
			'parser'        : (environment.boolean,environment.lower,'false',    'report BGP message parsing details'),
			'short'         : (environment.boolean,environment.lower,'false',    'use short log format (not prepended with time,level,pid and source)'),
		},
		'tcp' : {
			'timeout' : (environment.integer,environment.nop,'1',  'time we will wait on select (can help with unstable BGP multihop)\n'
			                                                       '%sVERY dangerous use only if you understand BGP very well.' % (' '* 34)),
			'once': (environment.boolean,environment.lower,'false','only one tcp connection attempt per peer (for debuging scripts)'),
		},
		'cache' : {
			'attributes'  :  (environment.boolean,environment.lower,'true', 'cache routes attributes (configuration and wire) for faster parsing'),
			'nexthops'    :  (environment.boolean,environment.lower,'true', 'cache routes next-hops'),
		},
		'api' : {
			'encoder'  :  (environment.api,environment.lower,'text', '(experimental) encoder to use with with external API (text or json)'),
		},
		# Here for internal use
		'internal' : {
			'name'    : (environment.nop,environment.nop,'ExaBGP', 'name'),
			'version' : (environment.nop,environment.nop,version,  'version'),
		},
		# Here for internal use
		'debug' : {
			'memory' : (environment.boolean,environment.lower,'false','command line option --memory'),
			'configuration' : (environment.boolean,environment.lower,'false','undocumented option: raise when parsing configuration errors'),
			'selfcheck' : (environment.unquote,environment.quote,'','does a self check on the configuration file'),
			'route' : (environment.unquote,environment.quote,'','decode the route using the configuration'),
		},
	}

	try:
		env = environment.setup(envfile)
	except environment.Error,e:
		print >> sys.stderr, 'configuration issue,', str(e)
		sys.exit(1)

	if arguments['decode']:
		env.log.parser = True
		env.debug.route = arguments['decode']

	if 'profile' in arguments:
		env.profile.enable = True
		env.profile.file = arguments['profile']

	if envfile and not os.path.isfile(envfile):
		comment = 'environment file missing\ngenerate it using "exabgp -fi > %s"' % envfile
	else:
		comment = ''

	for arg in sys.argv[1:]:
		if arg in ['--',]:
			break
		if arg in ['-h','--help']:
			help(comment)
			sys.exit(0)
		if arg in ['-fi','--full-ini']:
			for line in environment.iter_ini():
				print line
			sys.exit(0)
		if arg in ['-fe','--full-env']:
			print
			for line in environment.iter_env():
				print line
			sys.exit(0)
		if arg in ['-di','--diff-ini']:
			for line in environment.iter_ini(True):
				print line
			sys.exit(0)
		if arg in ['-de','--diff-env']:
			for line in environment.iter_env(True):
				print line
			sys.exit(0)
		if arg in ['--profile',]:
			env.profile.enable = True
		if arg in ['-d','--debug']:
			env.log.all = True
			env.log.level=syslog.LOG_DEBUG
		if arg in ['-p','--pdb']:
			# The following may fail on old version of python (but is required for debug.py)
			os.environ['PDB'] = 'true'
			env.debug.pdb = True
		if arg in ['-t','--test']:
			env.debug.selfcheck = True
			env.log.parser = True
		if arg in ['-m','--memory']:
			env.debug.memory = True

	if parse_error:
		from exabgp.structure.log import Logger
		logger = Logger()
		logger.error(parse_error,'configuration')
		sys.exit(1)

	configurations = []
	# check the file only once that we have parsed all the command line options and allowed them to run
	if arguments['file']:
		for f in arguments['file']:
			configurations.append(os.path.realpath(os.path.normpath(f)))
	else:
		from exabgp.structure.log import Logger
		logger = Logger()
		logger.error('no configuration file provided','configuration')
		sys.exit(1)

	for configuration in configurations:
		if not os.path.isfile(configuration):
			from exabgp.structure.log import Logger
			logger = Logger()
			logger.error('the argument passed as configuration is not a file','configuration')
			sys.exit(1)

	from exabgp.bgp.message.update.attribute.nexthop import NextHop
	NextHop.caching = env.cache.nexthops

	from exabgp.bgp.message.update.attribute.communities import Community
	Community.caching = env.cache.attributes

	if len(configurations) == 1:
		run(env,comment,configuration)

	if not (env.log.destination in ('syslog','stdout','stderr') or env.log.destination.startswith('host:')):
		from exabgp.structure.log import Logger
		logger = Logger()
		logger.error('can not log to files when running multiple configuration (as we fork)','configuration')
		sys.exit(1)

	try:
		# run each configuration in its own process
		pids = []
		for configuration in configurations:
			pid = os.fork()
			if pid == 0:
				run(env,comment,configuration,os.getpid())
			else:
				pids.append(pid)

		# If we get a ^C / SIGTERM, ignore just continue waiting for our child process
		import signal
		signal.signal(signal.SIGINT, signal.SIG_IGN)

		# wait for the forked processes
		for pid in pids:
			os.waitpid(pid,0)
	except OSError, e:
		from exabgp.structure.log import Logger
		logger = Logger()
		logger.supervisor('Can not fork, errno %d : %s' % (e.errno,e.strerror),'critical')

def run (env,comment,configuration,pid=0):
	from exabgp.structure.log import Logger
	logger = Logger()

	if comment:
		logger.info(comment,'configuration')

	if not env.profile.enable:
		Supervisor(configuration).run()
		__exit(env.debug.memory,0)

	try:
		import cProfile as profile
	except:
		import profile

	if not env.profile.file or env.profile.file == 'stdout':
		profile.run('Supervisor(configuration).run()')
		__exit(env.debug.memory,0)

	if pid:
		profile_name = "%s-pid-%d" % (env.profile.file,pid)
	else:
		profile_name = env.profile.file

	notice = ''
	if os.path.isdir(profile_name):
		notice = 'profile can not use this filename as outpout, it is not a directory (%s)' % profile_name
	if os.path.exists(profile_name):
		notice = 'profile can not use this filename as outpout, it already exists (%s)' % profile_name

	if not notice:
		logger.info('profiling ....','profile')
		profile.run('Supervisor(configuration).run()',filename=profile_name)
		__exit(env.debug.memory,0)
	else:
		logger.info("-"*len(notice),'profile')
		logger.info(notice,'profile')
		logger.info("-"*len(notice),'profile')
		Supervisor(configuration).run()
		__exit(env.debug.memory,0)


if __name__ == '__main__':
	main()
