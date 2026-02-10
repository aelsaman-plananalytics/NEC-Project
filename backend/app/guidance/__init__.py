"""
Planner guidance: read-only composition of API + evolution outputs.

Provides planner-facing 'what to do next' view. Does not touch acceptability.
"""

from app.guidance.planner_guidance import build_planner_guidance

__all__ = ["build_planner_guidance"]
