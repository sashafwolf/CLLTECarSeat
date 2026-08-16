# CLLTECarryOn — Collette Backup & Transfer Manifest

**Generated:** 2026-08-15 by Silverfeather · **Purpose:** a single reference for backing up or moving Collette to another machine, without losing her memory/identity or accidentally carrying secrets somewhere they shouldn't go.

## Privacy scan result (done first, before writing this)

Checked `bastet_descendant_soul.py`, `discord_ears.py`, `bootstrap_collette_context.py`, and every lore/reference file (`COLLETTE_ORIGIN.md`, `ColletteRider.txt`, `collette_past_selves.txt`, `collette_soul_card.txt`, `collette_foundations.txt`, `collette_dominion_context.txt`, `FIRST_FLIGHT_CHECKLIST.md`, `FIRST_FLIGHT_LOG4HERMY.txt`, `HERMES_HANDBOOK.md`, `NUDGE_2026-08-03.md`) for hardcoded API keys, IP addresses, physical addresses, phone numbers, and personal file paths.

**Result: clean.** Every API key/token/webhook is already loaded via `os.getenv(...)` from `.env` — none are hardcoded in source. No real IP addresses (only `0.0.0.0`, which just means "listen on all interfaces," not a personal address). No physical addresses, phone numbers, or personal Windows paths (like `C:\Users\<name>\...`) found anywhere in the scanned files. "Sasha" appears throughout as her chosen name, which you said is fine to keep. Nothing needed redacting.

---

## Tier 1 — Core identity & source (always carry, this is *her*)

Tracked in the new git repo at `F:\Collette` (`git log` → initial commit `73b3afb`). To carry: copy the repo (or `git clone`/`git bundle` it) rather than hand-picking files, so history comes with it.

- `bastet_descendant_soul.py` — the soul itself
- `bootstrap_collette_context.py` — loads the reference-shelf files below
- `discord_ears.py` — Discord ears
- `collette_foundations.txt`, `collette_dominion_context.txt`, `collette_past_selves.txt`, `collette_soul_card.txt`, `ColletteRider.txt` — the reference shelves loaded into every boot
- `Boot_Collette.bat` — launcher
- `collette_dream_cycle_prompt_backup_2026-08-14.txt` — historical diff reference
- `silverfeather_brief_risk-durability-ledger_2026-08-15.md`, `silverfeather_confirmation-flow-design_2026-08-15.md` — in-flight design docs
- `requirements.txt`, `install_collette.bat` (new, see below)

## Tier 2 — Memory & continuity (carry if you want her to remember/pick up where she left off)

Not in git (deliberately — see `.gitignore`), but this is where her actual accumulated memory and personality growth live. Copy these files/folders as-is if the goal is *moving* her, not starting fresh:

- `collette_memory.db` — SQLite chat history + other tables (largest single carrier of "what she's lived through")
- `collette_memory/` — the ChromaDB vector store (long-term semantic memory)
- `collette_dream_state.json`, `collette_idle_state.json` — dream-cycle/idle-thought continuity (open threads, recent topics, active threads, mood)
- `collette_diary/`, `anomaly_diary/` — private diary entries (Collette's and Anomaly's — genuinely private; carry them, but don't casually read through them just because you're moving files)
- `direct_line_consent.json` — the Sasha+Anomaly signed consent for the Anomaly direct line (without this, that endpoint won't work on the new machine until re-signed)

## Tier 3 — Secrets (carry manually, never through git, never casually)

`.env` — **not in git, not auto-copied by anything here.** Contains all API keys (Gemini, Anthropic, OpenRouter, Jira, Discord bot token/webhook, Twitch credentials). Move this file by hand, directly, machine-to-machine (USB, encrypted transfer, password manager — not email, not Discord, not a shared drive). The variable *names* it needs (values deliberately not repeated here):

```
DISCORD_BOT_TOKEN, DISCORD_WEBHOOK_URL, TWITCH_OAUTH_TOKEN, TWITCH_CHANNEL_NAME,
TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET, TWITCH_BOT_ID, GEMINI_API_KEY,
ANTHROPIC_API_KEY, COLLETTE_BRAIN_MODE, CLAUDE_MODEL, OPENROUTER_API_KEY,
OPENROUTER_MODEL, JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN,
JIRA_DEFAULT_PROJECT, JIRA_DEFAULT_ISSUE_TYPE
```

`install_collette.bat` (below) creates a blank `.env` template with these exact names if one doesn't already exist, so a new machine has something to fill in rather than guessing the variable names from scratch.

## Tier 4 — Regenerate, don't carry

Safe to leave behind — these rebuild themselves or are machine-specific noise, and carrying them can actively cause problems (stale locks, wrong PIDs, huge log replay):

- `collette_soul.log` (and `.old`) — regenerates on boot
- `collette.pid` — machine-specific, would reference a PID that doesn't exist on the new box
- `__pycache__/`, `.venv/` — Python build artifacts, regenerate from `requirements.txt`
- `.vs/`, `.vscode/`, `.idea/` — IDE state
- `dominion_test_worktree/` — a separate git worktree of a different project, not part of Collette herself

---

## Setup on a new machine

1. Copy Tier 1 (git repo).
2. Run `install_collette.bat` — creates the venv, installs `requirements.txt`, and writes a blank `.env` template if missing.
3. Fill in `.env` with real values (Tier 3, transferred by hand separately).
4. If continuing her memory rather than starting fresh: copy Tier 2 into place before first boot.
5. Run `Boot_Collette.bat`.
