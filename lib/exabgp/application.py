# encoding: utf-8
"""
exabgp.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import os
import sys

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


def help (comment=''):
	sys.stdout.write('usage:\n exabgp [options] <bgp configuration file>\n')
	sys.stdout.write('\n')
	sys.stdout.write('  -h, --help      : this help\n')
	sys.stdout.write('  -c, --conf      : configuration folder\n')
	sys.stdout.write('  -e, --env       : configuration file with environment value (ini format)\n')
	sys.stdout.write(' -fi, --full-ini  : display the configuration using the ini format\n')
	sys.stdout.write(' -fe, --full-env  : display the configuration using the env format\n')
	sys.stdout.write(' -di, --diff-ini  : display non-default configurations values using the ini format\n')
	sys.stdout.write(' -de, --diff-env  : display non-default configurations values using the env format\n')
	sys.stdout.write('  -d, --debug     : turn on all subsystems debugging\n'
	                 '                    shortcut for exabgp.log.all=true exabgp.log.level=LOG_DEBUG\n')
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

if __name__ == '__main__':
	main = int(sys.version[0])
	secondary = int(sys.version[2])

	if main != 2 or secondary < 4:
		sys.exit('This program can not work (is not tested) with your python version (< 2.4 or >= 3.0)')

	if main == 2 and secondary == 4:
		version_warning()

	from exabgp.structure.environment import EnvError,load,iter_ini,iter_env,default

	next = ''
	arguments = {
		'folder' : '',
		'file' : '',
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
		if not arguments['file']:
			arguments['file'] = arg
			continue
		parse_error = "invalid command line, more than one file name provided '%s' and '%s'" % (arguments['file'],arg)
		break

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
			env.log.level='LOG_DEBUG'
		if arg in ['-p','--pdb']:
			# The following may fail on old version of python (but is required for debug.py)
			os.environ['PDB'] = 'true'
			env.debug.pdb = True
		if arg in ['-m','--memory']:
			env.debug.memory = True

	from exabgp.structure.log import Logger
	logger = Logger()

	if parse_error:
		logger.error(parse_error,'configuration')
		sys.exit(1)

	from exabgp.structure.supervisor import Supervisor

	# check the file only once that we have parsed all the command line options and allowed them to run
	if arguments['file']:
		configuration = os.path.realpath(os.path.normpath(arguments['file']))
	else:
		logger.error('no configuration file provided','configuration')
		sys.exit(1)

	if not os.path.isfile(configuration):
		logger.error('the argument passed as configuration is not a file','configuration')
		sys.exit(1)

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

	notice = ''
	if os.path.isdir(env.profile.file):
		notice = 'profile can not use this filename as outpout, it is not a directory (%s)' % profile
	if os.path.exists(env.profile.file):
		notice = 'profile can not use this filename as outpout, it already exists (%s)' % profile

	if not notice:
		logger.info('profiling ....','profile')
		profile.run('Supervisor(configuration).run()',filename=env.profile.file)
	else:
		logger.info("-"*len(notice),'profile')
		logger.info(notice,'profile')
		logger.info("-"*len(notice),'profile')
		Supervisor(configuration).run()
		__exit(env.debug.memory,0)
