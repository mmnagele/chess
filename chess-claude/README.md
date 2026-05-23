# Chess (PySide6) - Multi-Provider AI + Commentator

PySide6-based chess game with full rules engine, API-backed AI integrations, and a dark neon UI with marble board.

## Quickstart

Requirements: Python >= 3.10, PySide6.

```bash
pip install -r requirements.txt
python3 __main__.py
# or
./start.sh
```

## API Keys (Environment Only)

Set keys in your shell environment:

- `OPENAI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GEMINI_API_KEY`

No `.env` loading is used.

Check current environment:

```bash
env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'
```

## Features

- Full chess rules: castling, en passant, promotion, check/checkmate/stalemate.
- White/Black player mode: `Human` or `AI`.
- For each AI side: provider dropdown (`OpenAI`, `Anthropic`, `Gemini`) and model dropdown with presets plus `(Custom...)`.
- Commentator controls:
  - On/Off toggle
  - Type: `Adult Coach`, `Parent + 5-Year-Old Coach`, `Tournament Commentator`
  - Provider + model selection
  - `Adult plays` side selector
- Three independent chats:
  - Commentator Chat
  - White AI Chat
  - Black AI Chat
- AI move flow is suggestion-first:
  - AI returns a suggested legal move
  - UI highlights from/to squares with neon accents
  - User executes moves by clicking on board
- Dark neon theme with marble-textured chessboard
- SVG chess pieces with neon selection/move highlights
- Board coordinate labels (a-h, 1-8)
- Prompt pack stored under `prompts/`.
- Session JSONL logs under `logs/chess_session_YYYYMMDD_HHMMSS.jsonl`.

## Architecture

- `engine/`: chess rules and board state
- `ai/`: provider clients, prompt loader, move parsing, strategist, commentator
- `ui_qt/`: PySide6 main window, widgets (board, chat, config panels), controller with Qt signals/slots
- `telemetry/`: in-memory telemetry + persistent session logger
- `prompts/`: prompt templates for player and commentator AI
- `assets/pieces/`: SVG chess piece files

## Development

```bash
pip install -r requirements-dev.txt
python3 -m pytest
ruff check .
black --check .
```

## Troubleshooting

### API keys not detected

**GUI / IDE launch:** If you launched the app from a desktop shortcut, file
manager, or IDE, your shell `export` statements may not be inherited. Launch
from a terminal where the keys are exported.

**sudo stripping env:** Running with `sudo` strips most environment variables.
Use `sudo -E` to preserve them, or avoid `sudo` entirely.

**.env files are NOT loaded:** This app reads keys only from `os.environ`.
Add `export OPENAI_API_KEY=sk-...` (etc.) to your shell profile
(`~/.bashrc`, `~/.zshrc`).

**Whitespace-only keys:** Keys that consist only of spaces are treated as
missing. Check for accidental whitespace in your exports.

**Reload at runtime:** Use the **Reload Keys** toolbar button to re-read
environment variables without restarting the app. You can also click
**Key Diagnostics** for a detailed status report.

**Verify keys from the terminal:**

```bash
env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'
```
