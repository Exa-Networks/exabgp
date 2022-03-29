import os

commit = "99de31e8"
release = "master"
json = "5.0.0"
text = "5.0.0"
version = os.environ.get('EXABGP_VERSION', release)

# Do not change the first line as it is parsed by scripts

if __name__ == '__main__':
    import sys

    sys.stdout.write(version)
