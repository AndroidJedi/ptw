"""Natal's deterministic landing-page kit and builder contract."""

from .brief import LandingBrief, brief_from_candidate
from .catalog import landing_templates, recommend_template

__all__ = [
    "LandingBrief",
    "brief_from_candidate",
    "landing_templates",
    "recommend_template",
]
