"""Canonical graph vocabulary for Product Brief validation."""

from enum import Enum


class EntityKind(str, Enum):
    SOURCE = "source"
    VALIDATION_PROJECT = "validation_project"
    PRODUCT_BRIEF = "product_brief"
    HUMAN_FEEDBACK = "human_feedback"
    WEIGHT_UPDATE = "weight_update"


class RelationType(str, Enum):
    CONTAINS = "contains"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    EVALUATES = "evaluates"
    ADJUSTS = "adjusts"
