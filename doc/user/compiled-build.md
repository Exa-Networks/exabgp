# The Compiled Build (mypyc)

ExaBGP can compile its implementation with [mypyc](https://mypyc.readthedocs.io/), which
turns type-annotated Python into C extensions. The source is the same Python: nothing is
written twice, and the pure Python build remains the reference implementation.
The measured message workloads run between 1.4 and 2.4 times as fast in the compiled tree.

It is experimental and only on `main`: it is built from a git checkout or into a wheel
you build yourself, none is published to PyPI yet, and the pure Python build remains the
default.

## What is compiled

The whole implementation is compiled: BGP messages, every path attribute and NLRI family,
the RIB, protocol helpers, configuration parser, reactor and TCP connections, API processes
and encoders, CLI, application commands, logging, environment, utilities and vendored code.
The tree and wheel use the same selection in `[tool.exabgp.mypyc]` in `pyproject.toml`.

Two import-time exceptions remain in Python:

- `util/mypyc.py` supplies `trait` and `mypyc_attr` fallbacks when `mypy_extensions` is not
  installed. Mypy considers that fallback branch unreachable; compiling it would turn a
  valid runtime fallback into a crash. The module only runs at import.
- Package `__init__.py` files retain Python's package import semantics. Compiling these
  initializers lost `__path__`, causing nested imports to fail with "is not a package".

The reactor and protocol handler are no longer excluded. The earlier partial-build
measurements do not describe the current compilation scope.

## Performance

Measured on 2026-09-30 with `qa/bin/benchmark_codec` on an Apple M4 Max, macOS arm64,
Python 3.12.14 and mypyc 1.20.1. The pure and whole-package compiled trees used the same
interpreter, sequentially in the same session, with the best of seven runs. Two corpora:

- **ci**: the 144 UPDATE messages of the functional encoding tests, repeated 40 times,
  covering every address family ExaBGP supports
- **bulk**: 20 IPv4 unicast UPDATEs of 400 prefixes each, repeated three times, as a
  full table would arrive

Neither build left out any capture. These are in-process message/RIB measurements, not
server throughput or executable startup measurements.

| Stage | What it measures | ci pure (UPDATE/s) | ci compiled (UPDATE/s) | Speedup | bulk pure (prefixes/s) | bulk compiled (prefixes/s) | Speedup |
|-------|------------------|---------|-------------|---------|-----------|---------------|---------|
| decode | an UPDATE read from the wire | 27,709 | 46,569 | 1.68x | 180,476 | 415,499 | 2.30x |
| json | the JSON an API process receives | 67,485 | 128,818 | 1.91x | 389,949 | 930,404 | 2.39x |
| encode | an UPDATE packed for the wire | 57,904 | 125,742 | 2.17x | 338,715 | 483,638 | 1.43x |
| rib | routes added to the adj-rib-out and UPDATEs generated | 276,719 | 593,050 | 2.14x | 378,112 | 747,111 | 1.98x |

The figures move by a few percent from one run to the next, so read the ratios, not the
last digit. Use the same interpreter which built the extensions. To measure your own machine:

```sh
uv run python qa/bin/benchmark_codec --corpus ci --runs 7 --save /tmp/pure-ci.json
env PYTHONPATH=build/mypyc uv run python qa/bin/benchmark_codec --corpus ci --runs 7 --compare /tmp/pure-ci.json
uv run python qa/bin/benchmark_codec --corpus bulk --runs 7 --save /tmp/pure-bulk.json
env PYTHONPATH=build/mypyc uv run python qa/bin/benchmark_codec --corpus bulk --runs 7 --compare /tmp/pure-bulk.json
```

## Building

You need a git checkout of `main`, the development dependencies, which bring mypy and so
mypyc, and a C compiler with the Python headers:

| Platform | Compiler |
|----------|----------|
| Debian, Ubuntu | `apt install build-essential python3-dev` |
| RHEL, Fedora | `dnf install gcc python3-devel` |
| macOS | `xcode-select --install` |

```sh
git clone https://github.com/Exa-Networks/exabgp
cd exabgp
uv sync
./qa/bin/build_mypyc
```

`build_mypyc` copies `src/exabgp` to `build/mypyc/exabgp` and compiles the modules above
in that copy. Build time depends on the host. The source tree never holds a compiled file.

The copy is taken when you build: after a `git pull`, or any change to the source, build
again, or the compiled tree runs the old code.

## Running

`sbin/exabgp` runs the compiled tree when `EXABGP_COMPILED` is set:

```sh
env EXABGP_COMPILED=1 ./sbin/exabgp server /etc/exabgp/exabgp.conf
env EXABGP_COMPILED=1 ./sbin/exabgp decode <hex>
```

Every command works this way. The launcher runs the tree with the Python which built it,
which `build_mypyc` records: the extensions load in no other version, and another Python
would import the `.py` files beside them instead, silently running pure Python.

`exabgp version` says which one runs:

```
ExaBGP : 6.0.0-20260930+main-8768aa04e8
Python : 3.12.14 ...
Build  : mypyc
```

`Build : python` is the pure Python tree. To go back to it, drop `EXABGP_COMPILED`.

## A compiled wheel

`setup.py` compiles the same modules into the wheel when `EXABGP_MYPYC=1` is set. Without
it the wheel is the pure Python one, and needs nothing but setuptools to build:

```sh
env EXABGP_MYPYC=1 uv build --wheel --no-build-isolation   # needs mypy installed, uv sync does it
pip install dist/exabgp-6.0.0-cp312-cp312-*.whl
exabgp version                                             # Build  : mypyc
```

The wheel only installs on the Python version and platform it was built for. The
`Compiled wheels (mypyc)` workflow builds them for Python 3.12, 3.13 and 3.14 on Linux
(x86_64 and arm64) and macOS (arm64), installs each one and runs the functional suites
against it with `qa/bin/test_wheel`. The wheels are kept as build artifacts: none is
published to PyPI yet.

## One-file executable

`qa/bin/build_binary` builds ExaBGP as a single executable file, with Python, the compiled
modules and the rest of ExaBGP inside, for a host which has no Python:

```sh
uv sync
uv run ./qa/bin/build_binary
./dist/exabgp-6.0.0-darwin-arm64 version     # Build  : mypyc
```

It builds the compiled wheel from a copy of the checkout in `build/binary`, installs it in
a scratch virtual environment with PyInstaller, and runs `PyInstaller --onefile` on the
`exabgp` entry point. It then checks that every compiled extension of the wheel is in the
binary, and runs it: `version` must say `Build  : mypyc`, a route is encoded and decoded
back, `etc/exabgp/conf-ipself6.conf` is validated, and the server is started on it and
stopped with SIGTERM. `--functional` also runs the decoding, encoding, API and CLI suites
against the binary, `--test <binary>` checks one built elsewhere, and `--wheel <wheel>`
skips building the wheel.

The binary is `dist/exabgp-<version>-<system>-<machine>`: `exabgp-6.0.0-darwin-arm64`,
`exabgp-6.0.0-linux-x86_64`, `exabgp-6.0.0-linux-aarch64`. The whole-package macOS arm64
build measured here is 18.6 MiB and holds:

- the Python 3.12 interpreter and the part of the standard library ExaBGP imports
- every ExaBGP module: 348 C extensions and mypyc's shared runtime library, with the
  import-time exceptions as Python bytecode
- the port names file (`exabgp/protocol/ip/port_data.json`) and the package metadata,
  which `exabgp version` reads

`sbin/exabgp` runs a binary instead of a Python tree when `EXABGP_BINARY` names it, which is
how the functional suites are pointed at it:

```sh
env EXABGP_BINARY=$PWD/dist/exabgp-6.0.0-darwin-arm64 ./qa/bin/functional encoding --quiet
```

The `One-file binary` workflow builds the binary on Linux x86_64, Linux arm64 and macOS
arm64, then checks each one on a clean runner, the functional suites included, and keeps
it as a build artifact. None is published yet.

Its limits:

- one binary per platform: a Linux binary does not run on macOS, nor an x86_64 one on arm64
- on Linux, it only runs with a glibc at least as recent as the one it was built with. The
  workflow builds in AlmaLinux 8 (glibc 2.28), so its binaries run on RHEL 8, Debian 10,
  Ubuntu 20.04 and later. A binary built on your machine needs your machine's glibc or
  newer. musl systems (Alpine) are not covered
- on macOS, it runs on the macOS version the bundled Python targets, or later. The
  workflow uses the Python of `actions/setup-python`; a Homebrew Python targets the macOS
  it is installed on
- the API programs a configuration runs are programs of their own: the Python ones, such
  as those under `etc/exabgp/run`, still need a Python on the host. ExaBGP's own CLI
  processes run the binary itself
- a one-file binary unpacks itself into a temporary directory under `$TMPDIR` each time it
  starts, and removes it when it exits: that directory must allow running programs (not
  mounted `noexec`). Every start pays for unpacking; a long-running server pays it once.
  On the macOS arm64 host above, one `version` invocation took 8.16s wall time. The full
  binary smoke/functional run took 18m19s: all suites eventually passed, but 45/47 encoding
  and 38/42 API cases needed serial retries. The harness uses a 20s default deadline for
  the initial concurrent run. Startup contention is suspected, not established by the
  quiet logs; the installed-wheel run reported no retries. Prefer the wheel for frequent
  short-lived commands.
- a configuration path starting with `etc/exabgp` is read under the directory holding the
  binary (its parent when that is a `bin` directory), as for an installed package: give
  `./etc/exabgp/...` or an absolute path, or set `EXABGP_ROOT`

## How far it is tested

`./qa/bin/test_everything compiled` (or `./qa/bin/test_everything --all`) runs the whole
test tree and the functional suites (decoding, encoding, API, CLI) against the rebuilt
compiled tree. The stage is opt-in: a plain `./qa/bin/test_everything` skips it, and CI
covers it through the compiled wheels.
Wheel and binary verification runs those four functional suites against the installed
artifact rather than the source checkout.

The final local binary run exercised all 23 decoding, 47 encoding and 42 API cases in
batches of four, plus the CLI suite, without widening deadlines. All passed, but five API
cases needed retries: four reached the initial deadline, and `api-fast` emitted a different
UPDATE sequence before passing its retry. An earlier concurrent decoding run also had one
failure which passed alone and in the final batches. These remain verification caveats,
not claims of a diagnosed or fixed startup race; details and logs are recorded in the plan.

Not every test in a compiled run is evidence about compiled dispatch. The fault-injection
tests in `test_configuration_route_validation.py`, `test_otc_configuration_validation.py`
and `test_decode_to_api_command_paths.py` deliberately load interpreted copies: compiled
direct calls do not see their monkeypatches. These remain source-level tests; functional
configuration validation and API encode/decode round trips exercise the compiled paths.

## Known limitations

- **Memory introspection:** after an async method of a compiled class has been read,
  a mypyc GC-traversal bug can make `gc.get_referents()` raise `SystemError` and
  `gc.get_referrers()` report spurious references. The objgraph diagnostics used by
  `exabgp server --memory` can encounter it. Use the pure Python build for those
  diagnostics. The objgraph exact-backreferences test remains an expected failure in
  compiled runs; this integration does not fix the compiler bug.
- **Help descriptions:** mypyc drops module docstrings, so compiled subcommand help
  lacks the introductory module description. Usage and option help remain available.
  Moving descriptions to explicit constants is not part of this integration.
- A test which supplies a deliberately invalid route to the RIB is skipped compiled,
  because compiled argument checks reject that object. The exception-chaining test is
  also skipped compiled because mypyc does not set `__suppress_context__` for
  `raise ... from None`.
- **Python ABC introspection:** mypyc 1.20.1 can leave compiled abstract classes sharing
  ABC instance-check caches. An interpreted `isinstance()` probe can then affect a later
  probe of an unrelated compiled abstract class. Do not use Python ABC introspection to
  discover or classify compiled grammar objects.

## For contributors

The compiled build checks at run time the types the code declares, where Python only
checks them when mypy runs. A few things the interpreter accepts fail compiled:

- an argument of another type than the one declared: a `Mock`, `None` where `None` is not
  in the annotation, an `int` where an `IntValue` subclass is declared. Tests use real
  objects: `tests/negotiation.py` builds a real `Negotiated` and `Neighbor`
- a class written in a test, or anywhere not compiled, which inherits from a compiled class
- a copy through `copy.copy` or `copy.deepcopy` without `__copy__`/`__deepcopy__`: a
  compiled class can only be built through its `__init__`
- `dir()` and `globals()` at module level, which a compiled module does not have
- class constants without `ClassVar`, which mypyc reads as instance attributes
- `__eq__` without `__ne__`, and a builtin (`int`, `list`, `dict`) as a base class

`./qa/bin/test_everything compiled` builds the tree and runs the unit and functional suites
against it.
The design and the measurements are in `plan/wip-mypyc.md`.
