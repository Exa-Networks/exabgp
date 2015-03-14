#!/usr/bin/env python
# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import sys
import imp
import platform
from shutil import rmtree
from setuptools import setup
from distutils.util import get_platform

dryrun = False

description_rst = """\
======
ExaBGP
======

.. image:: https://badges.gitter.im/Join%%20Chat.png
   :target: https://gitter.im/Exa-Networks/exabgp
   :alt: Gitter

.. image:: https://pypip.in/wheel/exabgp/badge.png
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Wheel Status

.. image:: https://pypip.in/download/exabgp/badge.png
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Downloads

.. image:: https://pypip.in/version/exabgp/badge.png
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: Latest Version

.. image:: https://img.shields.io/coveralls/Exa-Networks/exabgp.png
   :target: https://coveralls.io/r/Exa-Networks/exabgp
   :alt: Coverage

.. image:: https://pypip.in/license/exabgp/badge.png
   :target: https://pypi.python.org/pypi/exabgp/
   :alt: License

.. contents:: **Table of Contents**
   :depth: 2

Introduction
============

ExaBGP allows engineers to control their network from commodity servers. Think of it as Software Defined Networking using BGP.

It can be used to announce ipv4, ipv6, vpn or flow routes (for DDOS protection) from its configuration file(s).
ExaBGP can also transform BGP messages into friendly plain text or JSON which can be easily manipulate by scripts and report peer announcements.

Use cases include
-----------------

- sql backed `looking glass <https://code.google.com/p/gixlg/wiki/sample_maps>`_ with prefix routing visualisation
- service `high availability <http://vincent.bernat.im/en/blog/2013-exabgp-highavailability.html>`_ automatically isolating dead servers / broken services
- `DDOS mitigation <http://perso.nautile.fr/prez/fgabut-flowspec-frnog-final.pdf>`_ solutions
- `anycasted <http://blog.iweb-hosting.co.uk/blog/2012/01/27/using-bgp-to-serve-high-availability-dns/>`_ services

Installation
============

Prerequisites
-------------

ExaBGP requires python 2.6 or 2.7. It has no external dependencies.

Using pip
---------

#. Use pip to install the packages:

::

    pip install -U exabgp
    exabgp --help


Without installation
--------------------

::

    curl -L https://github.com/Exa-Networks/exabgp/archive/%(version)s.tar.gz | tar zx
    ./exabgp-%(version)s/sbin/exabgp --help

Feedback and getting involved
=============================

- Gitter: https://gitter.im/Exa-Networks/exabgp
- #exabgp: irc://irc.freenode.net:6667/exabgp
- Google +: https://plus.google.com/u/0/communities/108249711110699351497
- Twitter: https://twitter.com/#!/search/exabgp
- Mailing list: http://groups.google.com/group/exabgp-users
- Issue tracker: https://github.com/Exa-Networks/exabgp/issues
- Code Repository: https://github.com/Exa-Networks/exabgp

"""

version_template = """\
version = "%s"

# Do not change the first line as it is parsed by scripts

if __name__ == '__main__':
	import sys
	sys.stdout.write(version)
"""

debian_template = """\
exabgp (%s-0) unstable; urgency=low

  * Latest ExaBGP release.

 -- Vincent Bernat <bernat@debian.org>  %s

"""

if sys.argv[-1] == 'help':
	print """\
python setup.py help     this help
python setup.py cleanup  delete left-over file from release
python setup.py readme   show the pypi RST readme
python setup.py push     update the version, push to github
python setup.py release  tag a new version on github, and update pypi
python setup.py pypi     create egg/wheel
python setup.py debian   prepend the current version to debian/changelog
"""
	sys.exit(0)


def remove_egg ():
	if os.path.exists('lib/exabgp.egg-info'):
		print 'removing left-over egg'
		rmtree('lib/exabgp.egg-info')
	if os.path.exists('build/lib/exabgp'):
		print 'removing left-over egg'
		rmtree('build')

remove_egg()

if sys.argv[-1] == 'cleanup':
	sys.exit(0)

#
# Show python readme.rst
#

if sys.argv[-1].lower() == 'readme':
	print description_rst % { 'version' : '0.0.0' }
	sys.exit(0)

#
# Push a new version to github
#

if sys.argv[-1] == 'push':
	git_version = os.popen('git describe --tags').read().strip()

	with open('lib/exabgp/version.py','w') as version_file:
		version_file.write(version_template % git_version)

	version = imp.load_source('version','lib/exabgp/version.py').version

	if version != git_version:
		print 'version setting failed'
		sys.exit(1)

	commit = 'git ci -a -m "updating version to %s"' % git_version
	push = 'git push'

	ret = dryrun or os.system(commit)
	if ret:
		print 'failed to commit'
		sys.exit(ret)

	ret = dryrun or os.system(push)
	if ret:
		print 'failed to push'
		sys.exit(ret)

	sys.exit(0)

#
# update the debian changelog
#

def debian ():
	from email.utils import formatdate

	version = imp.load_source('version','lib/exabgp/version.py').version

	with open('debian/changelog', 'w') as w:
		w.write(debian_template % (version,formatdate()))

	print 'updated debian/changelog'

if sys.argv[-1] == 'debian':
	debian()
	sys.exit(0)

#
# Check that that there is no version inconsistancy before any pypi action
#

if sys.argv[-1] == 'release':
	print 'figuring valid next release version'

	tags = os.popen('git tag').read().split('-')[0].strip()
	versions = [[int(_) for _ in tag.split('.')]  for tag in tags.split('\n') if tag.count('.') == 2]
	latest = sorted(versions)[-1]
	next = [
		'.'.join([str(_) for _ in (latest[0], latest[1], latest[2]+1)]),
		'.'.join([str(_) for _ in (latest[0], latest[1]+1, 0)]),
		'.'.join([str(_) for _ in (latest[0]+1, 0, 0)]),
	]

	print 'valid versions are:', ', '.join(next)
	print 'checking the CHANGELOG uses one of them'

	with open('CHANGELOG') as changelog:
		changelog.next()  # skip the word version on the first line
		for line in changelog:
			if 'version' in line.lower():
				version = line.split()[1]
				if version in next:
					break
				print 'invalid new version in CHANGELOG'
				sys.exit(1)

	print 'ok, next release is %s' % version
	print 'checking that this release is not already tagged'

	if version in tags.split('\n'):
		print 'this tag was already released'
		sys.exit(1)

	print 'ok, this is a new release'
	print 'rewriting lib/exabgp/version.py'

	with open('lib/exabgp/version.py','w') as version_file:
		version_file.write(version_template % version)

	debian()

	print 'checking if we need to commit a version.py change'

	commit = None
	status = os.popen('git status')
	for line in status.read().split('\n'):
		if 'modified:' in line:
			if 'lib/exabgp/version.py' in line or 'debian/changelog' in line:
				if commit is not False:
					commit = True
			else:
				commit = False
		elif 'renamed:' in line:
			commit = False

	if commit is True:
		command = "git commit -a -m 'updating version to %s'" % version
		print '\n>', command

		ret = dryrun or os.system(command)
		if ret:
			print 'return code is', ret
			print 'could not commit version change (%s)' % version
			sys.exit(1)
		print 'version.py was updated'
	elif commit is False:
		print 'more than one file is modified and need updating, aborting'
		sys.exit(1)
	else:  # None
		print 'version.py was already set'

	print 'tagging the new version'
	command = "git tag -a %s -m 'release %s'" % (version,version)
	print '\n>', command

	ret = dryrun or os.system(command)
	if ret:
		print 'return code is', ret
		print 'could not tag version (%s)' % version
		sys.exit(1)

	print 'pushing the new tag to local repo'
	command = "git push --tags"
	print '\n>', command

	ret = dryrun or os.system(command)
	if ret:
		print 'return code is', ret
		print 'could not push release version'
		sys.exit(1)

	print 'pushing the new tag to upstream'
	command = "git push --tags upstream"
	print '\n>', command

	ret = dryrun or os.system(command)
	if ret:
		print 'return code is', ret
		print 'could not push release version'
		sys.exit(1)
	sys.exit(0)

if sys.argv[-1] in ('pypi'):
	print
	print 'updating PyPI'

	command = "python setup.py sdist upload"
	print '\n>', command

	ret = dryrun or os.system(command)
	if ret:
		print 'return code is', ret
		print 'could not generate egg on pypi'
		sys.exit(1)

	remove_egg()

	command = "python setup.py bdist_wheel upload"
	print '\n>', command

	ret = dryrun or os.system(command)
	if ret:
		print 'return code is', ret
		print 'could not generate wheel on pypi'
		sys.exit(1)

	print 'all done.'
	sys.exit(0)


def packages (lib):
	def dirs (*path):
		for location,_,_ in os.walk(os.path.join(*path)):
			yield location

	def modules (lib):
		return os.walk(lib).next()[1]

	r = []
	for module in modules(lib):
		for d in dirs(lib,module):
			r.append(d.replace('/','.').replace('\\','.')[len(lib)+1:])
	return r

def configuration (etc):
	etcs = []
	for l,d,fs in os.walk(etc):
		if not d:
			for f in fs:
				etcs.append(os.path.join(l,f))
	return etcs

os_name = platform.system()

if os_name == 'NetBSD':
	files_definition= [
		('share/exabgp',configuration('etc/exabgp')),
	]
else:
	files_definition = [
		('etc/exabgp',configuration('etc/exabgp')),
	]
	if sys.argv[-1] == 'systemd':
		files_definition.append(('/usr/lib/systemd/system',configuration('etc/systemd')))

version = imp.load_source('version','lib/exabgp/version.py').version

setup(name='exabgp',
	version=version,
	description='BGP swiss army knife',
	long_description=description_rst % {'version': version},
	author='Thomas Mangin',
	author_email='thomas.mangin@exa-networks.co.uk',
	url='https://github.com/Exa-Networks/exabgp',
	license="BSD",
	keywords = 'bgp routing api sdn flowspec',
	platforms=[get_platform(),],
	package_dir={'': 'lib'},
	packages=packages('lib'),
#	scripts=['sbin/exabgp',],
	download_url='https://github.com/Exa-Networks/exabgp/archive/%s.tar.gz' % version,
	data_files=files_definition,
	classifiers=[
		'Development Status :: 5 - Production/Stable',
		'Environment :: Console',
		'Intended Audience :: System Administrators',
		'Intended Audience :: Telecommunications Industry',
		'License :: OSI Approved :: BSD License',
		'Operating System :: POSIX',
		'Operating System :: MacOS :: MacOS X',
		'Operating System :: Microsoft :: Windows',
		'Programming Language :: Python',
		'Topic :: Internet',
	],
	entry_points={
		'console_scripts': [
			'exabgp = exabgp.application:run_exabgp',
		],
	},
)
