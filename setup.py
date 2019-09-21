#!/usr/bin/env python
# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

import os
import sys
import imp
import platform
from shutil import rmtree
from setuptools import setup
from distutils.util import get_platform

CHANGELOG = os.path.join(os.getcwd(),os.path.dirname(sys.argv[0]),'CHANGELOG')
VERSION_PY = os.path.join(os.getcwd(),os.path.dirname(sys.argv[0]),'lib/exabgp/version.py')
DEBIAN = os.path.join(os.getcwd(),os.path.dirname(sys.argv[0]),'debian/changelog')
EGG = os.path.join(os.getcwd(),os.path.dirname(sys.argv[0]),'lib/exabgp.egg-info')
BUILD_EXABGP = os.path.join(os.getcwd(),os.path.dirname(sys.argv[0]),'build/lib/exabgp')
BUILD_ROOT = os.path.join(os.getcwd(),os.path.dirname(sys.argv[0]),'build')


dryrun = False

json_version = '4.0.1'
text_version = '4.0.1'

version_template = """\
import os

release = "%s"
json = "%s"
text = "%s"
version = os.environ.get('EXABGP_VERSION',release)

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
	print("""\
python setup.py help     this help
python setup.py cleanup  delete left-over file from release
python setup.py current  show the current version
python setup.py next     show the next version
python setup.py version  set the content of the version include file
python setup.py push     update the version, push to github
python setup.py release  tag a new version on github, and update pypi
python setup.py pypi     create egg/wheel
python setup.py debian   prepend the current version to debian/changelog
""")
	sys.exit(0)


def versions ():
	versions = []
	with open(CHANGELOG) as changelog:
		changelog.readline()
		for line in changelog:
			if line.lower().startswith('version '):
				version = line.split()[1]
				versions.append(version)
	return versions


def remove_egg ():
	if os.path.exists(EGG):
		print('removing left-over egg')
		rmtree(EGG)
	if os.path.exists(BUILD_EXABGP):
		print('removing left-over egg')
		rmtree(BUILD_ROOT)


remove_egg()

if sys.argv[-1] == 'cleanup':
	sys.exit(0)

if sys.argv[-1] == 'current':
	print(versions()[1])
	sys.exit(0)

if sys.argv[-1] == 'next':
	print(versions()[0])
	sys.exit(0)

def set_version ():
	next_version = versions()[0]
	git_version = os.popen('git rev-parse --short HEAD').read().strip()
	full_version = "%s-%s" % (next_version,git_version)

	with open(VERSION_PY,'w') as version_file:
		version_file.write(version_template % (
			full_version,
			json_version,
			text_version
		))

	version = imp.load_source('version',VERSION_PY).version

	if version != full_version:
		print('version setting failed')
		sys.exit(1)

	return git_version

#
# Set the content of the version file
#

if sys.argv[-1] == 'version':
	set_version()
	sys.exit(0)

#
# Show python readme.rst
#

#
# Push a new version to github
#

if sys.argv[-1] == 'push':
	git_version = set_version()

	commit = 'git ci -a -m "updating version to %s"' % git_version
	push = 'git push'

	ret = dryrun or os.system(commit)
	if ret:
		print('failed to commit')
		sys.exit(ret)

	ret = dryrun or os.system(push)
	if ret:
		print('failed to push')
		sys.exit(ret)

	sys.exit(0)

#
# update the debian changelog
#

def debian ():
	from email.utils import formatdate

	version = imp.load_source('version',VERSION_PY).version

	with open(DEBIAN, 'w') as w:
		w.write(debian_template % (version,formatdate()))

	print('updated debian/changelog')

if sys.argv[-1] == 'debian':
	debian()
	sys.exit(0)

#
# Check that that there is no version inconsistancy before any pypi action
#

if sys.argv[-1] == 'release':
	print('figuring valid next release version')

	tags = os.popen('git tag').read().split('-')[0].strip()
	tag_versions = [
		[int(_) for _ in tag.split('.')]  for tag in tags.split('\n')
		if tag.count('.') == 2 and tag[0].isdigit()
	]
	latest = sorted(tag_versions)[-1]
	next = [
		'.'.join([str(_) for _ in (latest[0], latest[1], latest[2]+1)]),
		'.'.join([str(_) for _ in (latest[0], latest[1]+1, 0)]),
		'.'.join([str(_) for _ in (latest[0]+1, 0, 0)]),
	]

	print('valid versions are:', ', '.join(next))
	print('checking the CHANGELOG uses one of them')

	next_version = versions()[0]
	if next_version.count('.') != 2:
		print('invalid new version in CHANGELOG')
		sys.exit(1)

	print('ok, next release is %s' % next_version)
	print('checking that this release is not already tagged')

	if next_version in tags.split('\n'):
		print('this tag was already released')
		sys.exit(1)

	print('ok, this is a new release')
	print('rewriting lib/exabgp/version.py')

	git_version = os.popen('git rev-parse --short HEAD').read().strip()
	full_version = "%s-%s" % (next_version,git_version)

	with open(VERSION_PY,'w') as version_file:
		version_file.write(version_template % (
			full_version,
			json_version,
			text_version
		))

	debian()

	print('checking if we need to commit a version.py change')

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
		command = "git commit -a -m 'updating version to %s'" % next_version
		print('\n>', command)

		ret = dryrun or os.system(command)
		if ret:
			print('return code is', ret)
			print('could not commit version change (%s)' % next_version)
			sys.exit(1)
		print('version.py was updated')
	elif commit is False:
		print('more than one file is modified and need updating, aborting')
		sys.exit(1)
	else:  # None
		print('version.py was already set')

	print('tagging the new version')
	command = "git tag -a %s -m 'release %s'" % (next_version,next_version)
	print('\n>', command)

	ret = dryrun or os.system(command)
	if ret:
		print('return code is', ret)
		print('could not tag version (%s)' % next_version)
		sys.exit(1)

	print('pushing the new tag to local repo')
	command = "git push --tags"
	print('\n>', command)

	ret = dryrun or os.system(command)
	if ret:
		print('return code is', ret)
		print('could not push release version')
		sys.exit(1)

	print('pushing the new tag to upstream')
	command = "git push --tags upstream"
	print('\n>', command)

	ret = dryrun or os.system(command)
	if ret:
		print('return code is', ret)
		print('could not push release version')
		sys.exit(1)
	sys.exit(0)

if sys.argv[-1] in ('pypi'):
	print()
	print('updating PyPI')

	command = "python3 setup.py sdist upload"
	print('\n>', command)

	ret = dryrun or os.system(command)
	if ret:
		print('return code is', ret)
		print('could not generate egg on pypi')
		sys.exit(1)

	remove_egg()

	command = "python3 setup.py bdist_wheel upload"
	print('\n>', command)

	ret = dryrun or os.system(command)
	if ret:
		print('return code is', ret)
		print('could not generate wheel on pypi')
		sys.exit(1)

	print('all done.')
	sys.exit(0)


def packages (lib):
	def dirs (*path):
		for location,_,_ in os.walk(os.path.join(*path)):
			yield location

	def modules (lib):
		return next(os.walk(lib))[1]

	r = []
	for module in modules(lib):
		for d in dirs(lib,module):
			r.append(d.replace('/','.').replace('\\','.')[len(lib)+1:])
	return r


def filesOf (directory):
	files = []
	for l,d,fs in os.walk(directory):
		if not d:
			for f in fs:
				files.append(os.path.join(l,f))
	return files


def testFilesOf (directory):
	files = []
	for l,d,fs in os.walk(directory):
		if not d:
			for f in fs:
				if f.endswith('.run') or f.endswith('.conf'):
					files.append(os.path.join(l,f))
	return files


os_name = platform.system()

files_definition = [
	('share/exabgp/processes',filesOf('etc/exabgp')),
	('share/exabgp/etc',testFilesOf('qa/conf')),
]

if os_name != 'NetBSD':
	if sys.argv[-1] == 'systemd':
		files_definition.append(('/usr/lib/systemd/system',filesOf('etc/systemd')))

version = imp.load_source('version','lib/exabgp/version.py').version.split('-')[0]

try:
	description_rst = open('PYPI.rst').read() % {'version': version}
except IOError:
	description_rst = 'ExaBGP'

setup(
	name='exabgp',
	version=version,
	description='BGP swiss army knife',
	long_description=description_rst,
	author='Thomas Mangin',
	author_email='thomas.mangin@exa-networks.co.uk',
	url='https://github.com/Exa-Networks/exabgp',
	license='BSD',
	keywords='BGP routing SDN FlowSpec HA',
	platforms=[get_platform(),],
	package_dir={'': 'lib'},
	packages=packages('lib'),
	package_data={'': ['PYPI.rst']},
	download_url='https://github.com/Exa-Networks/exabgp/archive/%s.tar.gz' % version,
	data_files=files_definition,
	setup_requires=['setuptools'],
	classifiers=[
		'Development Status :: 5 - Production/Stable',
		'Environment :: Console',
		'Intended Audience :: System Administrators',
		'Intended Audience :: Telecommunications Industry',
		'License :: OSI Approved :: BSD License',
		'Operating System :: POSIX',
		'Operating System :: MacOS :: MacOS X',
		'Programming Language :: Python',
		'Programming Language :: Python :: 3.7',
		'Topic :: Internet',
	],
	entry_points={
		'console_scripts': [
			'exabgp = exabgp.application:run_exabgp',
			'exabgpcli = exabgp.application:run_cli',
		],
	},
)
