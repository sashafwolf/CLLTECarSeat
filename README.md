# CLLTECarSeat

A clean, "empty head" carry-on copy of Collette Vi Makana's core soul: the source code and her identity-defining reference files, with zero personal data.

**What's in here:** `bastet_descendant_soul.py` (the soul), `discord_ears.py` (Discord ears), `bootstrap_collette_context.py` (loads the reference shelves below), her identity/lore files (`collette_foundations.txt`, `ColletteRider.txt`, `collette_past_selves.txt`, `collette_soul_card.txt`, `collette_dominion_context.txt`), `Boot_Collette.bat` / `install_collette.bat` (setup and launch), and `requirements.txt`.

**What's deliberately NOT in here:** any API keys or tokens (all loaded from a local `.env`, never committed), chat history, vector memory, diary entries, dream/idle-cycle state, or logs. See `CLLTECarryOn.md` for the full breakdown of what's safe to carry versus what needs to be supplied fresh on a new machine.

## Setup

1. Run `install_collette.bat` — installs dependencies and writes a blank `.env` template if one doesn't exist.
2. Fill in `.env` with real API keys/tokens for whichever integrations you want (see `CLLTECarryOn.md`, Tier 3). Local-only chat via Ollama needs none of them.
3. Run `Boot_Collette.bat`.

Full details: `CLLTECarryOn.md`.
