"""Canonical graph vocabulary for the first PTW Result system."""

from enum import Enum


class EntityKind(str, Enum):
    SOURCE = "source"
    VALIDATION_PROJECT = "validation_project"
    PRODUCT_BRIEF = "product_brief"
    PROJECT_ASSET = "project_asset"
    PROJECT_BRAND_KIT = "project_brand_kit"
    STUDIO_RECIPE = "studio_recipe"
    STUDIO_RENDER = "studio_render"
    CONTENT_RUN = "content_run"
    CONTENT_CREATIVE = "content_creative"
    CONTENT_ELEMENT = "content_element"
    CONTENT_REVIEW_ACTION = "content_review_action"
    CONTENT_LEARNING_RULE = "content_learning_rule"
    CONTENT_LEARNING_SNAPSHOT = "content_learning_snapshot"
    CONTENT_CREATIVE_APPROVAL = "content_creative_approval"
    TELEGRAM_DELIVERY_RECEIPT = "telegram_delivery_receipt"
    CONTENT_OUTCOME = "content_outcome"
    HUMAN_FEEDBACK = "human_feedback"
    WEIGHT_UPDATE = "weight_update"


class RelationType(str, Enum):
    CONTAINS = "contains"
    DERIVED_FROM = "derived_from"
    SUPERSEDES = "supersedes"
    RERUN_OF = "rerun_of"
    EVALUATES = "evaluates"
    ADJUSTS = "adjusts"
