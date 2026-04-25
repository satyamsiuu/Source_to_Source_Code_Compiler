"""
errors.py — Unified error infrastructure for all compiler phases.
FROZEN after Phase 0 — do not modify.

Design: Every phase collects ALL errors into a list, then raises
CompilerErrorList once at the end. This gives the user a complete
picture of what went wrong instead of stopping at the first error.

Pattern used in every phase:
    errors = []
    ...
    if something_wrong:
        errors.append(CompilerError(Phase.LEXER, "message", line, col))
    ...
    if errors:
        raise CompilerErrorList(errors)
"""

from dataclasses import dataclass  # Python built-in: auto-generates __init__, __repr__
from enum import Enum              # Python built-in: named constants instead of magic strings


class Phase(Enum):
    """Identifies which compiler stage produced an error.
    Using an Enum prevents typos — Phase.LEXER is validated at import time,
    but the string 'lexr' would silently work and break downstream."""
    PREPROCESSOR = "preprocessor"
    LEXER = "lexer"
    PARSER = "parser"
    SEMANTIC = "semantic"
    IR = "ir"
    CODEGEN = "codegen"
    VALIDATOR = "validator"


@dataclass
class CompilerError:
    """A single error from any compiler phase.

    Fields:
        phase   — which stage found this error (Phase enum)
        message — human-readable description of what went wrong
        line    — 1-based line number in source code (None if not applicable)
        col     — 1-based column number in source code (None if not applicable)
    """
    phase: Phase
    message: str
    line: int = None   # default None: some errors (e.g. "empty source") have no location
    col: int = None

    def to_dict(self) -> dict:
        """Serialize to JSON-friendly dict for the frontend API response.
        Every error ends up in a JSON response that the browser displays."""
        return {
            "phase": self.phase.value,    # .value gives the string, not the Enum object
            "message": self.message,
            "line": self.line,
            "col": self.col,
        }


class CompilerErrorList(Exception):
    """Raised when one or more CompilerErrors are collected during a phase.

    Why extend Exception, not just return errors?
    Because errors should HALT the pipeline. If the lexer finds errors,
    the parser must not run on broken tokens. Python's exception mechanism
    naturally propagates up to the pipeline controller (main.py) which
    catches it and marks subsequent phases as 'blocked'.

    Why a list, not a single error?
    A CompilerError with one error stops at the first problem.
    A CompilerErrorList with all errors shows the user everything at once.
    Real compilers (GCC, Clang) do this — they show multiple errors per run.
    """

    def __init__(self, errors: list):
        # Store the list of CompilerError objects
        self.errors = errors
        # Build a human-readable summary for logging/debugging
        messages = [f"[{e.phase.value}] {e.message}" for e in errors]
        super().__init__("\n".join(messages))  # Exception.__init__ sets self.args

    def to_dict_list(self) -> list:
        """Serialize all errors to a list of dicts for the JSON API response."""
        return [e.to_dict() for e in self.errors]
