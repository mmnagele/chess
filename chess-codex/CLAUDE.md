# CLAUDE.md

Guidance for Claude Code when working in THIS repository.

This repository is a desktop Chess application with:
- a full chess rules engine,
- optional AI players (OpenAI / Anthropic / Gemini) via real APIs only,
- an optional AI commentator with selectable commentary modes,
- a PySide6 UI (dark + neon styling) and session logging.

## Non-negotiables (must always be true)

1. This is the chess repo. Legacy non-chess platform content must not exist here.
2. No local fallback AI providers are allowed.
3. API keys are read only from environment variables:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GEMINI_API_KEY`
   No `.env` loading and no alternate variable names.
4. UI must stay responsive. Network calls run off the UI thread and UI updates are marshaled back safely.
5. Documentation must match implementation.

Sanity check:

```bash
env | grep -E 'ANTHROPIC_API_KEY|GEMINI_API_KEY|OPENAI_API_KEY'
```

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 __main__.py
# or:
./start.sh
```

## Build / Quality Commands

```bash
python3 -m pytest
ruff check .
black --check .
black .
```

## Runtime Dependencies

- `PySide6`
- `openai`
- `anthropic`
- `google-genai`

## Functional Requirements

- White and Black are configurable independently: `Human` or `AI`.
- If AI is selected, provider and model are selectable.
- Commentator can be enabled/disabled and supports:
  - Adult Coach
  - Parent + 5-Year-Old Coach
  - Tournament Commentator
- Human-in-the-loop move execution:
  - AI suggests a move,
  - user applies it by clicking,
  - next prompts are sent afterward.
- Three chat logs + inputs:
  - White AI
  - Black AI
  - Commentator
- Separate move/event log.
- Board UI includes marble-style squares, coordinates, and neon highlights.

## Architecture

- `engine/` - chess rules, legality checking, FEN helpers.
- `ai/` - provider clients and prompt orchestration.
- `prompts/` - prompt templates.
- `ui/` - PySide6 GUI and controller.
- `telemetry/` - session logging.

## AI Provider Rules

- Use official SDKs.
- Never hardcode or log keys.
- Use request timeouts and retry transient failures.
- Move parsing relies on `MOVE: <uci>` output contract.
- Illegal AI moves are logged and retried with legal-move feedback.

## Logging / Telemetry

Each game writes a JSONL session file under `logs/` and includes:
- `app_start` / `game_start`
- `prompt_sent`
- `response_received`
- `move_played`
- `errors`

Never log secrets.

## Acceptance Checklist

- No legacy non-chess content/dependencies.
- Runtime requirements match imports.
- No local fallback providers remain.
- Keys are read only from the three supported env vars.
- UI provides player/commentator configuration, three chats, separate move log, and highlighted coordinate board.
- Session log file is created and excludes secrets.
- Tests and formatting pass.
- Docs match implementation.
