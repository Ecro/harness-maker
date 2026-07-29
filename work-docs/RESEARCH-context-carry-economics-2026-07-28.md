---
type: research
slug: context-carry-economics
created: 2026-07-28
source: harness_maker.economics report over 23,536 local turns ($5,422 list-price equiv.)
---

# RESEARCH — where the 65.8% carry actually is

`PLAN-token-economy-step-pruning` shipped a meter and ~0 measured savings (the rendered
command surface grew 0.75%). This is the first use of that meter to aim the next work.
Every number below is measured, not modelled.

> **⚠️ Corrected 2026-07-29 — every turn count and every absolute dollar below is ~2.1×
> too high. Every share, ratio, ctx/turn figure, and ordinal finding stands.**
>
> The meter counted **JSONL records, not API calls.** Claude Code writes one assistant
> record per content block (`thinking` / `text` / `tool_use`) and stamps the **same**
> `usage` on each, so `economics_source.load_turns` billed a single call two or three
> times. Verified verbatim: `msg_011CdF1bxf4qyKS3RE7i9RQR` spans 3 records all carrying
> `in=2 out=1663 cr=20352 cw=56171`.
>
> **What is wrong:** every `turns` column, and every `$`. **What is not:** shares (a ratio
> of two equally-inflated terms), `ctx/turn` (a mean over identical values is that value),
> and `context_composition`'s character shares (each content block appears in exactly one
> record). So Findings 1–6 and the lever ranking are unaffected — only their price tags.
>
> **Magnitude, measured on the frozen corpus** (`~/.cache/harness-maker/frozen-corpus-2026-07-28`,
> 48 files / 162 MB) with the shipped fix (`PLAN-wrapup-context-carry` Phase 1):
>
> | | before | after |
> |---|---:|---:|
> | assistant records → billed calls | 24,082 | **10,945** (13,137 collapsed) |
> | main-loop billed calls | 18,429 | **8,682** |
> | main-loop spend | $4,614 | **$2,150** |
> | main-loop carry | 74.9% | **79.2%** |
> | `hm:wrapup` spend / carry | $782 / $657 | **$339 / $294** |
>
> Carry *rises* as a share because collapsing removes duplicated non-cache-read cost from
> the denominator faster than cache-read from the numerator.
>
> **Two caveats on reproducing this.** (1) The figures above come from
> `tests/manual/oracle_dedupe_reference.py`, which prices every cache-creation token at
> the 5-minute rate; the shipped `economics report` splits 5m/1h and therefore reports a
> higher total (~$2,278) on the same corpus. The **call count (8,682) and carry dollars
> ($1,704) agree exactly** — the difference is pricing, not collapse. (2) The shipped
> report's `by_stage` mixes main-loop and subagent turns, while the per-stage tables in
> this document are main-loop only; do not compare them row-for-row.

## Headline

**Carry is a main-loop phenomenon. It is not a prompt-size phenomenon, and that is why
compacting prompts did nothing.**

| population | $ | share | turns | carry% | ctx/turn |
|---|---:|---:|---:|---:|---:|
| main loop | 4,767.61 | **87.9%** | 17,744 | **70.0%** | 300k–431k |
| subagents (13 kinds) | 654.52 | 12.1% | 5,483 | **35.2%** | 33k–128k |

Subagents start from a fresh context, carry half as much proportionally, and account for
one eighth of the bill. The main loop accumulates and re-reads.

## Finding 1 — context per turn is monotonic in pipeline position

| stage | ctx/turn | carry% | total $ |
|---|---:|---:|---:|
| `hm:research` | 79,894 | 25.1% | 120 |
| `hm:plan` | 186,514 | 42.2% | 467 |
| `hm:execute` | 308,797 | 66.9% | 1,141 |
| `hm:review` | 322,204 | 65.4% | 1,080 |
| `hm:verify` | 387,717 | **82.7%** | 57 |
| `hm:wrapup` | 431,128 | **82.4%** | 788 |

Carry% tracks ctx/turn almost exactly (research 80k/25% → wrapup 431k/82%). Nothing about
`verify` or `wrapup` needs more context than `research` — they run five mechanical checks
and write a commit message. **The growth is accumulation, not stage design.**

## Finding 2 — ~~the prompt is ~3% of what is carried~~ **CORRECTED: 17.6%**

The original claim here was a **per-turn** ratio (one 46,751-char command ≈ 13k tokens
against 431k ctx/turn) stated as if it settled the **aggregate** question. It does not.
Measured over 23.0M chars of transcript, carry-weighted, **slash-command bodies are 17.6%
of everything carried** — the third-largest category in the harness.

Phase 4 was therefore aimed at a real target. What it did not do is move it: it removed
4,437 chars from **one** of twenty commands, while Phase 3 added 3,765 chars to `review`,
which is invoked far more often. The category is worth attacking; a 3.6% cut to one member
of it is not an attack.

**Method note.** Two weightings were computed: chars-on-entry, and chars × turns-carried
(residency, with compaction boundaries resetting the segment). They agree to within ±5% on
every category — content enters roughly uniformly across a session, so there is no
early/late skew to exploit. The one exception is `compaction-summary` (ratio 1.71), which
by construction enters at a boundary and persists the whole following segment.

## Finding 3 — `wrapup` + `verify` pay $4.75 of rent per $1 of work

$696.60 of cache-read for $146.53 of `work_usd`. They are the two stages that need almost
none of the accumulated context, and they sit at the end of the pipeline where it is
largest. Together they are **19.5% of all carry**.

## Finding 4 — delegation is already enabled for `wrapup` and does not fix this

`delegation.stages: ["wrapup"]` is live; `stage-delegate` ran 327 turns. Wrapup is still
the worst carrier in the harness. The mechanism explains it: delegation moves the
*subagent's* work off the main loop, but the main loop's already-accumulated prefix is
re-read on every wrapup turn regardless of who does the work. **Delegation reduces what is
added; it cannot reduce what is already there.**

## Finding 5 — Phase 3's read budget was aimed at the cheaper half

The reviewer agents it bounds (`code-reviewer` 35.8% carry / $183, `test-reviewer` 23.5% /
$106, `security-reviewer` 32.4% / $87) are already the low-carry, low-cost population. The
expensive reader in the review stage is the **main loop** — $1,080 at 65.4% carry, 6× the
reviewers combined — and it has no read budget at all. The instruction is right; it was
installed on the wrong reader.

## Finding 6 — what the 300k+ prefix is actually made of

23.0M chars over 48 transcripts, carry-weighted:

| category | carried% | note |
|---|---:|---|
| **Bash** (call + result) | **27.9%** | the largest single thing in the harness |
| **slash-command bodies** | **17.6%** | Phase 4's target — see Finding 2 |
| **Write** (content authored) | **15.9%** | every file body stays in the prefix permanently |
| **Edit** (old + new strings) | **11.2%** | a large edit is stored twice, by construction |
| **Read** results | **7.8%** | *Phase 3's target* |
| task-notification | 5.9% | background-task chatter |
| assistant_text | 4.1% | |
| Agent (dispatch + reply) | 3.7% | |
| system-reminder | 1.6% | |
| compaction-summary | 1.3% | |
| **human-typed** | **0.1%** | the user is 1 part in 1,000 |

Inside Bash (27.9%), by command kind — share of **all** carried context:

| kind | of all context |
|---|---:|
| `grep` / `rg` output | **10.8%** |
| file inspection (`cat`/`head`/`ls`/`find`/`wc`) | **5.2%** |
| `harness_maker` CLI | 4.3% |
| `pytest` | 3.5% |
| `git diff/show/log` + other git, heredocs, inline python, mypy, ruff, other | remainder |

> **Corrected 2026-07-28 by the committed meter** (`PLAN-context-carry-discipline` Phase 1).
> The first version of this table multiplied each kind's entry-weighted share *within Bash*
> by Bash's *carry-weighted* total — two different weightings multiplied together. The
> figures above come from `economics composition`, which divides by `total_chars`
> throughout. Every correction moves the number **up**: search + inspection is **16.0%**,
> not 13.5%. The `write_after_read` figure was unaffected and matched to the character
> (877,409).

**Search and inspection output alone is 16.0% of everything carried** —
the largest addressable slice in the harness, and nothing in `PLAN-token-economy-step-pruning`
touched it. `pytest`, the intuitive suspect, is 2.3%: `-q` plus redirect-to-file is already
doing its job.

## Candidate levers, ranked by measured size

1. **Reset the context before late stages.** `verify` and `wrapup` at `plan`-level context
   (187k instead of ~410k) would cut ~$390 of the $697 carry those two spend. Mechanically
   this means a fresh session or an enforced compaction boundary before them — not more
   delegation.
2. **Give the main loop the read budget** that Phase 3 gave reviewers. Execute+review main
   loop = $2,221 at ~66% carry; whole-file reads there enter the prefix and are re-read
   for the rest of the session.
3. **Bound search and inspection output** — 16.0% of all carried context, 2,376 calls,
   averaging ~1.1k chars of result each. This is now the largest *addressable* lever and
   it is a behavioural one: `head`-limit every `rg`, prefer the Grep tool's `head_limit`
   over raw `rg`, and stop `cat`-ing files that a Read with an offset would answer.
   Cheap to instruct, no runtime machinery.
4. **Stop re-sending file bodies the context already holds** — measured at **3.8% of all
   carried context**, and it is 100% waste rather than a tradeoff.

   `Write` requires a prior `Read` of an existing file, so a full-file rewrite puts the
   body in the context **twice**: once as the Read result, once as the Write input. Of
   407 `Write` calls, 341 (69% of bytes) created a new file — irreducible, the content has
   to enter somehow. The other **66 calls, 877,409 chars, rewrote a file already Read in
   that session.** Every one of those bytes is a second copy.

   The offenders are not code — they are **PLAN documents**, the largest single-file
   artifacts in this repo, edited by full rewrite:

   | duplicated chars | file |
   |---:|---|
   | 128,422 | `PLAN-second-opinion-invocation-and-slug-cap.md` |
   | 111,543 | `PLAN-economics-attribution-and-carry.md` |
   | 51,305 | `PLAN-harness-economics-observability.md` |
   | 49,556 | `PLAN-permission-deny-and-hooks-wiring.md` |
   | 43,263 | `PLAN-token-economy-step-pruning.md` |

   For scale: mean `Write` = 6,956 chars; mean `Edit` (old+new) = 1,211 chars across 1,675
   calls. On an incremental change to a large document the two differ by an order of
   magnitude, and the difference is pure duplication.

   > **The constraint that made this unfixable was removed on 2026-07-28.** Both CLAUDE.md
   > files carried a rule mandating `Write` for full-file rewrites, attributed to Edit-tool
   > corruption on WSL2/NTFS. The user identified it as false and it was deleted. Its
   > likely origin is worth recording: the entry was tagged `[vault-system]`, and the vault
   > lives on a real NTFS mount (`/mnt/c/...`), whereas `/home/noel/harness-maker` is
   > **ext4 inside the WSL2 VM and not NTFS at all** — an observation on one filesystem
   > generalised to a path it never covered. Same shape as
   > `[fail:test] snapshot-regen-inside-worktree` instance 13: verifying X and asserting Y.
   >
   > The **separate** WSL2/NTFS facts about POSIX semantics — `flock` degrading silently,
   > hence the O_EXCL fallback in merge-fence Layer 4, and the atomic-write rule — are
   > unaffected and were deliberately left in place.

**Measurement completed 2026-07-28** (Finding 6). The original "what is in the prefix"
question is answered; levers 1–4 are now ranked against data rather than intuition.

### Ranking, with what each actually costs to take

| # | lever | measured size | reducible? | cost to take |
|---|---|---:|---|---|
| 1 | bound search/inspection output | 16.0% | mostly | instruction only |
| 3 | slash-command bodies | 17.6% | **hard** — Phase 4 moved 3.6% of one of twenty | template work, ratchet exists |
| 2 | reset context before `verify`/`wrapup` | ~$390 of $697 carry | yes | session/compaction boundary — real design change |
| 4 | stop Write-after-Read duplication | 3.8% | **entirely** | instruction only, now unblocked |

**Take 1 and 4 first.** Both are pure instruction, no runtime machinery, no design change,
and together they address 19.8% of carried context with no tradeoff against quality. Lever
3 is larger on paper but Phase 4 is the evidence for how hard it is to move. Lever 2 is
the biggest single dollar figure and the only one that needs an architectural decision —
it should get its own SPEC, not be bolted onto a prompt-discipline change.

## What this does NOT say

- It does not say the pipeline is wasteful in wall-clock or quality terms. `carry_ratio` is
  a cost shape, not a verdict; `harness-economics-observability` ADR-002's no-ratio
  invariant still holds — do not turn any of these into a score.
- `OTHER` is 74% of spend by category ($4,016 / 15,972 turns). That is mostly an
  attribution artifact, not a finding; `(unattributed)` alone is 7,009 turns.
- Nothing here is a before/after of Phase 3. It landed 2026-07-27 with too few subsequent
  reviews to measure.

## Next step

Lever 3 first — **measure the composition of the 300k+ prefix** before proposing any
change to it. Acting on levers 1 and 2 without knowing what is actually in the context
would repeat this plan's mistake: shrinking the part that was easy to see.
