# Telegram emergency boundary

The existing `@ptw_commander_bot`, root-owned token, allowlisted owner chat,
and established platform poller are the only Telegram integration. Inbound
commands are `/help`, `/status`, and `/stop`; every other input returns the
Owner Console link and cannot create or mutate domain state.

Product Brief and Studio actions send no Telegram completion, review, or failure
notifications. A deployment canary must not create a Brief or second poller.
Never print, copy, rotate, or replace the token without separate owner authorization.
