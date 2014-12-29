#!/usr/bin/env python
# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

import os
import sys
import imp
import platform
from distutils.core import setup
from distutils.util import get_platform

description_rst = """\
======
ExaBGP
======

.. image:: https://badges.gitter.im/Join%20Chat.png
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


Without installation
--------------------

::

    wget https://github.com/Exa-Networks/exabgp/archive/3.4.5.tar.gz
    tar zxvf 3.4.5.tar.gz
    cd exabgp-3.4.5
    ./sbin/exabgp --help

Feedback and getting involved
=============================

- Google +: https://plus.google.com/u/0/communities/108249711110699351497
- Twitter: https://twitter.com/#!/search/exabgp
- Mailing list: http://groups.google.com/group/exabgp-users
- Issue tracker: https://github.com/Exa-Networks/exabgp/issues
- Code Repository: https://github.com/Exa-Networks/exabgp

"""

if sys.argv[-1] == 'help':
	print """\
python setup.py help     this help
python setup.py push     update the version, push to github
python setup.py release  tag a new version on github, and update pypi
"""
	sys.exit(0)

#
# Show python readme.rst
#

if sys.argv[-1].lower() == 'readme':
	print description_rst
	sys.exit(0)

#
# Push a new version to github
#

if sys.argv[-1] == 'push':
	version_template = """\
version="%s"

# Do not change the first line as it is parsed by scripts

if __name__ == '__main__':
	import sys
	sys.stdout.write(version)
"""

	git_version = os.popen('git describe --tags').read().strip()

	with open('lib/exabgp/version.py','w') as version_file:
		version_file.write(version_template % git_version)

	version = imp.load_source('version','lib/exabgp/version.py').version

	if version != git_version:
		print 'version setting failed'
		sys.exit(1)

	commit = 'git ci -a -m "updating version to %s"' % git_version
	push = 'git push'

	ret = os.system(commit)
	if not ret:
		print 'failed to commit'
		sys.exit(ret)

	ret = os.system(push)
	if not ret:
		print 'failed to push'
		sys.exit(ret)

	sys.exit(0)

#
# Check that that there is no version inconsistancy before any pypi action
#

if sys.argv[-1] == 'release':
	try:
		short_git_version = os.popen('git describe --tags').read().split('-')[0].strip()
		tags = os.popen('git tag').read().split('-')[0].strip()

		for tag in tags.split('\n'):
			if tag.strip() == short_git_version:
				print 'this tag was already released'
				sys.exit(1)

		file_version = imp.load_source('version','lib/exabgp/version.py').version

		with open('CHANGELOG') as changelog:
			changelog.next()  # skip the word version on the first line
			for line in changelog:
				if 'version' in line.lower():
					if not file_version in line:
						print "CHANGELOG version does not match the code/git"
						print 'new version is:', version
						print 'CHANGELOG has :', line
						sys.exit(1)
					break

		git_version = os.popen('git describe --tags').read().strip()

		if git_version != file_version:
			status = os.popen('git status')
			for line in status.split('\n'):
				if 'modified:' in line and 'version.py' in line:
					ret = os.system("git ci -a -m 'updating version to %s'" % file_version)
					if not ret:
						print 'could not commit version change (%s)' % file_version
						sys.exit(1)
					git_version = file_version

		if git_version != file_version:
			print "No new version. version.py and git do not agree on the version"
			sys.exit(1)

		ret = os.system("git tag -a %s" % file_version)
		if not ret:
			print 'could not tag version (%s)' % file_version
			sys.exit(1)
		ret = os.system("git push --tags")
		if not ret:
			print 'could not push release version'
			sys.exit(1)

		ret = os.system("python setup.py sdist upload")
		if not ret:
			print 'could not generate egg on pypi'
			sys.exit(1)
		ret = os.system("python setup.py bdist_wheel upload")
		if not ret:
			print 'could not generate wheel on pypi'
			sys.exit(1)

	except Exception,e:
		print "Can not check the version consistancy"
		sys.exit(1)

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
		('bin/exabgp',configuration('etc/exabgp')),
	]
else:
	files_definition = [
		('etc/exabgp',configuration('etc/exabgp')),
		('/usr/lib/systemd/system',configuration('etc/systemd')),
	]

setup(name='exabgp',
	version=version,
	description='BGP swiss army knife',
	long_description=description_rst,
	author='Thomas Mangin',
	author_email='thomas.mangin@exa-networks.co.uk',
	url='https://github.com/Exa-Networks/exabgp',
	license="BSD",
	keywords = 'bgp routing api sdn flowspec',
	platforms=[get_platform(),],
	package_dir={'': 'lib'},
	packages=packages('lib'),
	scripts=['sbin/exabgp',],
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
)
