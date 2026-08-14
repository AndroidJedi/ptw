"""Explicit research-agent ownership and downstream consumption policy."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ResearchAgent:
    command: str
    owner_agent: str
    knowledge_domain: str
    research_type: str
    scope: str
    downstream: str


RESEARCH_AGENTS = {
    "creative": ResearchAgent("creative", "marketing.creative.instagram", "marketing.creative", "creative_ideation", "Instagram creative hooks, visual concepts, captions, and CTAs", "/creative from <hypothesis-id>"),
    "product": ResearchAgent("product", "product.strategy", "product.strategy", "product_discovery", "user problems, positioning, feature demand, and product evidence", "/task from <hypothesis-id> <request>"),
    "design": ResearchAgent("design", "product.design", "product.design", "design_patterns", "interaction patterns, usability evidence, visual systems, and accessibility", "/task from <hypothesis-id> <request>"),
    "engineering": ResearchAgent("engineering", "engineering.architecture", "engineering", "engineering_evidence", "primary technical documentation, architecture evidence, implementation constraints, and failure modes", "/task from <hypothesis-id> <request>"),
}


def research_agent(command: str) -> ResearchAgent:
    try:
        return RESEARCH_AGENTS[command.lower()]
    except KeyError as error:
        raise ValueError("research agent must be creative, product, design, or engineering") from error
