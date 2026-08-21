#!/usr/bin/env python3
# encoding: utf-8

"""Fill every decoder registry before the property tests are collected

The registries fill by import side effect: a class is registered when the module
defining it is imported.  A test module which imports only what it names by hand
therefore parametrises over a HALF EMPTY registry and reports a clean run over a
fraction of the codes, which reads as coverage and is worse than a failure.

Walking the packages here runs before collection, so the parametrised tests see
every registered code.
"""

import importlib
import pkgutil


def _import_everything(package_name: str) -> None:
    try:
        package = importlib.import_module(package_name)
    except ImportError:
        return
    for _finder, name, _ispkg in pkgutil.walk_packages(package.__path__, package.__name__ + '.'):
        try:
            importlib.import_module(name)
        except ImportError:
            continue


for _package in (
    'exabgp.bgp.message.update.attribute',
    'exabgp.bgp.message.update.nlri',
    'exabgp.bgp.message.open.capability',
):
    _import_everything(_package)
