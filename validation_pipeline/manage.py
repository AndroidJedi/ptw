from __future__ import annotations

import argparse

from .config import Settings
from .repository import ValidationRepository


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("verify", "recover"))
    args = parser.parse_args()
    repository = ValidationRepository(Settings.from_environment().database_url)
    if args.command == "recover":
        print(repository.recover_interrupted())
        return
    required = {
        "validation_projects", "product_briefs", "product_brief_approvals",
        "validation_generation_attempts", "validation_provider_invocations",
        "project_assets", "project_brand_kits", "studio_recipes", "studio_renders",
        "content_generation_runs", "content_creatives", "content_creative_previews",
        "content_elements", "content_creative_elements", "content_review_actions",
        "content_learning_rules", "content_learning_snapshots", "content_creative_approvals",
        "telegram_delivery_receipts",
        "content_generation_outcomes", "content_generation_checkpoints",
    }
    forbidden = {
        "creative_batches", "ad_creatives", "ad_creative_assets", "ad_studio_templates",
        "ad_studio_sample_sets", "ad_studio_wizard_proposals", "ad_studio_publications",
        "landing_builds", "landing_draft_sets", "commander_ad_batches",
        "content_candidates", "content_critic_passes", "content_improvement_actions",
        "content_results", "content_generation_skill_proposals",
    }
    with repository.connection() as connection:
        rows = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        ).fetchall()
    missing = required - {row[0] for row in rows}
    if missing:
        raise SystemExit(f"Result schema is incomplete: {sorted(missing)}")
    present_forbidden = forbidden & {row[0] for row in rows}
    if present_forbidden:
        raise SystemExit(f"legacy tables are forbidden: {sorted(present_forbidden)}")
    print("PTW Result schema: OK")


if __name__ == "__main__":
    main()
