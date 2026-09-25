# Contributing to ExaBGP

Thank you for helping us!

We want to make contributing to this project as easy as possible, whether it's:
- Reporting a bug
- Submitting a fix/patch
- Proposing new features
- Discussing the current state of the code
- Becoming a maintainer

## We Develop with Github

We use github to host code, to track issues and feature requests. We accept pull requests but may request some changes before we pull them.

The latest code is available directly on the main branch.

We will review all code changes sent via Pull Requests and welcome them. There is no strong convention for git commits due to the low number of external contributions.

To contribute:

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, please consider adding tests.
3. Ensure the test suite passes. You can run it locally (see below)
4. If you've changed APIs, please update the documentation.
5. Make sure your code is formatted with black (see below)
6. Issue the pull request!

## License

By contributing, you agree that your contributions will be licensed under the BSD License.
We do not ask for transfer of ownership.

In short, when you submit code changes, your submissions are understood to be under the same
[BSD License](https://github.com/Exa-Networks/exabgp/blob/main/LICENCE.txt) that covers the project
and the copyright remains yours (or your employer).

## Report bugs using Github's [issues](https://github.com/Exa-Networks/exabgp/issues/new/choose)

We use GitHub issues to track bugs and feature requests.

## Write bug reports with detail, and full logs

Please, please, do provide a full output of `exabgp -d`: if you do not we are unlikely to be able to help you.

Please keep in mind that we are using our "free" time to support the software.

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough and clear bug reports. It make a big difference.

## Code testing

### Machine prerequisites

The suite has to be both ends of a BGP session, so it needs a second local address to be the
far end with: `qa/bin/check_reload_cleanup` connects to the daemon from `127.0.0.2`.

On Linux the whole of `127.0.0.0/8` belongs to the loopback already and there is nothing to do.
On macOS `lo0` only answers to `127.0.0.1`, so add the alias:

```
sudo ifconfig lo0 alias 127.0.0.2 up
```

macOS forgets that on reboot, so it has to be run again after a restart. On a BSD the
equivalent is `sudo ifconfig lo0 alias 127.0.0.2 netmask 255.0.0.0`.

`./qa/bin/test_everything` checks this before it starts anything and refuses to run without
it, rather than letting the stage which needs it stand down and report a green suite which
never tested that code.

### Running the tests

```
./qa/bin/functional encoding
./qa/bin/parsing
env exabgp_log_enable=false pytest --with-coverage ./tests/unit/*_test.py ./tests/fuzz/*_test.py
env exabgp_tcp_bind='' ./sbin/exabgp ./etc/exabgp/api-open.conf --decode FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:003C:02:0000001C4001010040020040030465016501800404000000C840050400000064000000002001010101
```

using `main`, more options are available: only decoding nlri for example:
```
./sbin/exabgp decode --nlri etc/exabgp/conf-bgpls.conf "00 02 FF FF 03 00 00 00 00 00 00 00 00 01 00 00 20 02 00 00 04 00 00 00 01 02 01 00 04 c0 a8 7a 7e 02 02 00 04 00 00 00 00 02 03 00 04 0a 0a 0a 0a 01 01 00 20 02 00 00 04 00 00 00 01 02 01 00 04 c0 a8 7a 7e 02 02 00 04 00 00 00 00 02 03 00 04 0a 02 02 02"
{ "ls-nlri-type": "bgpls-link", "l3-routing-topology": 0, "protocol-id": 3, "local-node-descriptors": { "autonomous-system": 1, "bgp-ls-identifier": "3232266878", "ospf-area-id": "0.0.0.0", "router-id": "10.10.10.10" }, "remote-node-descriptors": { "autonomous-system": 1, "bgp-ls-identifier": "3232266878", "ospf-area-id": "0.0.0.0", "router-id": "10.2.2.2" }, "interface-address": {  }, "neighbor-address": {  } }
```


## RFC compliance

A change to the protocol code is held to the requirement ledgers under `qa/rfc/`, which
`./qa/bin/test_everything` checks. They hold one entry per normative sentence of the RFCs
ExaBGP implements, quoted verbatim, with what we do about it and which tests prove it;
`qa/rfc/README.md` explains how to add one and `qa/bin/check_rfc_compliance` is the gate.

Three things are worth knowing before you write an entry. Every quote is verified against
the RFC as published, held in `qa/rfc/text/`, so a requirement the document does not
contain cannot be committed, whatever wrote it. A MUST wants a test on both sides, because
a decoder which accepts everything passes every positive test ever written. And "we do not
do this" is a first class answer with a mandatory reason, either `not-applicable` for an
obligation which never bound ExaBGP or `gap` for one we owe and do not meet.

`doc/RFC_COMPLIANCE.md` is the published table and is generated by
`./qa/bin/check_rfc_compliance --markdown`. Do not edit it by hand: edit the ledger and
regenerate.

## Type checking

`main` (the 6.0 line) is held to `mypy --strict` across the whole of `src/`, and
`./qa/bin/test_everything` will not pass with an error in it:

```
uv run mypy --strict src/exabgp/
```

That is a property of this branch only. The 5.0 branch is not annotated and
`mypy --strict` reports thousands of errors there, spread across the tree rather
than caused by one import, so it gives no usable signal and is not a gate. Do
not read a clean run here as evidence about 5.0, and do not try to make 5.0 pass
as a side effect of a backport: annotating it is its own piece of work, far
larger than any fix being carried across.

## Coding Style

Really coding style is not something we really have strong opinion but to make things consistent, we format the code using black once in while with:
```
black -S -l 120
```

## References

This document was adapted from this [guideline](https://gist.githubusercontent.com/briandk/3d2e8b3ec8daf5a27a62/raw/8bc29dd83d0f7cc2d31f8c6741e787c95abb6497/CONTRIBUTING.md)
