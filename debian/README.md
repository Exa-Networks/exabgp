# Packaging for Debian

The packaging for Debian has been removed from this branch. It is now
located in the `debian/sid` branch.

## Released versions

You can get a specific version by using a tagged release:

    git tag | grep debian/

To build such a release, you can use the following commands:

    sudo apt install build-essential devscripts fakeroot
    git checkout debian/sid/4.0.2
    rm debian/source/format
    rm -rf debian/patches
    mk-build-deps \
        -t 'sudo apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -qqy' \
        -i -r debian/control
    dpkg-buildpackage -us -uc -b

You should get a set of packages. You can install them with:

    dpkg -i ../exabgp*deb ../python3-exabgp*deb
    apt install -f

## Unreleased versions

To build a package for a specific unreleased version, use the
following commands:

    sudo apt install build-essential devscripts fakeroot
    git checkout main
    git checkout debian/sid -- debian
    rm debian/source/format
    rm -rf debian/patches
    mk-build-deps \
        -t 'sudo apt-get -o Debug::pkgProblemResolver=yes --no-install-recommends -qqy' \
        -i -r debian/control
    dch -bv $(git describe --tags)-0 "Custom release."
    dpkg-buildpackage -us -uc -b

You will get a set of packages similar to the ones in the previous
step but for the current branch.
