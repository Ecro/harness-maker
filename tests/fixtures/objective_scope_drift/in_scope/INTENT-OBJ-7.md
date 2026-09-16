---
schema_version: 1
id: OBJ-7
title: Cut onboarding to one interview round
hypothesis: a shorter first interview keeps more first-run users, measured by onboarding_minutes
scope:
- merge interview rounds 2 and 3 into one
- drop the locale free-text question when the OS locale is known
non_scope:
- rewriting the renderer
- changing the preset axis
rejected:
- ship the interview unchanged and only shorten the help text
outcome_id: onboarding_minutes
depends_on: []
state: active
approval: null
revisit_when: null
observed: null
note: null
created_at: '2026-09-01T00:00:00Z'
closed_at: null
---
## Problem

See the PLAN beside this file.
