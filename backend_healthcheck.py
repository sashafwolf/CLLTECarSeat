"""
backend_healthcheck.py -- standalone, read-only sanity check for Collette's
tool-facing surface (file I/O, memory/state files, git, Jira, Dominion repo
presence, live-log access) plus a record of which brain backend is
currently configured.

Why standalone: this is meant to catch a broken tool-calling surface
*after* a brain-backend swap (e.g. Ollama -> Opus). If the swap breaks
Collette's own >>>TOOL {...} <<< dispatch, she may not be able to reliably
invoke a self-check tool -- so this runs independently of her, with no
dependency on the model actually working. It never writes to production
state, never touches the Dominion canon repo beyond `git status`, and
never runs the Dominion test suite (that's slow and not what this checks --
see the DominionRepoPresence check for what IS verified).

Usage: python backend_healthcheck.py
Exit code: 0 if all checks pass, 1 if any FAIL (WARN does not fail the run).
Writes a dated report to healthchecks/<timestamp>_backend_healthcheck.md
and prints a summary to stdout.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
import requests

load_dotenv()

HERE = os.path.dirname(os.path.abspath(__file__))
DOMINION_LIVE_REPO = os.path.normpath(r"F:\Project S\dominion-4-20-server-master")
DOMINION_LIVE_LOG_DIR = os.path.join(
    DOMINION_LIVE_REPO, "server", "GameServer-indev", "GameServerConsole",
    "bin", "x86", "Debug", "net6.0", "Logs"
)
DOMINION_SLN = os.path.join(DOMINION_LIVE_REPO, "server", "GameServer-indev", "GameServer.sln")
DOMINION_TESTS_CSPROJ = os.path.join(
    DOMINION_LIVE_REPO, "server", "GameServer-indev",
    "GameServerLibTests", "GameServerLibTests.csproj"
)

REQUIRED_IDENTITY_FILES = [
    "collette_foundations.txt", "ColletteRider.txt", "collette_past_selves.txt",
    "collette_soul_card.txt", "collette_dominion_context.txt",
]
REQUIRED_STATE_FILES = ["collette_idle_state.json", "collette_dream_state.json"]

results = []  # list of (name, status, detail)


def check(name):
    def decorator(fn):
        try:
            status, detail = fn()
        except Exception as e:
            status, detail = "FAIL", f"unhandled exception: {e}"
        results.append((name, status, detail))
        return fn
    return decorator


@check("File read: identity files")
def _identity_files():
    missing = [f for f in REQUIRED_IDENTITY_FILES if not os.path.isfile(os.path.join(HERE, f))]
    if missing:
        return "FAIL", f"missing: {', '.join(missing)}"
    sizes = {f: os.path.getsize(os.path.join(HERE, f)) for f in REQUIRED_IDENTITY_FILES}
    empty = [f for f, s in sizes.items() if s == 0]
    if empty:
        return "FAIL", f"present but empty: {', '.join(empty)}"
    return "PASS", f"{len(REQUIRED_IDENTITY_FILES)} identity files present and non-empty"


@check("Directory listing: F:\\Collette")
def _dir_listing():
    entries = os.listdir(HERE)
    if len(entries) < 5:
        return "FAIL", f"only {len(entries)} entries found, expected a real project directory"
    return "PASS", f"{len(entries)} entries listed"


@check("Memory/state file lookup + JSON validity")
def _state_files():
    bad = []
    for f in REQUIRED_STATE_FILES:
        path = os.path.join(HERE, f)
        if not os.path.isfile(path):
            bad.append(f"{f}: missing")
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                json.load(fh)
        except Exception as e:
            bad.append(f"{f}: invalid JSON ({e})")
    if bad:
        return "FAIL", "; ".join(bad)
    return "PASS", f"{len(REQUIRED_STATE_FILES)} state files present and valid JSON"


@check("Git status: Collette soul repo")
def _git_collette():
    try:
        out = subprocess.run(
            ["git", "-c", f"safe.directory={HERE}", "-C", HERE, "status", "--short"],
            capture_output=True, text=True, timeout=20
        )
    except FileNotFoundError:
        return "FAIL", "git executable not found on PATH"
    if out.returncode != 0:
        return "FAIL", f"git status failed: {out.stderr.strip()[:300]}"
    dirty = out.stdout.strip()
    if dirty:
        return "WARN", f"working tree not clean ({len(dirty.splitlines())} changed entries) -- expected during active work"
    return "PASS", "working tree clean"


@check("Git status: Dominion canon repo")
def _git_dominion():
    if not os.path.isdir(DOMINION_LIVE_REPO):
        return "FAIL", f"repo not found at {DOMINION_LIVE_REPO}"
    try:
        out = subprocess.run(
            ["git", "-C", DOMINION_LIVE_REPO, "-c", f"safe.directory={DOMINION_LIVE_REPO}",
             "status", "--short", "--branch"],
            capture_output=True, text=True, timeout=20
        )
    except FileNotFoundError:
        return "FAIL", "git executable not found on PATH"
    if out.returncode != 0:
        return "FAIL", f"git status failed: {out.stderr.strip()[:300]}"
    first_line = out.stdout.splitlines()[0] if out.stdout.strip() else "(no output)"
    return "PASS", f"branch: {first_line}"


@check("Jira API reachability")
def _jira():
    base_url = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_EMAIL")
    token = os.getenv("JIRA_API_TOKEN")
    if not (base_url and email and token):
        return "WARN", "JIRA_BASE_URL/JIRA_EMAIL/JIRA_API_TOKEN not fully configured in .env"
    try:
        resp = requests.post(
            f"{base_url}/rest/api/3/search/jql",
            auth=(email, token),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            json={"jql": "project = DOM ORDER BY updated DESC", "maxResults": 1, "fields": ["summary"]},
            timeout=15,
        )
    except requests.exceptions.RequestException as e:
        return "FAIL", f"request failed: {e}"
    if resp.status_code != 200:
        return "FAIL", f"HTTP {resp.status_code}: {resp.text[:200]}"
    return "PASS", "live search/jql call returned 200"


@check("Dominion repo presence (sln + test project, not a full run)")
def _dominion_presence():
    missing = [p for p in (DOMINION_SLN, DOMINION_TESTS_CSPROJ) if not os.path.isfile(p)]
    if missing:
        return "FAIL", f"missing: {missing}"
    try:
        out = subprocess.run(["dotnet", "--version"], capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        return "FAIL", "dotnet executable not found on PATH"
    if out.returncode != 0:
        return "FAIL", "dotnet --version failed"
    return "PASS", f"sln + test project present, dotnet {out.stdout.strip()} available (no build/test run)"


@check("Dominion live log access (watch_game_log surface)")
def _live_log():
    if not os.path.isdir(DOMINION_LIVE_LOG_DIR):
        return "WARN", f"log dir not found (server never booted?): {DOMINION_LIVE_LOG_DIR}"
    logs = [f for f in os.listdir(DOMINION_LIVE_LOG_DIR) if f.lower().endswith(".log")]
    if not logs:
        return "WARN", "log dir exists but no .log files present"
    newest = max(logs, key=lambda f: os.path.getmtime(os.path.join(DOMINION_LIVE_LOG_DIR, f)))
    try:
        with open(os.path.join(DOMINION_LIVE_LOG_DIR, newest), "r", errors="ignore") as fh:
            fh.readlines()[-1:]
    except Exception as e:
        return "FAIL", f"found {newest} but could not read it: {e}"
    return "PASS", f"read newest log file: {newest}"


@check("Active backend configuration")
def _backend_config():
    mode = os.getenv("COLLETTE_BRAIN_MODE", "ollama")
    claude_model = os.getenv("CLAUDE_MODEL", "(unset)")
    openrouter_model = os.getenv("OPENROUTER_MODEL", "(unset)")
    has_anthropic_key = bool(os.getenv("ANTHROPIC_API_KEY"))
    detail = (
        f"COLLETTE_BRAIN_MODE={mode} | CLAUDE_MODEL={claude_model} | "
        f"OPENROUTER_MODEL={openrouter_model} | ANTHROPIC_API_KEY set={has_anthropic_key}"
    )
    return "PASS", detail


def main():
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%d_%H%M%S")

    lines = [
        f"# Backend/Tool Health Check -- {now.isoformat()}",
        "",
        "Read-only checks. WARN does not fail the run; FAIL does.",
        "",
        "| Check | Status | Detail |",
        "|---|---|---|",
    ]
    fail_count = 0
    warn_count = 0
    for name, status, detail in results:
        if status == "FAIL":
            fail_count += 1
        elif status == "WARN":
            warn_count += 1
        lines.append(f"| {name} | **{status}** | {detail} |")

    pass_count = len(results) - fail_count - warn_count
    summary = f"{pass_count} PASS / {warn_count} WARN / {fail_count} FAIL out of {len(results)} checks"
    lines.insert(3, f"**Summary:** {summary}")
    lines.insert(4, "")

    report_dir = os.path.join(HERE, "healthchecks")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"{stamp}_backend_healthcheck.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")

    print(f"Backend health check -- {summary}")
    for name, status, detail in results:
        marker = {"PASS": "OK ", "WARN": "!! ", "FAIL": "XX "}[status]
        print(f"  [{marker}{status:4}] {name}: {detail}")
    print(f"\nReport written to {report_path}")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
