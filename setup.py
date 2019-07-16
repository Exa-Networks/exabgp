#!/usr/bin/env python3
# encoding: utf-8
"""
setup.py

Created by Thomas Mangin on 2011-01-24.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

import os
import sys


class path:
	root = os.path.join(os.getcwd(), os.path.dirname(sys.argv[0]))
	changelog = os.path.join(root,'CHANGELOG')
	lib_exa = os.path.join(root, 'lib/exabgp')
	version = os.path.join(root, 'lib/exabgp/version.py')
	debian = os.path.join(root, 'debian/changelog')
	egg = os.path.join(root, 'lib/exabgp.egg-info')
	build_exabgp = os.path.join(root, 'build/lib/exabgp')
	build_root = os.path.join(root, 'build')

	@staticmethod
	def remove_egg():
		from shutil import rmtree
		print('removing left-over egg')
		if os.path.exists(path.egg):
			rmtree(path.egg)
		if os.path.exists(path.build_exabgp):
			rmtree(path.build_root)
		return 0


class version:
	JSON = '4.0.1'
	TEXT = '4.0.1'

	template = """\
import os

commit = "%s"
release = "%s"
json = "%s"
text = "%s"
version = os.environ.get('EXABGP_VERSION',release)

# Do not change the first line as it is parsed by scripts

if __name__ == '__main__':
	import sys
	sys.stdout.write(version)
"""

	@staticmethod
	def get():
		sys.path.append(path.lib_exa)
		from version import version as release

		# transitional fix
		if "-" in release:
			release = release.split("-")[0]

		if version.changelog() != release:
			release += ".post1"

		return release

	@staticmethod
	def changelog():
		with open(path.changelog) as f:
			f.readline()
			for line in f:
				if line.lower().startswith('version '):
					return line.split()[1].rstrip().rstrip(':').strip()
		return ''

	@staticmethod
	def set(tag,commit):
		with open(path.version, 'w') as f:
			f.write(version.template % (
				commit, tag,
				version.JSON,
				version.TEXT
			))
		return version.get() == tag

	@staticmethod
	def latest (tags):
		valid = [
			[int(_) for _ in tag.split('.')] for tag in tags
			if version.valid(tag)
		]
		return '.'.join(str(_) for _ in sorted(valid)[-1])

	@staticmethod
	def valid (tag):
		parts = tag.split('.')
		return len(parts) == 3 \
			and parts[0].isdigit() \
			and parts[1].isdigit() \
			and parts[2].isdigit()

	@staticmethod
	def candidates(tag):
		latest = [int(_) for _ in tag.split('.')]
		return [
			'.'.join([str(_) for _ in (latest[0], latest[1], latest[2] + 1)]),
			'.'.join([str(_) for _ in (latest[0], latest[1] + 1, 0)]),
			'.'.join([str(_) for _ in (latest[0] + 1, 0, 0)]),
		]


class debian:
	template = """\
exabgp (%s-0) unstable; urgency=low

  * Latest ExaBGP release.

 -- Vincent Bernat <bernat@debian.org>  %s

"""
	@staticmethod
	def set(version):
		from email.utils import formatdate
		with open(path.debian, 'w') as w:
			w.write(debian.template % (version, formatdate()))
		print('updated debian/changelog')


class command:
	dryrun = 'dry-run' if os.environ.get('DRY', os.environ.get('DRYRUN', os.environ.get('DRY_RUN', False))) else ''

	@staticmethod
	def run(cmd):
		print('>', cmd)
		return git.dryrun or os.system(cmd)


class git (command):
	@staticmethod
	def commit (comment):
		return git.run('git commit -a -m "%s"' % comment)

	@staticmethod
	def push(tag=False,repo=''):
		command = 'git push'
		if tag:
			command += ' --tags'
		if repo:
			command += ' %s' % repo
		return git.run(command)

	@staticmethod
	def head_commit():
		return os.popen('git rev-parse --short HEAD').read().strip()

	@staticmethod
	def tags():
		return os.popen('git tag').read().split('-')[0].strip().split('\n')

	@staticmethod
	def tag(release):
		return git.run('git tag -a %s -m "release %s"' % (release, release))

	@staticmethod
	def pending():
		commit = None
		for line in os.popen('git status').read().split('\n'):
			if 'modified:' in line:
				if 'lib/exabgp/version.py' in line or 'debian/changelog' in line:
					if commit is not False:
						commit = True
				else:
					return False
			elif 'renamed:' in line:
				return False
		return commit

class repo:
	def update_version():
		if not version.set(version.changelog(), git.head_commit()):
			print('failed to set version in python code')
			return False

		if not git.commit('updating version to %s' % version.get()):
			print('failed to commit the change')
			return False

		if not git.push():
			print('failed to push the change')
			return False
		return True


#
# Check that that there is no version inconsistancy before any pypi action
#

def release_github():
	print()
	print('updating Github')
	release = version.changelog()
	tags = git.tags()

	if not version.valid(release):
		print('invalid new version in CHANGELOG (%s)' % release)
		return 1

	candidates = version.candidates(version.latest(tags))

	print('valid versions are:', ', '.join(candidates))
	print('checking the CHANGELOG uses one of them')

	print('ok, next release is %s' % release)
	print('checking that this release is not already tagged')

	if release in tags:
		print('this tag was already released')
		return 1

	print('ok, this is a new release')
	print('rewriting lib/exabgp/version.py')
	version.set(release, git.head_commit())
	print('rewriting debian/changelog')
	debian.set(release)

	print('checking if we need to commit a version.py change')
	status = git.pending()
	if status is None:
		print('all is already set for release')
	elif status is False:
		print('more than one file is modified and need updating, aborting')
		return 1
	else:
		if git.commit('updating version to %s' % release):
			print('could not commit version change (%s)' % release)
			return 1
		print('version was updated')

	print('tagging the new version')
	if git.tag(version):
		print('could not tag version (%s)' % release)
		return 1

	print('pushing the new tag to local repo')
	if git.push(tag=True, repo='upstream'):
		print('could not push release version')
		return 1
	return 0


def release_pypi():
	print()
	print('updating PyPI')

	path.remove_egg()

	if command.run('python3 setup.py sdist upload'):
		print('could not generate egg on pypi')
		return 1

	if command.run('python3 setup.py bdist_wheel upload'):
		print('could not generate wheel on pypi')
		return 1

	print('all done.')
	return 0


def st():
	import platform
	from distutils.util import get_platform
	from setuptools import setup

	def packages(lib):
		def dirs(*path):
			for location, _, _ in os.walk(os.path.join(*path)):
				yield location

		def modules(lib):
			return next(os.walk(lib))[1]

		r = []
		for module in modules(lib):
			for d in dirs(lib, module):
				r.append(d.replace('/', '.').replace('\\', '.')[len(lib) + 1:])
		return r


	def filesOf(directory):
		files = []
		for l, d, fs in os.walk(directory):
			if not d:
				for f in fs:
					files.append(os.path.join(l, f))
		return files


	def testFilesOf(directory):
		files = []
		for l, d, fs in os.walk(directory):
			if not d:
				for f in fs:
					if f.endswith('.run') or f.endswith('.conf'):
						files.append(os.path.join(l, f))
		return files


	files_definition = [
		('share/exabgp/processes', filesOf('etc/exabgp')),
		('share/exabgp/etc', testFilesOf('qa/conf')),
	]

	if platform.system() != 'NetBSD':
		if sys.argv[-1] == 'systemd':
			files_definition.append(('/usr/lib/systemd/system', filesOf('etc/systemd')))

	try:
		description_rst = open('PYPI.rst').read() % {'version': version.get()}
	except IOError:
		print('failed to open PYPI.rst')
		return 1

	if command.dryrun:
		return 1

	setup(
		name='exabgp',
		version=version.get(),
		description='BGP swiss army knife',
		long_description=description_rst,
		author='Thomas Mangin',
		author_email='thomas.mangin@exa-networks.co.uk',
		url='https://github.com/Exa-Networks/exabgp',
		license='BSD',
		keywords='BGP routing SDN FlowSpec HA',
		platforms=[get_platform(), ],
		package_dir={'': 'lib'},
		packages=packages('lib'),
		package_data={'': ['PYPI.rst']},
		download_url='https://github.com/Exa-Networks/exabgp/archive/%s.tar.gz' % version.get(),
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
	return 0


def help():
	print("""\
python3 setup.py help     this help
python3 setup.py cleanup  delete left-over file from release
python3 setup.py release  tag a new version on github, and update pypi
python3 setup.py pypi     create egg/wheel
python3 setup.py install  local installation
python3 setup.py build    local build
""")

def main ():
	if sys.argv[-1] == 'cleanup':
		sys.exit(path.remove_egg())

	if sys.argv[-1] == 'release':
		sys.exit(release_github())

	if sys.argv[-1] == 'pypi':
		sys.exit(release_pypi())

	# "internal" commands

	if sys.argv[-1] == 'version':
		sys.stdout.write("%s\n" % version.get())
		sys.exit(0)

	if sys.argv[-1] == 'current':
		sys.stdout.write("%s\n" % version.changelog())
		sys.exit(0)

	if '--help' in sys.argv or \
		'install' in sys.argv or \
		'upload' in sys.argv:
		sys.exit(st())

	if sys.argv[-1] == 'debian':
		release = version.changelog()
		debian.set(release)
		sys.exit(0)

	help()
	sys.exit(1)


if __name__ == '__main__':
	main()
