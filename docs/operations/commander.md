# PTW Validation service operations

Build linux/amd64 `ptw-commander`, `ptw-validation`, and
`ptw-owner-gateway` images off-host. Production uses one locked serial session,
one image load at a time, matching non-`latest` tags, and `--no-build` starts.

Commander/Owner Gateway/DB use `docker-compose.commander.yml`. Validation uses
its separately named Compose file/project and retains loopback 8093. The
platform bridge remains under `/opt/ptw/platform`; never merge repositories or
databases. Deploy its three-mode allowlist update independently. Run all fresh
strict bridge canaries and the non-persisting Pexels render canary before reset.

After cutover, run the dependency audit, public console audit, exact-owner
browser journey, skill verification, direct labelled bot emergency-boundary canary, restart check,
and `scripts/audit_ptw_1gb.sh`. Repeat the locked resource audit after 24 hours.
