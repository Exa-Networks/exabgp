# encoding: utf-8
"""
exabgp.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import os
import sys

from exabgp.version import version

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


def version_warning ():
	sys.stdout.write('\n')
	sys.stdout.write('************ WARNING *** WARNING *** WARNING *** WARNING *********\n')
	sys.stdout.write('* This program SHOULD work with your python version (2.4).       *\n')
	sys.stdout.write('* No tests have been performed. Consider python 2.4 unsupported  *\n')
	sys.stdout.write('* Please consider upgrading to the latest 2.x stable realease.   *\n')
	sys.stdout.write('************ WARNING *** WARNING *** WARNING *** WARNING *********\n')
	sys.stdout.write('\n')


def help ():
	sys.stdout.write('usage:\n exabgp [options] <bgp configuration file>\n')
	sys.stdout.write('\n')
	sys.stdout.write('  -h, --help      : this help\n')
	sys.stdout.write('  -c, --command   : command line file to use (ini format)\n')
	sys.stdout.write('  -i, --ini       : display the configuration using the ini format\n')
	sys.stdout.write('  -e, --env       : display the configuration using the env format\n')
	sys.stdout.write(' -di, --diff-ini  : display non-default configurations values using the ini format\n')
	sys.stdout.write(' -de, --diff-env  : display non-default configurations values using the env format\n')
	sys.stdout.write('  -d, --debug     : shortcut to turn on all subsystems debugging (shortcut for exabgp.log.all=true)\n')
	sys.stdout.write('  -p, --pdb       : start the python debugger on serious logging and on SIGTERM\n')
#	sys.stdout.write('  -m, --memory    : display memory usage information on exit\n')
	sys.stdout.write(' --profile <file> : enable profiling (shortcut for exabgp.profile.enable=true exabgp.profle=file=<file>)\n')

	sys.stdout.write('\n')
	sys.stdout.write('ExaBGP will automatically look for its configuration file (in windows ini format)\n')
	sys.stdout.write(' - in the etc/exabgp folder located within the extracted tar.gz \n')
	sys.stdout.write(' - in /etc/exabgp/exabgp.conf\n')
	sys.stdout.write('\n')
	sys.stdout.write('Individual configuration options can be set using environment variables, such as :\n')
	sys.stdout.write('   > env exabgp.bgp.minimal=true ./sbin/exabgp\n')
	sys.stdout.write('or > env exabgp_bgp_minimal=true ./sbin/exabgp\n')
	sys.stdout.write('or > export exabgp_bgp_minimal=true; ./sbin/exabgp\n')
	sys.stdout.write('\n')
	sys.stdout.write('Multiple environment values can be set\n')
	sys.stdout.write('and the order of preference is :\n')
	sys.stdout.write(' - 1 : command line env value using dot separated notation\n')
	sys.stdout.write(' - 2 : exported value from the shell using dot separated notation\n')
	sys.stdout.write(' - 3 : command line env value using underscore separated notation\n')
	sys.stdout.write(' - 4 : exported value from the shell using underscore separated notation\n')
	sys.stdout.write(' - 5 : the value in the ini configuration file\n')
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


if __name__ == '__main__':
	main = int(sys.version[0])
	secondary = int(sys.version[2])

	if main != 2 or secondary < 4:
		sys.exit('This program can not work (is not tested) with your python version (< 2.4 or >= 3.0)')

	if main == 2 and secondary == 4:
		version_warning()

	from exabgp.command import CommandError,load,ini,env,default

	if len(sys.argv) < 2:
		help()
		sys.exit(0)

	next = ''
	arguments = {
		'command' : '',
		'configuration' : '',
	}

	configuration = os.path.normpath(os.path.abspath(sys.argv[-1]))
	if not os.path.exists(configuration):
		sys.stdout.write('The last parameter is not a peer and route definition file')
		sys.exit(1)

	for arg in sys.argv[1:-1]:
		if next:
			arguments[next] = arg
			next = ''
			continue
		if arg in ['-c','--command']:
			next = 'command'
		if arg in ['--profile',]:
			next = 'profile'

	try:
		command = load(arguments['command'])
	except CommandError,e:
		print >> sys.stderr, 'configuration issue,', str(e)
		sys.exit(1)

	if 'profile' in arguments:
		command.profile.enable = True
		command.profile.file = arguments['profile']

	for arg in sys.argv[1:]:
		if arg in ['--',]:
			break
		if arg in ['-h','--help']:
			help()
			sys.exit(0)
		if arg in ['-i','--ini']:
			ini()
			sys.exit(0)
		if arg in ['-e','--env']:
			env()
			sys.exit(0)
		if arg in ['-di','--diff-ini']:
			ini(True)
			sys.exit(0)
		if arg in ['-de','--diff-env']:
			env(True)
			sys.exit(0)
		if arg in ['--profile',]:
			command.profile.enable = True
		if arg in ['-d','--debug']:
			command.log.all = True
			command.log.level='LOG_DEBUG'
		if arg in ['-p','--pdb']:
			# The following may fail on old version of python (but is required for debug.py)
			os.environ['PDB'] = 'true'
			command.debug.pdb = True
		if arg in ['-m','--memory']:
			command.debug.memory = True

	from exabgp.log import Logger
	logger = Logger()

	from exabgp.supervisor import Supervisor

	if not command.profile.enable:
		Supervisor(configuration).run()
		__exit(command.debug.memory,0)

	try:
		import cProfile as profile
	except:
		import profile

	if not command.profile.file or command.profile.file == 'stdout':
		profile.run('Supervisor(configuration).run()')
		__exit(command.debug.memory,0)

	notice = ''
	if os.path.isdir(command.profile.file):
		notice = 'profile can not use this filename as outpout, it is not a directory (%s)' % profiled
	if os.path.exists(command.profile.file):
		notice = 'profile can not use this filename as outpout, it already exists (%s)' % profiled

	if not notice:
		log.debug('profiling ....')
		profile.run('main()',filename=configuration.profile.destination)
	else:
		log.debug("-"*len(notice))
		log.debug(notice)
		log.debug("-"*len(notice))
		main()
		__exit(command.debug.memory,0)
