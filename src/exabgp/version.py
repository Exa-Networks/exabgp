import os
import sys

commit = "99de31e8"
release = "master"
json = "5.0.0"
text = "5.0.0"
version = os.environ.get('EXABGP_VERSION', release)

# Do not change the first line as it is parsed by scripts

if sys.version_info.major < 3:
    sys.exit('exabgp requires python3.7 or later')
if (sys.version_info.major == 3 and sys.version_info.minor < 7):
    sys.exit('exabgp requires python3.7 or later')

if __name__ == '__main__':
    sys.stdout.write(version)
