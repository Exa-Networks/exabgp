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


if sys.argv[-1] == 'help':
	print """\
python setup.py help     this help
python setup.py push     update the version, push to github
python setup.py release  tag a new version on github, and update pypi
"""
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
	long_description="Control your network using BGP from any commodity servers and reap the benefit of software defined networking without OpenFlow. Receive parsed BGP updates in a friendly form (plain text or JSON) and manipulate them with simple scripts.",
	author='Thomas Mangin',
	author_email='thomas.mangin@exa-networks.co.uk',
	url='https://github.com/Exa-Networks/exabgp',
	license="BSD",
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
