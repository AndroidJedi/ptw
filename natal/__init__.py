"""Natal's deterministic landing-page kit and builder contract."""

from .brief import LandingBrief, brief_from_positioning
from .catalog import landing_templates, recommend_template

__all__ = [
    "LandingBrief",
    "brief_from_positioning",
    "landing_templates",
    "recommend_template",
]
