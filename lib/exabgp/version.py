import os

release = "4.0.0"
json = "3.5.0"
text = "3.5.0"
version = os.environ.get('EXABGP_VERSION',release)

# Do not change the first line as it is parsed by scripts


if __name__ == '__main__':
	import sys
	sys.stdout.write(version)
