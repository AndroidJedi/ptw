# PTW service operations

Build Linux/amd64 Commander, Validation, and Owner Gateway images off-host with
one matching non-`latest` tag. Production starts them serially with `--no-build`.

The unrelated bridge remains under `/opt/ptw/platform`. Before rollout it must
advertise exactly Product Brief and Brief revision JSON modes and no media mode.
Run real Brief/revision canaries before an authorized reset.

After cutover verify Brief creation/correction/approval and graph persistence,
Studio asset/preview/version behavior, restart recovery, current PWA cache,
skills/schema checks, dependency audit, and resource audit. Never log prompts,
credentials, image bytes, or Telegram tokens.
