import os
import sys

commit = "078e4ef2"
release = "5.0.0"
json = "5.0.0"
text = "5.0.0"
version = os.environ.get('exabgp_version',release)

# Do not change the first line as it is parsed by scripts

if sys.version_info.major < 3:
    sys.exit('exabgp requires python3.6 or later')
if (sys.version_info.major == 3 and sys.version_info.minor < 6):
    sys.exit('exabgp requires python3.6 or later')

if __name__ == '__main__':
    sys.stdout.write(version)
