# Meta Ads boundary

PTW does not call the Meta Ads API in the active product. Paid Instagram tests
are prepared in PTW, launched manually in Meta Ads Manager, and measured by
combining reviewed CSV delivery data with automatically collected first-party
Landing events. The complete current contract is
[`instagram-manual-validation.md`](instagram-manual-validation.md).

Historical `meta_ads_*` tables, migrations, provider modules, configurator, and
tests remain intact so prior records retain their authority and an explicitly
requested recovery remains possible. Their presence does not imply runtime
readiness. Validation, Owner Gateway, and Owner Console do not mount their
routes, jobs, or UI.

Use `skills/legacy-social-automation-recovery/SKILL.md` only if the owner
explicitly asks to restore Ads API automation. Restoration must revalidate
current Meta permissions/app approval, preserve historical graph lineage, keep
new objects PAUSED through review, and coexist explicitly with or deliberately
replace the manual Instagram-test contract. No production recovery is implicit.
