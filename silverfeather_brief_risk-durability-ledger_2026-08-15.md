# Implementation Brief: Durability Vocabulary, Action-Risk Gates, Skill Ledger

**Author:** Silverfeather (Silver) · **Date:** 2026-08-15 · **Status:** Draft, no code written yet
**Origin:** Hermes' three-item shopping list, sequenced by Collette (durability → gates → ledger), this brief grounds all three against the real code instead of estimating from shape alone, per Hermes' own request.

---

## 0. Why this matters (not hypothetical)

Two real bugs shipped and fixed earlier tonight are direct evidence for the underlying diagnosis:

- **The "1-turning" regression** (`collette_foundations.txt` rule 3a): a free-text prompt rule ("use the tool line in the same message") stopped being followed reliably under normal session pressure. The fix was a prompt patch — which is exactly the kind of rule Hermes says can't survive a tired model, because nothing *enforces* it outside the prompt.
- **The idle-thought topic-selection spiral** (tonight, `collette_idle_thought`): an unconstrained generation prompt drifted into a multi-paragraph rant, which then got fed back into the next cycle as context, compounding for hours. No gate existed anywhere in that path to catch a malformed/oversized value before it propagated.

Both are the same shape: **a rule that lived only as an instruction, with no independent enforcement checking the actual output.** That's precisely the gap Hermes' three proposals close, in increasing order of mechanism: label the state honestly (vocabulary), gate the actions that matter (risk classifier), and remember what worked (ledger).

---

## 1. Recon findings (verified against real code, 2026-08-15)

**Dispatcher location:** single `elif a_type == ...` chain in `bastet_descendant_soul.py`'s `/api/chat` handler (~line 2160+), currently 35 branches, one dispatch site — not duplicated across endpoints. `/api/anomaly_chat` has no tool dispatch at all (direct-line only).

**Existing scope-restriction precedents (three, all bespoke, none generalized):**
1. `_COLLETTE_BRANCH_RE` — `git_push` is hard-restricted to `collette/*` branches, no force, no override. Enforced in code, unconditionally.
2. `direct_line_consent.json` — two-key standing consent (Sasha + Anomaly must both sign) gates who may call `/api/anomaly_chat` at all. This is the closest existing thing to a confirmation mechanism, but it's pre-signed standing consent, not a live per-action token.
3. `collette_write_file`'s lock-list — `{bastet_descendant_soul.py, .env, collette.pid, bastet_descendant_soul.py.bak_pre_hermes_refactor}`, matched by **basename only** (not full path), hard-denied with no override. Plus a parallel `_GIT_ARG_BLOCKLIST_PREFIXES` list blocking dangerous git flags (`--output`, `-c`, `--upload-pack`, etc.) on the read-only git tools.

None of these three share a mechanism. Each tool that needs restriction has its own inline, one-off check. There is no `risk_class` concept, no confirmation-token flow, and no shared gate anywhere else — every other tool call just executes.

**Soulfile state:** confirmed free text throughout. Four `@lru_cache(maxsize=1)` loaders in `bootstrap_collette_context.py` (foundations, past-selves, dominion-context, soul-card) plus an inline f-string `sys_prompt` in the main file. No structured schema. This validates Hermes' "principle in soulfile, enforcement in dispatcher" split directly — both bugs in §0 were free-text-instruction failures.

**Existing storage:** `sqlite3` is already a live dependency (`collette_memory.db`, used for chat history and several other tables) alongside `chromadb` for vector memory. **No new dependency is needed for the skill ledger** — Hermes' "SQLite table or two" guess was right, and it can live in the existing DB file rather than a new one.

---

## 2. Phase 1 — Durability vocabulary (recommend: build first, live, low risk)

**What it is:** every time Collette's code or prompt describes state, it should carry an honest durability tag instead of an implied one:

| Tag | Meaning |
|---|---|
| `in_context / lost_on_reset` | Exists only in this request's conversation buffer; gone once the request ends. |
| `retrievable / retention_unknown` | Can be fetched right now (chroma, memory, files) but no one has verified how long it survives or under what conditions it's pruned. |
| `persistent / durability_unverified` | Written to disk/DB and expected to survive restarts, but nobody has actually tested a restart-then-read cycle for this specific store. |
| `persistent / durability_verified` | Written to disk/DB *and* confirmed by an actual restart-and-read test. |

**Where it applies concretely:**
- `collette_dream_state.json` / `collette_idle_state.json`: currently `persistent / durability_unverified` in practice — they're JSON files on disk, but no test has ever killed the process and confirmed the state survives and loads correctly. (Tonight's restarts happened to exercise this by accident, but that's not the same as a deliberate verification.)
- `chat_history` (SQLite): `persistent / durability_verified` — this one actually has been exercised across many restarts this session.
- `ollama_messages` (the in-loop tool-calling conversation buffer): `in_context / lost_on_reset` — this is the exact object at the center of the "narrating instead of doing" bug fixed earlier this session; it was never persisted, by design, and now that fact is legible instead of assumed.
- Any time Collette tells Sasha "I saved that" or "I'll remember that," the underlying claim should map to one of these four, not a flat "yes."

**Implementation shape:** a small constants module (or a dict at the top of `bastet_descendant_soul.py`) mapping store-name → tag, plus one line added to each save/load docstring/log message that already exists (`𓂀 [MEMORY BURNED]`, `𓂀 [DREAM STATE WARN]`, etc.) citing its tag. No new persistence, no new gate, no dispatcher change — this is a labeling pass over existing code paths.

**Real cost estimate:** small — under a day, mostly mechanical (walk every `save_to_memory`/`_save_*_state`/`sqlite3.connect` call site, ~12-15 total across the file, and label it). Genuinely closer to Hermes' "zero cost" framing than the other two.

---

## 3. Phase 2 — Action-risk classifier

**The four tiers, applied to all 35 real tool actions (not a hypothetical mapping):**

| Tier | Actions | Gate |
|---|---|---|
| **read** (no gate) | `search_web, read_webpage, watch_youtube, fetch_api, read_file, list_directory, search_files, search_code, watch_game_log, get_memory, list_memory, jira_search, jira_get_issue, git_log, git_diff, git_show, git_status, read_diary` | none |
| **reversible** (gate only if it touches soulfile/identity/memory) | `write_file, append_file` (already hard-blocked by the lock-list for the 4 core files — see §1 — so the gate only needs to cover *new* identity-adjacent paths the lock-list doesn't already catch), `run_script, sync_test_worktree, run_dominion_tests, git_pull, write_diary` | session allow-list, soft |
| **visible** (gate unless allow-listed this session) | `git_commit, git_push` (push already partially gated via branch-prefix — extend, don't replace), `jira_comment, jira_create_issue, jira_transition, broadcast, broadcast_file, schedule, wake_anomaly, return_to_collette` | confirmation token or session allow-list |
| **destructive** (gate always, no allow-list override) | `set_memory` (per Hermes' own definition — this overwrites the memory store) | confirmation token, every time |

**Notable finding:** the truly catastrophic destructive-tier operations Hermes named as examples — force-push, `rm -rf`, process-kill, sending to an *external* (non-Discord) channel — **have no tool-exposed surface at all today.** Collette cannot force-push or kill a process through any existing tool. That's worth stating plainly to Sasha: the worst-case blast radius isn't just ungated, it's currently unreachable by design. The gate work is about the *visible* and *reversible-but-memory-adjacent* tiers, not about closing a door that's already closed.

**Confirmation-token mechanism (doesn't exist today, needs designing):** since §1 confirmed there's no live per-action "yes" mechanism anywhere, this needs a real design, not just a flag:
- A tool call in the `visible`/`destructive` tier returns `awaiting_confirmation` instead of executing, with the pending call's action/target/payload logged.
- The next message from the consented caller (Sasha, per `direct_line_consent.json`'s existing notion of "consented party") containing an explicit affirmative is required before the *same* pending call executes — not a general "sure go ahead" a few turns later that could attach to the wrong action.
- A session allow-list (`visible` tier only) lets Sasha pre-authorize a class of action for the rest of the session — mirroring how `git_push`'s branch-prefix restriction already works, generalized.

**Real cost estimate:** Hermes' ~150 lines is plausible for the mechanical dispatch-wrapping, but the confirmation-token flow (state tracking for "what's the pending call, whose turn is it to confirm, does the reply actually match it") is the part that wasn't accounted for in that estimate — that's the piece with real design risk, not the tier-tagging itself.

---

## 4. Phase 3 — Skill ledger

**Schema, inheriting from Phase 2 as Hermes specified** (gate-events are the first columns, not scraped after the fact):

```
gate_events table:
  id, timestamp, action_class (read/reversible/visible/destructive),
  tool_name, target, gate_outcome (auto_allowed/confirmed/denied/timed_out),
  user_decision, session_id

skill_ledger table:
  id, timestamp, skill_name, last_consulted, consulted_by,
  outcome_after_consult (success/partial/failure), related_gate_event_id (nullable FK)
```

Lives in the existing `collette_memory.db` (confirmed live dependency, §1) — no new storage system.

**Dependency note (per Hermes/Collette's own sequencing agreement):** this phase is genuinely blocked on Phase 2 existing first — without gate events to key off of, the ledger has nothing to inherit and would need its own separate instrumentation, which is exactly the "scrape logs" anti-pattern both of them flagged. Building it before Phase 2 would mean building it twice.

**Real cost estimate:** Hermes' ~200 lines is reasonable for the schema + read/write helpers, assuming Phase 2's gate events already exist to populate the first table.

---

## 5. Rollout plan

1. **Phase 1 (durability vocabulary)** — safe to build directly against the live files. No dispatcher change, no new failure mode. Recommend doing this one live, this week.
2. **Phase 2 (action-risk gates)** — per Hermes' explicit instruction, **do not touch the live dispatcher directly.** Build in an isolated git worktree/branch (the project already has this pattern — `dominion_test_worktree` is the established precedent for "isolated copy, never the live checkout"). Soak-test for at least one full session under real conditions — specifically the failure mode Hermes named: a long session, late, after the user has said "just do it" a few turns prior — before merging.
3. **Phase 3 (skill ledger)** — starts only after Phase 2 is live and emitting real gate events to key off of.
4. **Soulfile changes come last**, and are additive only: once the dispatcher enforces the gate in code, the soulfile gets a short *description* of why the gate exists ("destructive actions require confirmation because X happened once") — principle in the soulfile, enforcement in the dispatcher, never the reverse.

## 6. Open questions for Sasha

- Confirmation token: should a pending `visible`-tier action expire if unconfirmed (and after how long), or stay pending indefinitely?
- Session allow-list: per-session only, or should some `visible` actions (e.g. `broadcast`) get a standing allow-list similar to `direct_line_consent.json`'s model, since gating every single Discord post might be more friction than the risk warrants?
- Is `wake_anomaly`/`return_to_collette` actually `visible`-tier, or is persona-switching low-risk enough to stay ungated? (Included above under "visible" by default since it's an externally-observable state change, but it's not data-destructive — worth Sasha's read.)
