"""
Read-only diagnostics layer for validator output.

Explains validator results to planners. Does not modify, infer, or recompute
acceptability. See obligation_diagnostics.build_obligation_diagnostics.
"""

from app.diagnostics.obligation_diagnostics import build_obligation_diagnostics

__all__ = ["build_obligation_diagnostics"]
