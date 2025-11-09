# CRUSH Guidelines

## Development Commands

# Run all unit tests with coverage
env PYTHONPATH=src exabgp_log_enable=false pytest --cov --cov-reset ./tests/*_test.py

# Run single unit test by name or path
env PYTHONPATH=src exabgp_log_enable=false pytest ./tests/<module>_test.py::TestClass::test_method

# Run configuration parsing tests
./qa/bin/functional parsing

# Run functional encoding tests
./qa/bin/functional encoding --list
./qa/bin/functional encoding <letter>

# Run functional decoding tests
./qa/bin/functional decoding --list
./qa/bin/functional decoding <letter>

# Build package
python3 setup.py sdist bdist_wheel

# Lint & format
ruff . --fix

## Code Style

- Follow PEP8: 120-char max, single quotes for strings
- Imports: stdlib first, blank line, 3rd-party, blank line, local
- Type hints for public APIs; use `typing` only when needed
- Naming: snake_case for functions/vars, PascalCase for classes
- Exceptions: subclass `Exception`; raise custom errors with clear msgs
- Logging: use `exabgp.logger` utilities, avoid prints

## Project Rules

- No `.cursor` or Copilot rules detected
- Ignore `.crush/` artifacts via `.gitignore`
