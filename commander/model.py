"""Canonical generic graph vocabulary retained by PTW v2."""

from enum import Enum


class EntityKind(str, Enum):
    SOURCE = "source"
    PRODUCT_BRIEF = "product_brief"
    CREATIVE_BATCH = "creative_batch"
    AD_CREATIVE = "ad_creative"
    HUMAN_FEEDBACK = "human_feedback"
    WEIGHT_UPDATE = "weight_update"
    TASK = "task"
    ARTIFACT = "artifact"
    AUDIT_EVENT = "audit_event"
    POLICY_EVALUATION = "policy_evaluation"


class RelationType(str, Enum):
    CONTAINS = "contains"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    EVALUATES = "evaluates"
    ADJUSTS = "adjusts"
