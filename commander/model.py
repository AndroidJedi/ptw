"""Canonical generic graph vocabulary retained by PTW v2."""

from enum import Enum


class EntityKind(str, Enum):
    SOURCE = "source"
    POSITIONING_PROJECT = "positioning_project"
    MARKETING_POSITIONING = "marketing_positioning"
    LANDING_DRAFT_SET = "landing_draft_set"
    LANDING_DRAFT = "landing_draft"
    LANDING = "landing"
    LEAD_SUBMISSION = "lead_submission"
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
    SUBMITTED_TO = "submitted_to"
