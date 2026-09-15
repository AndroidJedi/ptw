# Preserved inactive surfaces

The active applications intentionally do not mount Meta Ads automation or
TikTok publishing routes. Before recovery, confirm that this remains true in:

- `validation_pipeline/api.py`
- `validation_pipeline/studio_local_api.py`
- `owner_gateway/api.py`
- `apps/commander-web/src/`

Historical implementation material remains in provider modules, migrations,
tests, configuration scripts, and database tables. Relevant starting points
include:

- `validation_pipeline/meta_ads.py` and `validation_pipeline/meta_ads_routes.py`
- `validation_pipeline/tiktok_publication.py` and
  `validation_pipeline/tiktok_publication_routes.py`
- `validation_pipeline/social_publishing/`
- `scripts/configure_meta_ads.sh` and `scripts/configure_tiktok.sh`
- migrations and tests containing `meta_ads_*` or `tiktok_*`

Do not infer runtime readiness from their presence. Reconcile each preserved
contract against the current approved-Post source abstraction, Landing
publication lifecycle, attribution model, analytics projection, API security,
and current provider requirements before exposing it.
