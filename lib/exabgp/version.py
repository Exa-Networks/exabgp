import os

commit = "e21a59d0"
release = "4.2.16"
json = "4.0.1"
text = "4.0.1"
version = os.environ.get('EXABGP_VERSION',release)

# Do not change the first line as it is parsed by scripts

if __name__ == '__main__':
    import sys
    sys.stdout.write(version)
