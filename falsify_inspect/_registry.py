"""Inspect AI extension registry.

Inspect discovers extensions via the ``inspect_ai`` setuptools entry point,
which points here. Importing the hook class is enough to register it (the
``@hooks`` decorator does the registration on import).
"""

from falsify_inspect.hooks import FalsifyHooks  # noqa: F401
