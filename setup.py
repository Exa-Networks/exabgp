#!/usr/bin/env python
# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import os
import sys
import glob
from distutils.core import setup
from distutils.util import get_platform

try:
	f = open('lib/exabgp/version.py','r')
	version = f.read().strip().split('"')[1]
	f.close()
except Exception,e:
	print "can not find the 'version.py' file in the repository"
	sys.exit(1)

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

setup(name='exabgp',
	version=version,
	description='a bgp route engine',
	long_description="A BGP software which can be used to announce IPv4/IPv6 routes with arbitrary next-hops, source flow routes, manipulate received routes/generate routes though third party plugins/applications",
	author='Thomas Mangin',
	author_email='thomas.mangin@exa-networks.co.uk',
	url='http://code.google.com/p/exabgp/',
	license="BSD",
	platforms=[get_platform(),],
	package_dir = {'': 'lib'},
	packages=packages('lib'),
	scripts=['sbin/exabgp',],
	download_url='http://exabgp.googlecode.com/files/exabgp-%s.tgz' % version,
	data_files=[
		('etc/exabgp',configuration('etc/exabgp')),
	],
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
