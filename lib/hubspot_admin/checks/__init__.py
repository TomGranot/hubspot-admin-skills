"""Importing this package registers every check. Lens modules register in
the order they should appear in the report."""

from . import shared, marketing, sales  # noqa: F401
from ..findings import registry  # noqa: F401
