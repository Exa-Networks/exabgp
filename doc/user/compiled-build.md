# The Compiled Build (mypyc)

ExaBGP can compile its message code with [mypyc](https://mypyc.readthedocs.io/), which
turns type-annotated Python into C extensions. The source is the same Python: nothing is
written twice, and the pure Python tree stays the reference which every other tool runs.
The compiled tree decodes, encodes and prints BGP messages between 1.4 and 2.1 times as
fast.

It is experimental and only on `main`: it is built from a git checkout, there is no
compiled wheel yet, and the pure Python build remains the default.

## What is compiled

| Compiled | Left in Python |
|----------|----------------|
| `protocol/` (AFI, SAFI, IP addresses, FlowSpec values) | the reactor and the TCP connections |
| `bgp/message/` (OPEN, UPDATE, NOTIFICATION, KEEPALIVE, ROUTE-REFRESH, OPERATIONAL) | the configuration parser |
| every path attribute | the API processes and their encoders |
| every NLRI family (unicast, VPN, labelled, FlowSpec, EVPN, BGP-LS, MUP, MVPN, RTC, VPLS, SR Policy) | the CLI |
| `rib/` (adj-rib-in, adj-rib-out, route cache) | |

The compiled part is where the CPU goes when routes flow: every received UPDATE is
decoded, every announced route encoded, and every route an API process asks for goes
through the RIB. What stays in Python is either waiting on the network or runs once.

The TCP framing (`reactor/network/connection.py`) compiles, but reads messages only 1.2
times as fast, about 3% of the cost of receiving an UPDATE, and the protocol handler holds
an async generator, which mypyc 1.20 does not compile.

## Performance

Measured with `qa/bin/benchmark_codec` on an Apple M4 Max with Python 3.12, the pure and
compiled trees in the same session, the best of seven runs. Two corpora:

- **ci**: the 144 UPDATE messages of the functional encoding tests, repeated 40 times,
  covering every address family ExaBGP supports
- **bulk**: 20 IPv4 unicast UPDATEs of 400 prefixes each, repeated three times, as a
  full table would arrive

| Stage | What it measures | ci pure | ci compiled | | bulk pure | bulk compiled | |
|-------|------------------|---------|-------------|---|-----------|---------------|---|
| decode | an UPDATE read from the wire | 27,662 /s | 45,087 /s | 1.63x | 180,400 prefixes/s | 353,200 prefixes/s | 1.96x |
| json | the JSON an API process receives | 66,611 /s | 97,844 /s | 1.47x | 391,600 prefixes/s | 752,400 prefixes/s | 1.92x |
| encode | an UPDATE packed for the wire | 58,603 /s | 125,363 /s | 2.14x | 340,800 prefixes/s | 480,400 prefixes/s | 1.41x |
| rib | routes added to the adj-rib-out and UPDATEs generated | 276,831 /s | 548,452 /s | 1.98x | 370,400 prefixes/s | 671,200 prefixes/s | 1.81x |

The figures move by a few percent from one run to the next, so read the ratios, not the
last digit. To measure your own machine:

```sh
./qa/bin/benchmark_codec --save /tmp/pure.json
env PYTHONPATH=build/mypyc ./qa/bin/benchmark_codec --compare /tmp/pure.json
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
in that copy, which takes a minute or two. The source tree never holds a compiled file.

The copy is taken when you build: after a `git pull`, or any change to the source, build
again, or the compiled tree runs the old code.

## Running

`sbin/exabgp` always runs the Python tree. Run the compiled one with `python -m exabgp`,
from the root of the checkout:

```sh
export EXABGP_ROOT=$PWD
env PYTHONPATH=build/mypyc .venv/bin/python -m exabgp server /etc/exabgp/exabgp.conf
env PYTHONPATH=build/mypyc .venv/bin/python -m exabgp decode <hex>
```

Every command works this way. `EXABGP_ROOT` is what `sbin/exabgp` sets for you: without it
ExaBGP looks for its environment file and creates its CLI socket inside `build/mypyc`,
where the socket path is too long to create on macOS. Use the interpreter of the
environment you built with (`.venv/bin/python` after `uv sync`): the extensions only load
in the Python version which compiled them.

To check which tree is running:

```sh
env PYTHONPATH=build/mypyc .venv/bin/python -c "import exabgp.bgp.message.update.nlri.inet as m; print(m.__file__)"
```

A path ending in `.so` is the compiled module, one ending in `.py` the Python one. To go
back to Python, drop `PYTHONPATH`, or use `sbin/exabgp` again.

## How far it is tested

The whole unit test suite runs against the compiled tree and passes, one test excepted,
which builds a route the compiled RIB refuses by design. `./qa/bin/test_everything` runs it
as its `compiled` stage. The functional suites (encoding, decoding, API) have not yet run
against it, because they start ExaBGP through `sbin/exabgp`. Until they do, run the
compiled build beside a pure one before trusting it in production.

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

`./qa/bin/test_everything compiled` builds and runs the suite against the compiled tree.
The design and the measurements are in `plan/wip-mypyc.md`.
