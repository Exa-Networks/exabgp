"""The configuration grammar.

Every keyword of the configuration is declared once, in `tree/`, as a node with a type.
The engine reads a configuration against that tree and builds Settings objects; the same
declarations print a configuration back, describe the syntax and drive completion.

Copyright (c) 2009-2026 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""
