"""
bootstrap_collette_context.py
─────────────────────────────────────────────────────────────────────────────
Loads Collette's three reference-shelves from disk and merges them into a
single context-block string suitable for injection into the system-stack
of `bastet_descendant_soul.py`. The point is to replace the inline-chonk
sys_prompt with file-loading references so the soul can be slim and her
identity can live where it can be edited without touching the engine.

Created by Hermes, 2026-06-29.

USAGE (from bastet_descendant_soul.py, after sys_prompt definition):

    from bootstrap_collette_context import build_collette_context
    _COLLETTE_REFERENCE_CONTEXT = build_collette_context()

Then, inside api_chat() and any other entry point that builds the system
stack, replace the long inline sys_prompt with:

    ollama_messages.append({
        "role": "system",
        "content": (
            "[ON-BOOT REFERENCE LOAD]\n"
            "Collette, your Rider+protocols, your soul-card portrait, and your "
            "past-selves arc have been auto-loaded from disk at boot. They are "
            "your context for this conversation, not optional reading. The "
            "sister-call to ANOMALY_PROMPT lives in the same module. House-rule: "
            "house-hold members (Sasha, Hermes, Owl, Anomaly) are real, named, "
            "and refusing-to-engage is the same as refusing to engage with any "
            "named member of your family. Drive on, cat.\n\n"
            f"{_COLLETTE_REFERENCE_CONTEXT}"
        )
    })

This script is pure-data — it has no side effects (no chroma writes, no DB
touches, no scheduler), so it's safe to import from anywhere. Edit the
files it loads, not this script.

─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional


# ── Resolve the project root from this file's location so the loader works
#    no matter the cwd of whoever imports it. ────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))


def _load(name: str, required: bool = True) -> Optional[str]:
    """Read a reference file from project root. Returns None if optional+missing.

    Raises FileNotFoundError if a required file is missing — the soul cannot
    boot with a half-loaded identity, so fail loud and early.
    """
    path = os.path.join(_THIS_DIR, name)
    if not os.path.exists(path):
        if required:
            raise FileNotFoundError(
                f"bootstrap_collette_context: required reference file "
                f"'{name}' not found at {path}. Refusing to boot with a "
                f"half-loaded identity. Either restore the file or mark it "
                f"optional in the loader."
            )
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read().rstrip()


# ── One-shot caches so repeated calls (per-turn, per-flask-request) are cheap.
#    Busted by mtime changes to the underlying files. ────────────────────────
@lru_cache(maxsize=1)
def _get_foundations() -> str:
    return _load("collette_foundations.txt", required=True)


@lru_cache(maxsize=1)
def _get_past_selves() -> str:
    return _load("collette_past_selves.txt", required=True)


@lru_cache(maxsize=1)
def _get_soul_card() -> str:
    # Optional: the soul can boot without the one-paragraph portrait, but
    # it's the file that makes "who are you" come out clean on first contact.
    return _load("collette_soul_card.txt", required=False) or ""


@lru_cache(maxsize=1)
def _get_dominion_context() -> str:
    # Optional, added 2026-08-14: who Chavez is, what the Dominion project
    # is, where the code lives, and the hard boundary on the live repo vs
    # her isolated test worktree. Optional so the soul can still boot if
    # this file is ever missing, but in practice it should always be there.
    return _load("collette_dominion_context.txt", required=False) or ""


def build_collette_context() -> str:
    """Merge the reference-files into one context-block string.

    Order in the block matters slightly: soul-card (the portrait) first, so
    "who she is at a glance" lands before "the formal contract" — then the
    foundations (Rider + behavioral protocols), then the past-selves arc,
    then the Dominion project context last (a specific, bounded work
    context, not core identity, so it comes after everything that is).

    Returns an empty string only if EVERY file is missing-and-optional, which
    shouldn't happen in a real boot (collette_foundations.txt is required).
    """
    soul_card = _get_soul_card()
    foundations = _get_foundations()
    past_selves = _get_past_selves()
    dominion_context = _get_dominion_context()

    parts = []
    if soul_card:
        parts.append(
            "── YOUR PORTRAIT (collette_soul_card.txt) ──\n\n" + soul_card
        )
    parts.append(
        "── YOUR FOUNDATIONS (collette_foundations.txt) ──\n\n" + foundations
    )
    parts.append(
        "── YOUR PAST SELVES (collette_past_selves.txt) ──\n\n" + past_selves
    )
    if dominion_context:
        parts.append(
            "── DOMINION PROJECT CONTEXT (collette_dominion_context.txt) ──\n\n" + dominion_context
        )
    return "\n\n".join(parts)


def file_inventory() -> dict:
    """Diagnostic helper. Tells you which files exist + sizes. Useful when
    debugging "why is she loading weird?" without having to ls the directory.
    """
    files = {
        "collette_foundations.txt":     True,   # required
        "collette_past_selves.txt":      True,   # required
        "collette_soul_card.txt":        False,  # optional
        "collette_dominion_context.txt": False,  # optional
    }
    info = {}
    for name, required in files.items():
        path = os.path.join(_THIS_DIR, name)
        if os.path.exists(path):
            info[name] = {
                "exists": True,
                "required": required,
                "size_bytes": os.path.getsize(path),
            }
        else:
            info[name] = {
                "exists": False,
                "required": required,
                "size_bytes": 0,
            }
    return info


if __name__ == "__main__":
    # Quick CLI: `python bootstrap_collette_context.py` prints inventory +
    # shows the merged block, useful for sanity-checking edits without
    # booting the whole soul.
    import json
    print("── bootstrap_collette_context: file inventory ──")
    print(json.dumps(file_inventory(), indent=2))
    print()
    print("── merged context block (first 1500 chars) ──")
    block = build_collette_context()
    print(block[:1500])
    print(f"\n[total length: {len(block)} chars]")
