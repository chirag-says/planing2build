"""Public interface of the specification module. Other modules import only this file."""

from p2b.specification.service import (
    LineView,
    instantiate_lines,
    lines_for,
    record_accepted_values,
)

__all__ = ["LineView", "instantiate_lines", "lines_for", "record_accepted_values"]
