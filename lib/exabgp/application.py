# encoding: utf-8
"""
exabgp.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import os
import sys

from exabgp.structure.environment import EnvError,load,iter_ini,iter_env,LOG,default
# import before the fork to improve copy on write memory savings
from exabgp.structure.supervisor import Supervisor

def __exit(memory,code):
	if memory:
		from exabgp.leak import objgraph
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
	                 '                    one of : EMERG,ALERT,CRITICAL,ERROR,WARNING,NOTICE,INFO,DEBUG')
	sys.stdout.write('  -p, --pdb       : start the python debugger on serious logging and on SIGTERM\n'
	                 '                    shortcut for exabgp.pdb.enable=true\n')
	sys.stdout.write('  -m, --memory    : display memory usage information on exit\n')
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

	for line in default():
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
		'folder' : '',
		'file' : [],
		'env' : 'exabgp.env',
	}

	parse_error = ''

	for arg in sys.argv[1:]:
		if next:
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

	try:
		env = load(envfile)
	except EnvError,e:
		print >> sys.stderr, 'configuration issue,', str(e)
		sys.exit(1)

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
			for line in iter_ini():
				print line
			sys.exit(0)
		if arg in ['-fe','--full-env']:
			print
			for line in iter_env():
				print line
			sys.exit(0)
		if arg in ['-di','--diff-ini']:
			for line in iter_ini(True):
				print line
			sys.exit(0)
		if arg in ['-de','--diff-env']:
			for line in iter_env(True):
				print line
			sys.exit(0)
		if arg in ['--profile',]:
			env.profile.enable = True
		if arg in ['-d','--debug']:
			env.log.all = True
			env.log.level=LOG.DEBUG
		if arg in ['-p','--pdb']:
			# The following may fail on old version of python (but is required for debug.py)
			os.environ['PDB'] = 'true'
			env.debug.pdb = True
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
	from exabgp.structure.supervisor import Supervisor
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
