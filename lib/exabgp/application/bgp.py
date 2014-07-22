# encoding: utf-8
"""
exabgp.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import os
import sys
import string
import syslog

from exabgp.version import version
# import before the fork to improve copy on write memory savings
from exabgp.reactor import Reactor

from exabgp.dep import docopt
from exabgp.dep import lsprofcalltree

usage = """\
The BGP swiss army knife of networking

usage: exabgp [--help] [--version] [--folder FOLDER] [--env ENV]
              [[--full-ini | --diff-ini | --full-env | --diff-env] |
              [--fi | --di | --fe | --de]]
              [--debug] [--once] [--pdb] [--memory] [--profile PROFILE] [--test]
              [--decode HEX_MESSAGE]...
              [<configuration>...]

positional arguments:
  configuration         peer and route configuration file

optional arguments:
  --help, -h            exabgp manual page
  --version, -v         shows ExaBGP version
  --folder FOLDER, -f FOLDER
                        configuration folder
  --env ENV, -e ENV     environment configuration file
  --full-ini            display the configuration using the ini format
  --fi                  (shorthand for above)
  --diff-ini            display non-default configurations values using the ini
                        format
  --di                  (shorthand for above)
  --full-env            display the configuration using the env format
  --fe                  (shorthand for above)
  --diff-env            display non-default configurations values using the env
                        format
  --de                  (shorthand for above)

debugging:
  --debug, -d           start the python debugger on serious logging and on
                        SIGTERM (shortcut for exabgp.log.all=true
                        exabgp.log.level=DEBUG)
  --once, -1            only perform one attempt to connect to peers (used for
                        debugging)
  --pdb, -p             fire the debugger on critical logging, SIGTERM, and
                        exceptions (shortcut for exabgp.pdb.enable=true)
  --memory, -s          display memory usage information on exit
  --profile PROFILE     enable profiling (shortcut for
                        exabgp.profile.enable=true exabgp.profile.file=PROFILE)
  --test, -t            perform a configuration validity check only
  --decode HEX_MESSAGE, -x HEX_MESSAGE
                        decode a raw route packet in hexadecimal string


ExaBGP will automatically look for its configuration file (in windows ini
format):
 * in the etc/exabgp folder located within the extracted tar.gz
 * in /etc/exabgp/exabgp.env

Individual configuration options can be set using environment variables, such
as:
 > env exabgp.daemon.daemonize=true ./sbin/exabgp
or:
 > env exabgp.daemon.daemonize=true ./sbin/exabgp
or:
 > export exabgp.daemon.daemonize=true; ./sbin/exabgp

Multiple environment values can be set, the order of preference being:
 1) command line environment value using dot separated notation
 2) exported value from the shell using dot separated notation
 3) command line environment value using underscore separated notation
 4) exported value from the shell using underscore separated notation
 5) the value in the ini configuration file
 6) the built-in defaults

For example :
 > env exabgp.profile.enable=true \\
      exabgp.profile.file=~/profile.log  \\
      exabgp.log.packets=true \\
      exabgp.log.destination=host:127.0.0.1 \\
      exabgp.daemon.user=wheel \\
      exabgp.daemon.daemonize=true \\
      exabgp.daemon.pid=/var/run/exabpg.pid \\
 > ./bin/exabgp ./etc/bgp/configuration.txt

The program configuration can be controlled using signals:
 * SIGLARM : restart ExaBGP
 * SIGUSR1 : reload the configuration
 * SIGUSR2 : reload the configuration and the forked processes
 * SIGTERM : terminate ExaBGP
 * SIGHUP  : terminate ExaBGP (does NOT reload the configuration anymore)
"""


def is_hex (s):
	return all(c in string.hexdigits or c == ':' for c in s)

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
		obj = objgraph.by_type('Reactor')
		objgraph.show_backrefs([obj], max_depth=10)
	sys.exit(code)

def main ():
	options = docopt.docopt(usage, help=False)

	main = int(sys.version[0])
	secondary = int(sys.version[2])

	if main != 2 or secondary < 5:
		sys.exit('This program can not work (is not tested) with your python version (< 2.5 or >= 3.0)')

	if options["--version"]:
		print(version)
		sys.exit(0)

	if options["--decode"]:
		decode = ''.join(options["--decode"]).replace(':','').replace(' ','')
		if not is_hex(decode):
			print(usage)
			print 'Environment values are:\n' + '\n'.join(' - %s' % _ for _ in environment.default())
			print ("\n\n"
				   "The BGP message must be an hexadecimal string.\n"
				   "All colons or spaces are ignored, for example:\n"
				   " --decode 001E0200000007900F0003000101\n"
				   " --decode 001E:02:0000:0007:900F:0003:0001:01\n"
				   " --decode FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF001E0200000007900F0003000101\n"
				   " --decode FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:001E:02:0000:0007:900F:0003:0001:01\n"
				   " --decode 'FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF 001E02 00000007900F0003000101'\n"
				  )
			sys.exit(1)
	else:
		decode = ''

	if options["--folder"]:
		etc = os.path.realpath(os.path.normpath(options["--folder"]))
	else:
		etc = os.path.realpath(os.path.normpath(os.environ.get('ETC','etc')))
	os.environ['ETC'] = etc

	envfile = 'exabgp.env' if not  options["--env"] else options["--env"]
	if not envfile.startswith('/'):
		envfile = '%s/%s' % (etc, envfile)

	from exabgp.configuration.environment import environment

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
			'configuration' : (environment.boolean,environment.lower,'true',     'report command parsing'),
			'reactor'       : (environment.boolean,environment.lower,'true',     'report signal received, command reload'),
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
			'once': (environment.boolean,environment.lower,'false', 'only one tcp connection attempt per peer (for debuging scripts)'),
			'delay': (environment.integer,environment.nop,'0',      'start to announce route when the minutes in the hours is a modulo of this number'),
			'bind': (environment.optional_ip,environment.quote,'', 'IP to bind on when listening (no ip to disable)'),
			'port': (environment.integer,environment.nop,'179', 'port to bind on when listening'),
			'acl': (environment.boolean,environment.lower,'', '(experimental) unimplemented'),
		},
		'bgp' : {
			'openwait': (environment.integer,environment.nop,'60','how many second we wait for an open once the TCP session is established'),
		},
		'cache' : {
			'attributes'  :  (environment.boolean,environment.lower,'true', 'cache all attributes (configuration and wire) for faster parsing'),
			'nexthops'    :  (environment.boolean,environment.lower,'true', 'cache routes next-hops (deprecated: next-hops are always cached)'),
		},
		'api' : {
			'encoder'  :  (environment.api,environment.lower,'text', '(experimental) default encoder to use with with external API (text or json)'),
			'highres'  :  (environment.boolean,environment.lower,'false','should we use highres timer in JSON'),
			'respawn'  :  (environment.boolean,environment.lower,'false','should we respawn a helper process if it dies'),
		},
		'reactor' : {
			'speed' : (environment.real,environment.nop,'1.0', 'time of one reactor loop\n'
			                                                   '%suse only if you understand the code.' % (' '* 34)),
		},
		# Here for internal use
		'internal' : {
			'name'    : (environment.nop,environment.nop,'ExaBGP', 'name'),
			'version' : (environment.nop,environment.nop,version,  'version'),
		},
		# Here for internal use
		'debug' : {
			'pdb' : (environment.boolean,environment.lower,'false','enable python debugger on errors'),
			'memory' : (environment.boolean,environment.lower,'false','command line option --memory'),
			'configuration' : (environment.boolean,environment.lower,'false','undocumented option: raise when parsing configuration errors'),
			'selfcheck' : (environment.boolean,environment.lower,'false','does a self check on the configuration file'),
			'route' : (environment.unquote,environment.quote,'','decode the route using the configuration'),
			'defensive' : (environment.boolean,environment.lower,'false', 'generate random fault in the code in purpose'),
		},
	}

	try:
		env = environment.setup(envfile)
	except environment.Error,e:
		print(usage)
		print '\nconfiguration issue,', str(e)
		sys.exit(1)

	if options["--help"]:
		print(usage)
		print 'Environment values are:\n' + '\n'.join(' - %s' % _ for _ in environment.default())
		sys.exit(0)

	if options["--decode"]:
		env.log.parser = True
		env.debug.route = decode
		env.tcp.bind = ''

	if options["--profile"]:
		env.profile.enable = True
		if options["--profile"].lower() in ['1','true']:
			env.profile.file = True
		elif options["--profile"].lower() in ['0','false']:
			env.profile.file = False
		else:
			env.profile.file = options["--profile"]

	if envfile and not os.path.isfile(envfile):
		comment = 'environment file missing\ngenerate it using "exabgp --fi > %s"' % envfile
	else:
		comment = ''

	if options["--full-ini"] or options["--fi"]:
		for line in environment.iter_ini():
			print line
		sys.exit(0)

	if options["--full-env"] or options["--fe"]:
		print
		for line in environment.iter_env():
			print line
		sys.exit(0)

	if options["--diff-ini"] or options["--di"]:
		for line in environment.iter_ini(True):
			print line
		sys.exit(0)

	if options["--diff-env"] or options["--de"]:
		for line in environment.iter_env(True):
			print line
		sys.exit(0)

	if options["--once"]:
		env.tcp.once = True

	if options["--debug"]:
		env.log.all = True
		env.log.level=syslog.LOG_DEBUG

	if options["--pdb"]:
		# The following may fail on old version of python (but is required for debug.py)
		os.environ['PDB'] = 'true'
		env.debug.pdb = True

	if options["--test"]:
		env.debug.selfcheck = True
		env.log.parser = True

	if options["--memory"]:
		env.debug.memory = True


	configurations = []
	# check the file only once that we have parsed all the command line options and allowed them to run
	if options["<configuration>"]:
		for f in options["<configuration>"]:
			configurations.append(os.path.realpath(os.path.normpath(f)))
	else:
		print(usage)
		print 'Environment values are:\n' + '\n'.join(' - %s' % _ for _ in environment.default())
		print '\nno configuration file provided'
		sys.exit(1)

	for configuration in configurations:
		if not os.path.isfile(configuration):
			from exabgp.logger import Logger
			logger = Logger()
			logger.configuration('the argument passed as configuration is not a file','error')
			sys.exit(1)

	from exabgp.bgp.message.update.attribute.attribute import Attribute
	Attribute.caching = env.cache.attributes

	if len(configurations) == 1:
		run(env,comment,configuration)

	if not (env.log.destination in ('syslog','stdout','stderr') or env.log.destination.startswith('host:')):
		from exabgp.logger import Logger
		logger = Logger()
		logger.configuration('can not log to files when running multiple configuration (as we fork)','error')
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
		from exabgp.logger import Logger
		logger = Logger()
		logger.reactor('Can not fork, errno %d : %s' % (e.errno,e.strerror),'critical')

def run (env,comment,configuration,pid=0):
	from exabgp.logger import Logger
	logger = Logger()

	if comment:
		logger.configuration(comment)

	if not env.profile.enable:
		Reactor(configuration).run()
		__exit(env.debug.memory,0)

	try:
		import cProfile as profile
	except:
		import profile

	if not env.profile.file or env.profile.file == 'stdout':
		profile.run('Reactor(configuration).run()')
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
		logger.reactor('profiling ....')
		pr = profile.Profile()
		pr.enable()
		try:
			Reactor(configuration).run()
		except:
			raise
		finally:
			pr.disable()
			kprofile = lsprofcalltree.KCacheGrind(pr)

			with open(profile_name, 'w+') as write:
				kprofile.output(write)

			__exit(env.debug.memory,0)
	else:
		logger.reactor("-"*len(notice))
		logger.reactor(notice)
		logger.reactor("-"*len(notice))
		Reactor(configuration).run()
		__exit(env.debug.memory,0)


if __name__ == '__main__':
	main()
