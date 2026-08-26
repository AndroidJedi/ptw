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
    CONTENT_CANDIDATE = "content_candidate"
    CONTENT_ELEMENT = "content_element"
    CONTENT_CRITIC_PASS = "content_critic_pass"
    CONTENT_IMPROVEMENT_ACTION = "content_improvement_action"
    CONTENT_RESULT = "content_result"
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
