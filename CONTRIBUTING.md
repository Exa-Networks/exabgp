# Contributing to ExaBGP

Thank you for helping us! 

We want to make contributing to this project as easy as possible, whether it's:
- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## We Develop with Github

We use github to host code, to track issues and feature requests, as well as accept pull requests.

Due to the low number of external contribution,The development is mostly done directly on master without carring too much about git history.
We will review all code changes sent via Pull Requests and welcome them:

1. Fork the repo and create your branch from `master`.
2. If you've added code that should be tested, add tests.
4. Ensure the test suite passes.
   ./qa/bin/functional run
   ./qa/bin/parsing
   env exabgp_log_enable=false nosetests --with-coverage ./qa/tests/*_test.py
   env exabgp_tcp_bind='' ./sbin/exabgp ./etc/exabgp/api-open.conf --decode FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:003C:02:0000001C4001010040020040030465016501800404000000C840050400000064000000002001010101
5. Make sure your code is formated with black (black -S -l 130).
3. If you've changed APIs, update the documentation.
6. Issue that pull request!

## License

By contributing, you agree that your contributions will be licensed under the BSD License.
We do not ask for transfer of ownership.

In short, when you submit code changes, your submissions are understood to be under the same 
[BSD License](https://github.com/Exa-Networks/exabgp/blob/master/LICENCE.txt) that covers the project and it remains your.

## Report bugs using Github's [issues](https://github.com/Exa-Networks/exabgp/issues/new/choose)

We use GitHub issues to track bugs and feature requests.

## Write bug reports with detail, and full logs

Please, please, do provide a full output of "exabgp -d", if you do not we are unlikely to be able to help you.
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

## Use a Consistent Coding Style

We format the code using black
```
black -S -l 130
```

## References
This document was adapted from this [guideline](https://gist.githubusercontent.com/briandk/3d2e8b3ec8daf5a27a62/raw/8bc29dd83d0f7cc2d31f8c6741e787c95abb6497/CONTRIBUTING.md)
