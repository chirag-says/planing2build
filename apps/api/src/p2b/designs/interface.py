"""Public interface of the designs module. The buildplan module only checks that a design request
names this project's AI concepts as illustrative references."""

from p2b.designs.service import concepts_of_project

__all__ = ["concepts_of_project"]
