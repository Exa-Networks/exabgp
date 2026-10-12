# The zipapp

The zipapp is ExaBGP in a single file, `exabgp.pyz`, which you download and run with
Python. There is nothing to install: no pip, no virtual environment, no git checkout.

## What a zipapp is

A zipapp is a zip archive of Python code with a `__main__.py` at its root. Python has been
able to run one since 2.6: give it the archive instead of a script, and it imports the code
straight from the zip, without unpacking anything. The format is documented with Python's
[zipapp module](https://docs.python.org/3/library/zipapp.html), which is also what builds
it.

`exabgp.pyz` holds the same files as the pure Python wheel `pip install` uses: the
`exabgp` package and its metadata, so `version` reports the version of the file itself.
The file starts with a `#!/usr/bin/env python3` line, which zip tools ignore, so it can be
made executable and run like any other program.

ExaBGP has no dependencies outside the standard library, so the zipapp needs nothing but
the interpreter. Being pure Python, the same file runs on Linux, macOS and the BSDs, on any
CPU. The catch is that it needs Python 3.12 or later on the host. Should your system
Python be older, use the [one-file binary](compiled-build.md), which carries its own
Python, or the container.

## Where to get it

| What | URL |
|------|-----|
| main, rebuilt each night the code changed | https://github.com/Exa-Networks/exabgp/releases/download/nightly/exabgp.pyz |
| the latest release | https://github.com/Exa-Networks/exabgp/releases/latest/download/exabgp.pyz |
| a given release | https://github.com/Exa-Networks/exabgp/releases/download/6.0.0/exabgp-6.0.0.pyz |

The nightly is the code of `main` on that day, after the functional tests passed against
the zipapp itself. It is not a release: use it to try a fix or a feature before it is
released, or when we ask you to check if a problem is still there.

Every release has a zipapp from 6.0.0 and from 5.0.14 onwards. The 5.0 one runs on Python
3.8 or later. Until 6.0.0 is out, the latest release is a 5.0 one; afterwards, it is always
the newest 6.x release, even when a 5.0 release is made after it.

Every release and the nightly carry a `SHA256SUMS` file:

```sh
curl -LO https://github.com/Exa-Networks/exabgp/releases/download/nightly/exabgp.pyz
curl -LO https://github.com/Exa-Networks/exabgp/releases/download/nightly/SHA256SUMS
sha256sum --ignore-missing -c SHA256SUMS    # shasum -a 256 --ignore-missing -c SHA256SUMS on macOS
```

The `SHA256SUMS` of a release also lists `exabgp-<version>.pyz`: `--ignore-missing` checks the
files you downloaded and skips the others.

## Running it

Give the file to Python, followed by the same arguments as the `exabgp` command:

```sh
python3 exabgp.pyz version
python3 exabgp.pyz configuration validate /etc/exabgp/exabgp.conf
python3 exabgp.pyz server /etc/exabgp/exabgp.conf
python3 exabgp.pyz healthcheck --help
```

If `python3` is not 3.12 or later, name the interpreter which is (`python3.12 exabgp.pyz
...`). An older Python stops straight away and says so.

You can also make it a command. Copied to a directory of your `PATH` without its
extension, it is used exactly like an installed `exabgp`:

```sh
install -m 755 exabgp.pyz /usr/local/bin/exabgp
exabgp version
```

The `version` output names the file in use on its `From` line, which is the quickest way to
check you are running the zipapp and not another ExaBGP installed on the machine.

## Configuration and environment

ExaBGP looks for its environment file relative to where the program is: for a zipapp in
`/usr/local/bin`, that is `/usr/local/etc/exabgp/exabgp.env`. Set `EXABGP_ENVFILE` to use
another file, or set the values as environment variables (`exabgp env` lists them all).

The example configurations which `pip` installs under `etc/exabgp/examples` are not in the
zipapp. They are in the repository, under
[etc/exabgp](https://github.com/Exa-Networks/exabgp/tree/main/etc/exabgp).

Programs started by a `process` section run on their own: a helper written in Python needs
its own interpreter, the zipapp does not lend it one. To use the healthcheck which comes
with ExaBGP, run it from the zipapp:

```
process watch-service {
	run /usr/bin/python3 /usr/local/bin/exabgp healthcheck --cmd "curl -sf http://127.0.0.1/";
	encoder text;
}
```

## As a service

A systemd unit only needs to point at the file:

```ini
[Service]
ExecStart=/usr/bin/python3 /usr/local/bin/exabgp server /etc/exabgp/exabgp.conf
```

When ExaBGP is started as root and drops its privileges (`exabgp.daemon.user`), that user
must be able to read the zipapp and enter every directory above it, as it reads modules
from it after the drop. ExaBGP checks this before dropping, and refuses to start rather than
fail later.

## Building it yourself

From a checkout, with `uv sync` done:

```sh
uv run ./release binary                 # builds and checks dist/exabgp-<version>.pyz
uv run ./release binary --functional    # also runs the functional suites against it
uv run ./release binary -d exabgp.pyz   # uncompressed, starting with the debug options on
```

The zipapps on GitHub are built and published by `.github/workflows/zipapp.yml`.
