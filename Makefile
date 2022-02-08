PYTHON_CMD ?= python3
PIP_CMD ?= pip3

# set local bin in PATH for poetry
export PATH := $(HOME)/.local/bin:$(PATH)

all: init fmt syntax test build clean

# lists all available targets
list:
	@sh -c "$(MAKE) -p no_targets__ | \
		awk -F':' '/^[a-zA-Z0-9][^\$$#\/\\t=]*:([^=]|$$)/ {\
			split(\$$1,A,/ /);for(i in A)print A[i]\
		}' | grep -v '__\$$' | grep -v 'make\[1\]' | grep -v 'Makefile' | sort"

# required for list
no_targets__:

init:
	@echo "Target init"
	$(PIP_CMD) show -q poetry || $(PIP_CMD) install --user poetry
	poetry install
	poetry version --no-ansi
	touch init

fmt:
	@echo "Target fmt"
	poetry run black src tests

poetry.lock:
	@echo "Target poetry.lock"
	poetry lock
	poetry version --no-ansi

test: poetry.lock
	@echo "Target test"
	./qa/bin/parsing
	./qa/bin/functional run
	./sbin/exabgp decode ./etc/exabgp/api-open.conf FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF:003C:02:0000001C4001010040020040030465016501800404000000C840050400000064000000002001010101
	env exabgp_log_enable=false nosetests --with-coverage ./tests/*_test.py

syntax: poetry.lock
	@echo "Target syntax"
	# stop the build if there are Python syntax errors or undefined names
	poetry run flake8 . --exclude src/exabgp/vendoring/ --exclude build/ --count --select=E9,F63,F7,F82 --show-source --statistics

extra_syntax:
	# exit-zero treats all errors as warnings. The GitHub editor is 127 chars wide
	poetry run flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

security:
	poetry run bandit -r src

build: poetry.lock
	@echo "Target build"
	poetry version --no-ansi
	poetry build

publish:
	@echo "Target publish to pypi"
	poetry publish

pex: build
	@echo "Target pex"
	mkdir -p artifacts/binaries

	poetry run dephell deps convert --envs main

	poetry run pex exabgp \
       --find-links=dist/ \
       --entry-point="exabgp.application.main:main" \
       --requirement=requirements.txt \
       --output-file=artifacts/binaries/exabgp \
       --wheel \
       --manylinux=manylinux2014

clean:
	@echo "Target clean"
	git clean -fdx

clean-venv:
	@echo "Target clean-venv"
	@poetry env remove $$(poetry env list --no-ansi | tail -n 1 | cut -d' ' -f1)

.PHONY: all list test syntax build publish pex clean clean-venv

