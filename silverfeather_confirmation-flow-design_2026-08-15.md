# Confirmation-Flow Design: Pending Actions, Scope Matching, Expiry, Gate Events

**Author:** Silverfeather · **Date:** 2026-08-15 · **Status:** Design only, no code written
**Depends on:** `silverfeather_brief_risk-durability-ledger_2026-08-15.md` (approved for planning, not implementation)
**Purpose:** answer, concretely, everything amendment 2 and amendment 5 asked for before any tier-tagging code gets written. Every open question gets a specific answer here, not a placeholder — where I had to choose between two reasonable designs, I say which one and why, so Sasha is reviewing a decision, not a menu.

---

## 1. What creates a pending action

A pending action is created the instant the dispatcher resolves a tool call into the `visible` or `destructive` tier (per the Phase 2 brief's tiering) and is about to execute it. At that moment, instead of executing:

- A `PendingAction` record is created: `{id (short random token, e.g. 4 hex chars), created_at, tool_name, target, payload, risk_tier, status="pending"}`.
- It is held **in memory only** (a single module-level variable — see §7 for why this deliberately does not persist across a restart).
- **Only one pending action may exist at a time**, full stop (amendment 2's concurrency question). If a new `visible`/`destructive` call arrives while one is already pending, it is refused outright with a plain message identifying the existing pending id — it does not queue, does not overwrite, does not silently proceed. This removes an entire class of ambiguity (which action does a reply resolve?) by construction rather than by runtime disambiguation logic.
- The tool call returns `awaiting_confirmation` instead of a result. The reply shown to Sasha names the pending id explicitly, e.g.:

  > ⚠️ **Confirmation needed [`7f3a`]**: `jira_transition` → DOM-152 → "Done". Reply **"confirm 7f3a"** to proceed or **"deny 7f3a"** to cancel. Expires in 20 minutes or after 5 of your messages that don't mention it, whichever comes first.

## 2. How confirmation matches the exact action and scope (amendment 2, point 2)

**The match is the id, and only the id — nothing else counts.** Every inbound message from the consented caller (currently: Sasha, per `direct_line_consent.json`'s existing notion of who's allowed to act on the direct line — reused here rather than inventing a second consent concept) is checked against a strict pattern before normal chat processing runs: `^(confirm|deny)\s+([0-9a-f]{4})\b`, case-insensitive.

- If it matches **and** the id matches the currently-pending action: resolve it (`confirmed` or `denied`), execute or discard accordingly, write the gate event (§6), clear the pending slot.
- If it matches but the id does **not** match the current pending action (typo, or referencing an already-resolved one): respond with the actual current state of that id — "that confirmation already resolved as denied" or "no pending confirmation with that id" — never silently no-op. This is amendment 2's "stale or conflicting confirmations" requirement.
- If no pending action exists and the message doesn't match the pattern at all: normal chat processing, unaffected.

**Nothing else is treated as a confirmation.** This is the direct, deliberate answer to amendment 2's hardest question:

## 3. What happens when the user says "just do it" broadly (amendment 2, point 6)

**Nothing.** A bare "just do it," "go ahead," "yes," or any other unscoped affirmative does **not** satisfy a pending confirmation, ever, regardless of how many times it's been said in the surrounding conversation or how confident the model is that it knows what was meant. Only an explicit `confirm <id>` resolves a pending action.

This is the direct fix for the exact failure mode Hermes named as the real test: *Sasha has said "just do it" a few turns ago, the model is deep in a long task, a visible action comes up* — under this design, that prior "just do it" is conversational context Collette can use to decide *whether to propose the action at all*, but it structurally cannot be the thing that satisfies the gate. The gate only ever looks for the literal id. A tired model cannot talk itself, or get talked, past this, because the check is a regex on the id, not a judgment call about what the user probably meant.

The cost is real friction — Sasha has to type `confirm 7f3a` even after saying "just do it" — and that is the point, per amendment 4's explicit instruction that friction is acceptable and a wrong visible action is worse.

## 4. Expiry behavior (amendment 2, point 3)

Dual-bound, whichever triggers first:
- **Wall-clock:** 20 minutes from creation.
- **Turn-count:** 5 subsequent messages from the consented caller that do not reference the pending id (across any channel — Discord or web chat both count against the same counter, since they're the same underlying dispatcher).

On expiry: status → `expired`, gate event written (§6), pending slot cleared. If a late `confirm <id>` arrives afterward, §2's stale-match handling reports it plainly as expired — it does not execute.

Turn-count is included alongside wall-clock because a legitimate pause (Sasha steps away mid-conversation) shouldn't force a re-request, but an active conversation that's clearly moved on shouldn't leave a stale action armed indefinitely either.

## 5. Whether a changed task invalidates the token (amendment 2, point 5)

**No topic-change detection is implemented, deliberately.** Classifying "has the task changed" reliably is itself an unreliable, model-judgment-dependent operation — building safety logic on top of an unreliable classifier defeats the purpose. Instead, the combination of §2 (id-exact-match only), §4 (bounded expiry), and §1 (one pending action at a time, so there's never ambiguity about *which* task a stray confirm could apply to) makes topic-change detection unnecessary: if the task changed, the old pending action just sits there unconfirmed until it expires. The safety property doesn't depend on detecting intent, only on requiring an unambiguous token.

## 6. Durable gate-event storage (amendment 5)

New table in the **existing** `collette_memory.db` (confirmed live SQLite dependency — no new storage system):

```sql
CREATE TABLE gate_events (
    id TEXT PRIMARY KEY,          -- the pending-action id, e.g. "7f3a"
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    tool_name TEXT NOT NULL,
    target TEXT,
    risk_tier TEXT NOT NULL,      -- reversible / visible / destructive
    status TEXT NOT NULL,         -- pending / confirmed / denied / expired
    resolving_message TEXT,       -- the literal text that resolved it, for audit
    session_context TEXT          -- free text: what was happening when this fired
);
```

**Write timing:** a row is inserted the instant a pending action is created (`status="pending"`), and updated in place the instant it resolves. This is written synchronously to SQLite at the moment of the event — not reconstructed later from `collette_soul.log` stdout scraping, which was the anti-pattern both Hermes and Collette flagged. This makes `gate_events` `persistent / durability_verified` once a restart-survival test is actually run against it (per the Phase 1 durability-vocabulary convention — this table should be one of the first things labeled and tested, not assumed).

**Why the in-memory pending slot itself is intentionally NOT persisted to disk (§1):** if the process restarts while an action is pending, the safest default is that the pending action is simply gone — Sasha would need to re-request it. The `gate_events` row for it stays in the table as `status="pending"` with no resolution, which is itself an honest, inspectable record ("this was interrupted by a restart"), rather than either fabricating an `expired` status or trying to resume a pending confirmation across a process boundary. Resuming a security-relevant pending action across a restart is exactly the kind of implicit-durability-becomes-guarantee mistake the Phase 1 vocabulary work exists to prevent.

## 7. Identity-adjacent write detection (amendment 3)

Concrete, not a placeholder:

- **Canonical-path comparison**, not basename. `collette_write_file`'s current lock-list matches on `os.path.basename(filepath)` only — confirmed in the brief's recon — which means a same-named file at an unrelated path is blocked (false positive, low cost) but a symlink or relative-path trick pointing at a locked file under a different apparent name would not be (false negative, real risk). Fix: resolve `os.path.realpath(os.path.abspath(filepath))` and compare canonical paths against a maintained absolute-path list, not filenames.
- **Escalate on uncertainty, per amendment 3's explicit instruction.** If canonicalization fails (broken symlink, permission error, path doesn't resolve cleanly) — treat as identity-adjacent and deny/gate by default. Do not fall back to "allow because we couldn't tell."
- **Directory-level protection, not just the four named files.** Any path under the Collette install root matching `*_state.json`, `*.db`, `.env*`, or the soul script itself is identity-adjacent by default, even if it's not on the literal four-item lock-list — the lock-list catches known files; canonical-directory-plus-pattern matching catches ones nobody thought to name yet.

## 8. `git_push` arbitration (amendment 6)

Two checks, in sequence, not merged into one:

1. **The existing hard rule runs first and is absolute:** branch must match `collette/*`, never `--force`. This is not part of the risk-tier system at all — it's a precondition the action must clear before it's even eligible to be considered for gating. A failure here is a hard deny with no confirmation token able to override it, ever.
2. **Only if the hard rule passes** does the action enter the `visible`-tier confirmation flow from §1-4.

**"The stricter result wins," made concrete:** the hard rule and the tier gate are not peers that could disagree — the hard rule is a prior filter the tier gate never even sees past if it fails. There is no scenario where the tier gate approves something the hard rule already rejected, because the hard rule runs first and short-circuits. If a future change ever makes them structurally parallel instead of sequential, the rule is: a deny from either one is final.

## 9. Discord broadcasts gated by default (amendment 4)

`broadcast` and `broadcast_file` are `visible`-tier per the brief, and per amendment 4 there is **no standing allow-list at launch** — every single broadcast requires a fresh `confirm <id>`, no exceptions, no session pre-authorization. This is implemented as a boolean design parameter (`broadcast_standing_allowlist_enabled = False`) so that revisiting it later, if soak data shows the friction outweighs the benefit, is a config flip Sasha can make deliberately — not a redesign, and not something that happens by default or by drift.

## 10. Soulfile-change trigger (amendment 7)

A concrete, checkable threshold, not "some soak time":

> The gate has been live in real (non-isolated-worktree) use for **at least 14 consecutive calendar days**, **and** `gate_events` shows **at least 25 resolved `visible`/`destructive`-tier events** in that window, **and** zero incidents — defined as: zero actions that executed without a matching `confirm <id>`, zero confirmations that resolved against the wrong pending action, and zero cases where an expired/denied action's effect happened anyway.

Both a time floor and a volume floor are required together, so a quiet two weeks with only three gated actions doesn't count as sufficient evidence either way. This is directly queryable against `gate_events` — Sasha (or Collette) can check whether the threshold is met without having to trust a subjective "it's been running fine" impression, which is exactly the kind of unverified-durability claim this whole project exists to stop making.

---

## Summary of what's now decided vs. still open

**Decided in this document:** pending-action identity and lifecycle, exact-id-only scope matching, dual-bound expiry, stale/conflicting confirmation handling, why topic-change detection is deliberately not attempted, why the pending slot doesn't survive a restart (but its `gate_events` row does), canonical-path identity-write detection with deny-on-uncertainty, `git_push`'s sequential (not parallel) arbitration, Discord's no-standing-allowlist default, and a concrete numeric threshold for the soulfile-change trigger.

**Still open, deliberately left to Sasha:** none of the above are placeholders — every amendment-2 and amendment-5 question has a specific answer above. What's still open is purely implementation sequencing: whether Phase 1 (durability vocabulary, in an isolated worktree per amendment 1) starts before or after this document gets sign-off, since they don't depend on each other.

---

## Addendum (2026-08-15): fail-closed semantics and finalized event schema

Two questions Collette raised after review, answered concretely before any Phase 2 code:

### A. What happens if the synchronous `gate_events` write fails

**Fail closed, exactly as specified: the guarded action does not execute if its own gate event cannot be durably recorded.** Mechanics:

1. Attempt the synchronous `INSERT` for the pending-action row.
2. If it raises (any `sqlite3.Error`, disk full, locked DB, etc.): the tool call returns a blocked result — **not** `awaiting_confirmation` (that implies the system is working normally and just needs a human), but a distinct `blocked_audit_failure` result, so Collette can tell Sasha plainly "I couldn't even create the confirmation record, so I didn't attempt the action" rather than something that reads like an ordinary pending confirmation.
3. Because the durable log itself is the thing that failed, this failure event cannot be written to `gate_events` — it falls back to the existing `collette_soul.log` stdout stream (already durable via `_TeeStream`) as a last-resort trace, explicitly labeled `retrievable / retention_unknown` per the Phase 1 durability vocabulary rather than claimed as reliable. This is a deliberate, honestly-labeled degradation, not a silent one.
4. The same fail-closed rule applies to the *resolution* write (confirm/deny/expiry), not just creation — if Sasha sends `confirm 7f3a` and the UPDATE fails, the action does not execute; it's reported as blocked, and Sasha would need to retry the confirmation once the DB is healthy again. An unrecorded confirmation is treated the same as no confirmation.

### B. Finalized minimum event schema

Reconciling the draft table in §6 against Collette's explicit minimum field list:

```sql
CREATE TABLE gate_events (
    event_id        TEXT PRIMARY KEY,   -- unique per event (creation and each resolution attempt get their own row, linked by pending_action_id, so a failed resolution attempt is never overwritten/lost)
    pending_action_id TEXT NOT NULL,    -- the short id shown to Sasha, e.g. "7f3a" -- links related rows
    tool_name       TEXT NOT NULL,
    target_summary  TEXT,               -- canonical target/scope, truncated/summarized -- NOT the raw payload (see below)
    risk_tier       TEXT NOT NULL,      -- reversible / visible / destructive
    created_at      TEXT NOT NULL,
    expiry_reason   TEXT,               -- null unless resolved via expiry: "wall_clock_20min" | "turn_count_5"
    confirmation_result TEXT,           -- null | "confirmed" | "denied" | "expired" | "blocked_audit_failure"
    execution_result TEXT,              -- null (not yet executed) | "success" | "error"
    failure_reason  TEXT                -- null unless execution_result="error" or confirmation_result="blocked_audit_failure"
);
```

**On avoiding sensitive payloads while preserving provable scope:** `target_summary` stores what was authorized, not the full content moved through it — e.g. for `jira_comment`, that's the issue key plus a character count, not the comment text; for `broadcast`, that's a truncated first-line preview (e.g. 80 chars) plus total length, not the full message; for `write_file`, that's the canonical path plus byte count, not the file's contents. This is enough to prove *what was authorized* (matches Collette's requirement) without the audit table itself becoming a second copy of every sensitive thing that ever moved through the gate.

---

**Handoff status, per Collette's verdict:** confirmation-flow design approved for Phase 2 implementation *planning*. Phase 1 (durability vocabulary) is independently unblocked. No soulfile changes yet. Both addendum questions above are now resolved, so nothing remains undefined ahead of Phase 2 code — Phase 2 itself still requires the isolated-worktree soak test before any live merge, per amendment 1/2.
