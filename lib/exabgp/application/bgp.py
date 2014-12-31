# encoding: utf-8
"""
exabgp.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import platform
import string
import syslog

from exabgp.version import version
# import before the fork to improve copy on write memory savings
from exabgp.reactor import Reactor

from exabgp.dep import docopt
from exabgp.dep import lsprofcalltree

from exabgp.configuration.usage import usage

from exabgp.debug import setup_report
setup_report()

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
		print 'ExaBGP : %s' % version
		print 'Python : %s' % sys.version.replace('\n',' ')
		print 'Uname  : %s' % platform.version()
		sys.exit(0)

	if options["--folder"]:
		folder = os.path.realpath(os.path.normpath(options["--folder"]))
	elif os.environ.get('ETC',None):
		folder = os.path.join(os.path.realpath(os.path.normpath(os.environ.get('ETC','etc'))),'exabgp')
	elif sys.argv[0] == '/usr/local/bin/exabgp':
		folder = '/usr/local/etc/exabgp'
	else:
		folder = '/etc/exabgp'

	if not os.environ.get('ETC',''):
		os.environ['ETC'] = folder

	envfile = 'exabgp.env' if not options["--env"] else options["--env"]
	if not envfile.startswith('/'):
		envfile = '%s/%s' % (folder, envfile)

	from exabgp.configuration.setup import environment

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

	try:
		env = environment.setup(envfile)
	except environment.Error,e:
		print(usage)
		print '\nconfiguration issue,', str(e)
		sys.exit(1)

	duration = options["--signal"]
	if duration and duration.isdigit():
		pid = os.fork()
		if pid:
			import time
			import signal
			try:
				time.sleep(int(duration))
				os.kill(pid,signal.SIGUSR1)
			except KeyboardInterrupt:
				pass
			try:
				pid,exit = os.wait()
				sys.exit(exit)
			except KeyboardInterrupt:
				try:
					pid,exit = os.wait()
					sys.exit(exit)
				except:
					sys.exit(0)

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
			normalised = os.path.realpath(os.path.normpath(f))
			if os.path.isfile(normalised):
				configurations.append(normalised)
				continue
			if f.startswith('etc/exabgp'):
				normalised = os.path.join(folder,f[11:])
				if os.path.isfile(normalised):
					configurations.append(normalised)
					continue
			from exabgp.logger import Logger
			logger = Logger()
			logger.configuration('one of the arguments passed as configuration is not a file (%s)' % f,'error')
			sys.exit(1)

	else:
		print(usage)
		print 'Environment values are:\n' + '\n'.join(' - %s' % _ for _ in environment.default())
		print '\nno configuration file provided'
		sys.exit(1)

	from exabgp.bgp.message.update.attribute.attribute import Attribute
	Attribute.caching = env.cache.attributes

	if env.debug.rotate or len(configurations) == 1:
		run(env,comment,configurations)

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
				run(env,comment,configurations,os.getpid())
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

def run (env,comment,configurations,pid=0):
	from exabgp.logger import Logger
	logger = Logger()

	if comment:
		logger.configuration(comment)

	if not env.profile.enable:
		Reactor(configurations).run()
		__exit(env.debug.memory,0)

	try:
		import cProfile as profile
	except:
		import profile

	if not env.profile.file or env.profile.file == 'stdout':
		profile.run('Reactor(configurations).run()')
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
			Reactor(configurations).run()
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
		Reactor(configurations).run()
		__exit(env.debug.memory,0)


if __name__ == '__main__':
	main()
