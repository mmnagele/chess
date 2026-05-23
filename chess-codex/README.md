# Chess (PySide6): Human + AI + Commentator

Desktop chess app with a full rules engine, API-backed AI per side, optional AI commentator, and per-role chat transcripts.

## Quickstart

Requirements: Python 3.10+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 __main__.py
# or ./start.sh
```

## API Keys (Environment Variables Only)

This app reads provider keys only from process environment variables:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

No config files, no hard-coded keys, and no key persistence are used.

## Key Diagnostics and Troubleshooting

Use `Reload Keys` to re-read `os.environ` at runtime and refresh provider dropdown labels immediately.
Use `Key Diagnostics` for a detailed visibility report (safe only: present/length + process context hints).

If keys still appear as `(missing key)`, verify the exact launch environment:

```bash
env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'
```

Common causes and fixes:

- IDE/GUI launch did not inherit exported shell variables.
- Start the IDE from a terminal with exports, or add env vars to the IDE run config.
- Avoid launching via `sudo` (it strips environment by default).

Optional shell probing can be enabled explicitly with `CHESS_IMPORT_KEYS_FROM_LOGIN_SHELL=1`.
It is disabled by default and guarded to Linux/macOS.

## Features

- Full chess rules: castling, en passant, promotion, check/checkmate/stalemate.
- Per-side mode: `Human` or `AI`.
- Provider + model selectors for each AI side and commentator.
- Visual move guidance:
  - Neon yellow-green legal move dots
  - Strong red last-move highlights on both from/to squares
  - Blue capture rings with capture animation (incl. en passant)
- Configurable commentator personas:
  - `Adult Coach`
  - `Parent + 5-Year-Old Coach`
  - `Tournament Commentator`
- Three chats: commentator, white AI, black AI.
- Move/event log with safe key diagnostics lines.

## Repository Layout

- `engine/`: chess rules and board state
- `ai/`: provider clients, prompt pack, move parsing, strategist, commentator
- `ui/`: Qt controls, board renderer, controller, app bootstrap
- `telemetry/`: runtime telemetry + session jsonl logger
- `assets/pieces/`: SVG piece set

## Development

```bash
python3 -m pytest
ruff check .
black --check .
```

## Visual Verification and Screenshots

- UI acceptance checklist: `docs/ui_sanity_checklist.md`
- Button/state screenshots: `docs/screenshots/`
