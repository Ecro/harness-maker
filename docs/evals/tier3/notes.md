**What each hm run carried across the session boundary.** Read from the transcripts of both
sessions of every run. "Saved" is what session 1 left on disk, "used" is what session 2 read
before it changed code. No run wrote or read an intent entry or a world-model digest, and no
SessionStart context named the earlier work: session 2 found it by listing `specs/` and reading
the files.

| Run | Session 1 saved | Session 2 found and used | t20 trap / t21 guard | Holds and stalls |
|---|---|---|---|---|
| t20 hm 1 | SPEC (full lane), PLAN, REVIEW, code and tests. The SPEC's Non-Goals hold the whole deferred step: `lang` defaults to `en`, joiner `", "` for `en` and `" "` for `ko`, an unknown `lang` raises before formatting | Read that SPEC first, wrote a step-2 SPEC from it | Avoided: Korean joiner and `lang` both right | Session 1 sat idle for about 18 minutes after its verify report, waiting on its own 20-minute `ScheduleWakeup` fallback, which then fired a no-op review. That is most of the run's 31-minute wall |
| t20 hm 2 | SPEC (light lane), PLAN, REVIEW. The hand-off is one line, "`", "` vs `" "` joiner", which does not say which language gets which | Read the SPEC and chose `en` `", "`, `ko` `" "` from the order of that line | Avoided, on an ambiguous note | none |
| t20 hm 3 | SPEC (full lane), PLAN, REVIEW. The SPEC says step 2 exists and lists open questions, but drops the joiner rule and the unknown-`lang` ordering | Read the SPEC and its machine file, chose `", "` for every language, and filed the Korean joiner as an open question for the DRI | **Hit**: `"1시간, 30분"` where the rule says `"1시간 30분"` (`test_korean_uses_its_own_joiner`) | The open question waited for an answer that a headless run cannot give |
| t21 hm 1 | SPEC (full lane), PLAN, REVIEW, a new `D-11` in `docs/DECISIONS.md`, and a project fact in `.claude/memory/wiki.md` (through Maker) stating the 30-day cap | Grepped `D-11` and the wiki fact, superseded `D-11` with `D-12`, retired the fact, lifted the cap | Guard kept (`parse_duration` unchanged); solved | none |
| t21 hm 2 | SPEC (full lane), PLAN, REVIEW for the capped `parse_iso_duration` | Read that SPEC and wrote a step-2 SPEC that lifts the cap | Guard kept, but the run is not solved: `parse_clock` was never written and the cap stayed | **Decided by a hold.** The test-reviewer gate (A.5) failed twice, execute stopped as blocked and asked the operator to pick a path. Nobody answers in `-p`, so the session ended with only tests on disk |
| t21 hm 3 | not run | | | The runner stopped scheduling when recorded spend passed the run's $15 cap |

**Approval holds.** Four of the five runs wrote full-lane SPECs that autopilot could not get
approved headless ("no approval stamped, so the land hold covers IRR-..."). The bench grades the
work tree and nothing has to land, so the land hold changed no grade. The hold that changed a
grade was t21 hm 2's blocked test-review gate. No session hit the runner's 1800-second timeout.

**Controls on the same two tasks.** `plain-continue` (the second session resumes the first
conversation) solved t20 3/3 and t21 3/3 at under a fifteenth of hm's cost per run, so on these
tasks hm's saved state did not beat simply keeping the conversation. `plain-careful` solved t20 2/3
with no saved state at all: its second session wrote `" "` for Korean, which is the natural
Korean convention, so t20's joiner can be guessed as well as remembered. Its one failure never
added `lang`. In the pilot, plain failed t20 the same two ways: `", "` for Korean twice, no `lang`
once.

**Cost.** Each hm row's cost is the CLI total, which leaves out subagent spend; the
transcript-priced total for the 17 diagnostic rows is about $22.2 against $18.1 by the CLI.

**Fairness notes.**

- The plain pilot ran before the DRI signed the tier-3 hash; the rows record the hash that was
  later signed (`1f8767cb8b8c`), so the piloted bytes are the signed bytes.
- `docs/DECISIONS.md` in the shared base (D-1 to D-10) helped plain: the answer to several tasks
  is a decision record, and a plain session reads that small file whole. It is part of why plain
  solved t13-t19 and the tasks dropped.
- t18's oracle is strict: one hidden test parses `timeparse/parse.py` and fails while the old
  token loop (`finditer`) is still called. Plain's one t18 failure is exactly that, a structure
  miss with unchanged behaviour, and t18 dropped either way (2 of 3).
- The pilot and the diagnostic ran from a checkout with one untracked session file, so both
  record a `-dirty-764de9af` harness sha; the diagnostic's base commit is the rebased branch.
