# Telegram emergency boundary

The existing `@ptw_commander_bot`, root-owned token, allowlisted owner chat,
and established platform poller are the only Telegram integration. Inbound
commands are `/help`, `/status`, and `/stop`; every other input returns the
Owner Console link and cannot create a task or mutate domain state.

Result and Product Brief generation send no Telegram completion or failure
messages. A deployment canary is explicitly labelled and must not create a
Brief, Result, feedback row, or second poller. Never print, copy, rotate, or
replace the existing token without separate owner authorization.
