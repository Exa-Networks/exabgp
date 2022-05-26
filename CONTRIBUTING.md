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

The latest code is available directly on master.

We will review all code changes sent via Pull Requests and welcome them. There is no strong convention for git commits due to the low number of external contributions.

To contribute:

1. Fork the repo and create your branch from `master`.
2. If you've added code that should be tested, please consider adding tests.
3. Ensure the test suite passes. You can run it locally (see below)
4. If you've changed APIs, please update the documentation.
5. Make sure your code is formatted with black (see below)
6. Issue the pull request!

## License

By contributing, you agree that your contributions will be licensed under the BSD License.
We do not ask for transfer of ownership.

In short, when you submit code changes, your submissions are understood to be under the same
[BSD License](https://github.com/Exa-Networks/exabgp/blob/master/LICENCE.txt) that covers the project
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

```
./qa/bin/functional encoding
./qa/bin/parsing
env exabgp_log_enable=false pytest --with-coverage ./tests/*_test.py
env exabgp_tcp_bind='' ./sbin/exabgp ./etc/exabgp/api-open.conf --decode FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:003C:02:0000001C4001010040020040030465016501800404000000C840050400000064000000002001010101
```

using master, more options are available: only decoding nlri for example:
```
./sbin/exabgp decode --nlri etc/exabgp/conf-bgpls.conf "00 02 FF FF 03 00 00 00 00 00 00 00 00 01 00 00 20 02 00 00 04 00 00 00 01 02 01 00 04 c0 a8 7a 7e 02 02 00 04 00 00 00 00 02 03 00 04 0a 0a 0a 0a 01 01 00 20 02 00 00 04 00 00 00 01 02 01 00 04 c0 a8 7a 7e 02 02 00 04 00 00 00 00 02 03 00 04 0a 02 02 02"
{ "ls-nlri-type": "bgpls-link", "l3-routing-topology": 0, "protocol-id": 3, "local-node-descriptors": { "autonomous-system": 1, "bgp-ls-identifier": "3232266878", "ospf-area-id": "0.0.0.0", "router-id": "10.10.10.10" }, "remote-node-descriptors": { "autonomous-system": 1, "bgp-ls-identifier": "3232266878", "ospf-area-id": "0.0.0.0", "router-id": "10.2.2.2" }, "interface-address": {  }, "neighbor-address": {  } }
```


## Coding Style

Really coding style is not something we really have strong opinion but to make things consistent, we format the code using black once in while with:
```
black -S -l 120
```

## References

This document was adapted from this [guideline](https://gist.githubusercontent.com/briandk/3d2e8b3ec8daf5a27a62/raw/8bc29dd83d0f7cc2d31f8c6741e787c95abb6497/CONTRIBUTING.md)
