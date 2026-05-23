# CLAUDE.md

Guidance for Claude Code when working in THIS repository.

This repository is a **desktop Chess application** with:
- a full chess rules engine,
- optional AI players (OpenAI / Anthropic / Gemini) via **real APIs only**,
- an optional AI commentator with selectable commentary modes,
- a modern **PySide6** UI (dark + neon styling) and session logging.

---

## Non-negotiables (must always be true)

1) **This is the CHESS repo.**
- No unrelated code, docs, or dependencies.

2) **NO heuristic / local "AI" providers.**
- Every AI move/commentary must come from a real API call.

3) **API keys are read ONLY from environment variables (nowhere else).**
- Supported keys:
  - `OPENAI_API_KEY`
  - `ANTHROPIC_API_KEY`
  - `GEMINI_API_KEY`
- Do NOT load `.env` files.
- Do NOT support alternate variable names.
- Never print or log keys (redact secrets).

Agent sanity check:
```bash
env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'
```

4) **UI must not freeze.**
- All network calls (AI) must run off the UI thread (Python threads + Qt signals).

5) **Docs must match reality.**
- If a statement becomes false, update or delete it immediately.

---

## Quickstart

```bash
# Create venv (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install runtime deps
pip install -r requirements.txt

# Run the app
python3 __main__.py
# or:
./start.sh
```

---

## Build & Quality Commands

```bash
# Tests
python3 -m pytest

# Lint & format
ruff check .
black --check .

# Auto-format
black .
```

---

## Runtime Requirements

- PySide6 (Qt for Python)
- API calls use Python stdlib HTTP (urllib)

Dev tools: pytest, ruff, black (in requirements-dev.txt).

---

## Architecture

Four-layer structure:

- `engine/` -- Chess rules + game state (FEN import/export, legal move generation)
- `ai/` -- Provider clients (OpenAI, Anthropic, Gemini) + AIPlayer thread wrapper + move parsing
- `ui_qt/` -- PySide6 GUI (main window, widgets, controller). AI callbacks marshalled via Qt signals/slots.
- `telemetry/` -- Session logging (JSONL)

Prompts live in `prompts/` and are loaded by the `ai/` layer.
Assets (SVG pieces) live in `assets/pieces/`.

---

## AI Output Contract

All move-generation calls use a strict output format:
First line must be: `MOVE: e2e4` (coordinate move, promotion suffix optional).
The move parser normalizes and validates the move against engine legal moves.
Illegal/unparseable moves trigger an automatic retry prompt with a legal-moves list.

---

## UI Sanity Checklist

Quick manual checks after making UI changes:

1. **4K scaling** -- Run at fullscreen 4K. Board coordinates (a-h, 1-8) must never clip. Font size is clamped between 9px and 28px.
2. **Button readability** -- Verify normal / hover / pressed / disabled states for "New Game" (primary) and "Send" / "Clear" (default) buttons. Text must be readable in every state.
3. **API key detection** -- Set API keys via `env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'`. Provider dropdowns must NOT show "(missing key)" for set keys. Use the "Reload Keys" toolbar button to refresh at runtime. Check the Move Log for `[keys]` diagnostic lines.
4. **Capture animation** -- Select a piece that can capture. Blue ring shows on capture squares. Execute the capture; an inflate-then-implode blue ring animation plays once (~350 ms).
5. **Last-move highlight** -- After any move, both from/to squares show a strong red tint overlay that persists until the next move.
6. **Legal-move indicators** -- Selecting a piece shows neon cyan dots for non-capture moves and blue rings for capture moves.
