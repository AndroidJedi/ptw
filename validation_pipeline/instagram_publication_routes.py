"""Compatibility facade for Instagram routes backed by the shared engine."""

from typing import Any, Sequence

from fastapi import APIRouter
from fastapi.params import Depends as DependsParameter

from .social_publishing.routes import social_media_router, social_publishing_router


def instagram_router(service: Any, *, prefix: str, dependencies: Sequence[DependsParameter] = ()) -> APIRouter:
    return social_publishing_router(
        service, prefix=prefix, label="Instagram", dependencies=dependencies,
    )


def instagram_media_router(service: Any, *, prefix: str, dependencies: Sequence[DependsParameter] = ()) -> APIRouter:
    return social_media_router(service, prefix=prefix, dependencies=dependencies)
