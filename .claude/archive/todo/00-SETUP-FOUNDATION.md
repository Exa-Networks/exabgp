# Phase 0: Foundation Setup

**Estimated Time**: 2-3 hours
**Priority**: CRITICAL - Must complete before other tasks

---

## Task 0.1: Add Testing Dependencies

**File**: `/home/user/exabgp/pyproject.toml`

**What to do**:
1. Open `pyproject.toml`
2. Locate the `[tool.uv]` section with `dev-dependencies`
3. Add these new dependencies:

```toml
[tool.uv]
dev-dependencies = [
    "ruff",
    "pytest",
    "pytest-cov",
    "coveralls",
    "psutil",
    "hypothesis>=6.0",         # NEW: Property-based testing/fuzzing
    "pytest-benchmark>=4.0",   # NEW: Performance benchmarking
    "pytest-xdist>=3.0",       # NEW: Parallel test execution
    "pytest-timeout>=2.0",     # NEW: Timeout protection for tests
]
```

**Acceptance Criteria**:
- [ ] All 4 new dependencies added
- [ ] Version constraints specified (>=)
- [ ] File saved

**Verification**:
```bash
cd /home/user/exabgp
uv pip install -e ".[dev]"
python -c "import hypothesis; import pytest_benchmark; print('Success!')"
```

---

## Task 0.2: Update Coverage Configuration

**File**: `/home/user/exabgp/.coveragerc`

**What to do**:
1. Open `.coveragerc`
2. Find the `[run]` section
3. Add branch coverage tracking:

```ini
[run]
branch = True  # Track branch coverage, not just line coverage
omit =
    */python?.?/*
    dist-packages/*
    usr/*
    /qa/*
    /dev/*
    /debian/*
    /systemd/*
    */__init__.py
```

4. Find the `[report]` section
5. Add coverage thresholds:

```ini
[report]
fail_under = 70           # Fail if coverage below 70%
show_missing = True
skip_covered = False
exclude_lines =
    pragma: no cover
    ^\s*pass\s*$
    ^\s*\.\.\.\s*$
    def __repr__
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @(abc\.)?abstractmethod
```

**Acceptance Criteria**:
- [ ] `branch = True` added to `[run]`
- [ ] `fail_under = 70` added to `[report]`
- [ ] `show_missing = True` added
- [ ] File saved

**Verification**:
```bash
env PYTHONPATH=src pytest --cov --cov-report=term ./tests/cache_test.py
# Should show branch coverage in output
```

---

## Task 0.3: Create Test Directory Structure

**What to do**:
```bash
cd /home/user/exabgp/tests
mkdir -p fuzz
mkdir -p integration
mkdir -p performance
mkdir -p security
mkdir -p regression
```

**Create `.gitkeep` files**:
```bash
touch tests/fuzz/.gitkeep
touch tests/integration/.gitkeep
touch tests/performance/.gitkeep
touch tests/security/.gitkeep
touch tests/regression/.gitkeep
```

**Acceptance Criteria**:
- [ ] 5 new directories created under `tests/`
- [ ] Each has a `.gitkeep` file
- [ ] Directory structure matches plan

**Verification**:
```bash
ls -la tests/fuzz tests/integration tests/performance tests/security tests/regression
```

---

## Task 0.4: Create Fuzzing Conftest

**File**: `/home/user/exabgp/tests/fuzz/conftest.py`

**What to do**:
Create a pytest configuration file for fuzzing tests:

```python
"""Pytest configuration for fuzzing tests."""
import pytest
from hypothesis import settings, HealthCheck

# Configure Hypothesis for fuzzing
settings.register_profile(
    "ci",
    max_examples=100,
    deadline=1000,
    suppress_health_check=[HealthCheck.too_slow],
)

settings.register_profile(
    "dev",
    max_examples=50,
    deadline=500,
)

settings.register_profile(
    "extensive",
    max_examples=10000,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)

# Use dev profile by default
settings.load_profile("dev")


@pytest.fixture
def negotiated():
    """Fixture providing a mock negotiated capabilities object."""
    from exabgp.bgp.message.open.capability.negotiated import Negotiated
    return Negotiated(None)


@pytest.fixture
def direction():
    """Fixture providing message direction."""
    from exabgp.bgp.message.direction import Direction
    return Direction.IN
```

**Acceptance Criteria**:
- [ ] File created at correct path
- [ ] Three Hypothesis profiles configured
- [ ] Fixtures for `negotiated` and `direction` added
- [ ] File saved

**Verification**:
```bash
python -c "import sys; sys.path.insert(0, 'tests/fuzz'); import conftest; print('Success!')"
```

---

## Task 0.5: Create Test Utilities Module

**File**: `/home/user/exabgp/tests/unit/helpers.py`

**What to do**:
Create a shared utilities module:

```python
"""Shared test utilities and helpers."""

def create_bgp_header(length, msg_type):
    """Create a BGP message header.

    Args:
        length: Message length (19-4096)
        msg_type: Message type (1-5)

    Returns:
        bytes: BGP header (19 bytes)
    """
    marker = b'\xFF' * 16
    length_bytes = length.to_bytes(2, 'big')
    type_byte = bytes([msg_type])
    return marker + length_bytes + type_byte


def create_update_message(withdrawn_routes=b'', attributes=b'', announced_routes=b''):
    """Create a BGP UPDATE message.

    Args:
        withdrawn_routes: Withdrawn routes (prefixed with 2-byte length)
        attributes: Path attributes (prefixed with 2-byte length)
        announced_routes: Announced routes

    Returns:
        bytes: Complete UPDATE message with header
    """
    withdrawn_len = len(withdrawn_routes).to_bytes(2, 'big')
    attr_len = len(attributes).to_bytes(2, 'big')

    body = withdrawn_len + withdrawn_routes + attr_len + attributes + announced_routes
    header = create_bgp_header(19 + len(body), 2)  # Type 2 = UPDATE

    return header + body


def create_open_message(asn=65000, holdtime=180, router_id='192.0.2.1', capabilities=b''):
    """Create a BGP OPEN message.

    Args:
        asn: AS number
        holdtime: Hold time in seconds
        router_id: Router ID as string
        capabilities: Optional capabilities

    Returns:
        bytes: Complete OPEN message with header
    """
    import struct

    version = b'\x04'  # BGP-4
    asn_bytes = asn.to_bytes(2, 'big')
    holdtime_bytes = holdtime.to_bytes(2, 'big')
    router_id_bytes = bytes(map(int, router_id.split('.')))

    opt_param_len = len(capabilities)
    if opt_param_len > 0:
        opt_param_len += 2  # Include type and length bytes

    body = version + asn_bytes + holdtime_bytes + router_id_bytes
    body += bytes([opt_param_len])

    if capabilities:
        body += b'\x02'  # Parameter type: Capabilities
        body += bytes([len(capabilities)])
        body += capabilities

    header = create_bgp_header(19 + len(body), 1)  # Type 1 = OPEN
    return header + body


class ExpectedException(Exception):
    """Base class for expected exceptions in tests."""
    pass


def assert_clean_error(func, *args, **kwargs):
    """Assert that a function raises only expected exceptions.

    Args:
        func: Function to call
        *args: Positional arguments
        **kwargs: Keyword arguments

    Raises:
        AssertionError: If unexpected exception raised
    """
    from exabgp.bgp.message import Notify

    expected_exceptions = (
        Notify,
        ValueError,
        KeyError,
        IndexError,
        TypeError,
        struct.error,
    )

    try:
        func(*args, **kwargs)
    except expected_exceptions:
        # This is fine - these are expected error conditions
        pass
    except Exception as e:
        # Unexpected exception type
        raise AssertionError(
            f"Unexpected exception: {type(e).__name__}: {e}\n"
            f"Expected one of: {[e.__name__ for e in expected_exceptions]}"
        )
```

**Acceptance Criteria**:
- [ ] File created with all helper functions
- [ ] Functions documented with docstrings
- [ ] `assert_clean_error` utility added
- [ ] File saved

**Verification**:
```bash
python -c "import sys; sys.path.insert(0, 'tests'); from helpers import create_bgp_header; print(create_bgp_header(19, 1).hex())"
```

---

## Task 0.6: Update pytest.ini Configuration

**File**: `/home/user/exabgp/pytest.ini` (create if doesn't exist)

**What to do**:
Create or update pytest configuration:

```ini
[pytest]
testpaths = tests
python_files = *_test.py test_*.py fuzz_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
    --hypothesis-show-statistics

markers =
    fuzz: Fuzzing tests using Hypothesis
    integration: Integration tests requiring multiple components
    performance: Performance and benchmark tests
    security: Security-focused tests
    slow: Tests that take significant time

# Timeout for tests (prevent infinite loops)
timeout = 30
timeout_method = thread

# Coverage settings
[coverage:run]
source = src/exabgp
branch = True

[coverage:report]
precision = 2
show_missing = True
skip_covered = False
```

**Acceptance Criteria**:
- [ ] File created or updated
- [ ] Test markers defined
- [ ] Timeout configured
- [ ] Coverage paths set
- [ ] File saved

**Verification**:
```bash
pytest --markers | grep -E "(fuzz|integration|performance|security)"
```

---

## Task 0.7: Create README for Test Directory

**File**: `/home/user/exabgp/tests/README.md`

**What to do**:
Create documentation for test organization:

```markdown
# ExaBGP Test Suite

## Directory Structure

```
tests/
├── *_test.py              # Unit tests (existing)
├── fuzz/                  # Fuzzing tests (Hypothesis)
├── integration/           # Integration tests
├── performance/           # Performance benchmarks
├── security/              # Security-focused tests
├── regression/            # Regression tests for bug fixes
└── helpers.py             # Shared test utilities
```

## Running Tests

### All Tests
```bash
env PYTHONPATH=src pytest
```

### Specific Category
```bash
# Unit tests only
env PYTHONPATH=src pytest tests/unit/*_test.py

# Fuzzing tests
env PYTHONPATH=src pytest tests/fuzz/ -m fuzz

# Integration tests
env PYTHONPATH=src pytest tests/unit/ -m integration

# Performance benchmarks
env PYTHONPATH=src pytest tests/unit/ --benchmark-only
```

### With Coverage
```bash
env PYTHONPATH=src pytest --cov --cov-report=html
# Open htmlcov/index.html to view coverage report
```

### Parallel Execution
```bash
env PYTHONPATH=src pytest -n auto
```

## Fuzzing Profiles

Configure fuzzing intensity with environment variable:

```bash
# Fast (50 examples)
env HYPOTHESIS_PROFILE=dev pytest tests/fuzz/

# CI (100 examples)
env HYPOTHESIS_PROFILE=ci pytest tests/fuzz/

# Extensive (10,000 examples)
env HYPOTHESIS_PROFILE=extensive pytest tests/fuzz/
```

## Writing Tests

### Unit Test Example
```python
import unittest
from exabgp.bgp.message import Message

class TestMyFeature(unittest.TestCase):
    def test_basic_case(self):
        result = Message.do_something()
        self.assertEqual(result, expected)
```

### Fuzzing Test Example
```python
import pytest
from hypothesis import given, strategies as st

@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=4096))
def test_parser_never_crashes(data):
    try:
        parse_message(data)
    except (ValueError, KeyError):
        pass  # Expected errors
```

## Test Markers

Use pytest markers to categorize tests:

- `@pytest.mark.fuzz` - Fuzzing tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.performance` - Performance tests
- `@pytest.mark.security` - Security tests
- `@pytest.mark.slow` - Slow tests (skip in quick runs)

Run specific markers:
```bash
pytest -m fuzz           # Only fuzzing tests
pytest -m "not slow"     # Skip slow tests
```
```

**Acceptance Criteria**:
- [ ] File created with comprehensive documentation
- [ ] Examples for each test type included
- [ ] Running instructions clear
- [ ] File saved

**Verification**:
```bash
cat tests/README.md | grep -E "(Directory Structure|Running Tests)"
```

---

## Task 0.8: Commit Foundation Changes

**What to do**:
```bash
cd /home/user/exabgp
git add pyproject.toml .coveragerc pytest.ini
git add tests/fuzz tests/integration tests/performance tests/security tests/regression
git add tests/unit/helpers.py tests/README.md
git add tests/fuzz/conftest.py

git commit -m "Set up testing foundation infrastructure

- Add Hypothesis, pytest-benchmark, pytest-xdist, pytest-timeout
- Configure coverage for branch tracking and 70% threshold
- Create test directory structure (fuzz, integration, performance, security, regression)
- Add fuzzing conftest with Hypothesis profiles
- Create shared test helpers and utilities
- Configure pytest with markers and settings
- Document test organization and usage"
```

**Acceptance Criteria**:
- [ ] All new files staged
- [ ] Descriptive commit message
- [ ] Committed successfully

**Verification**:
```bash
git log -1 --stat
git status
```

---

## Completion Checklist

- [ ] Task 0.1: Dependencies added to pyproject.toml
- [ ] Task 0.2: Coverage configuration updated
- [ ] Task 0.3: Test directories created
- [ ] Task 0.4: Fuzzing conftest created
- [ ] Task 0.5: Test helpers module created
- [ ] Task 0.6: pytest.ini configured
- [ ] Task 0.7: Test README documented
- [ ] Task 0.8: Changes committed

**Estimated Total Time**: 2-3 hours
**Next File**: `01-FUZZ-MESSAGE-HEADER.md`
