"""Canonical generic graph vocabulary retained by PTW v2."""

from enum import Enum


class EntityKind(str, Enum):
    SOURCE = "source"
    VALIDATION_PROJECT = "validation_project"
    PRODUCT_BRIEF = "product_brief"
    CREATIVE_BATCH = "creative_batch"
    AD_CREATIVE = "ad_creative"
    STUDIO_SOURCE_ASSET = "studio_source_asset"
    STUDIO_BRAND_KIT = "studio_brand_kit"
    STUDIO_TEMPLATE = "studio_template"
    STUDIO_RECIPE = "studio_recipe"
    STUDIO_RENDER = "studio_render"
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
