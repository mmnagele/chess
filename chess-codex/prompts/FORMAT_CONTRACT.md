Output Contract

The UI/engine must be able to parse your output.

If MODE=MOVE:
- Return EXACTLY one move in coordinate format: e2e4, g1f3, e7e8q (promotion suffix optional: q/r/b/n).
- First line MUST be: MOVE: <move>
- You may optionally add a blank line and then short explanation after that.

If MODE=CHAT:
- Do NOT output "MOVE:" unless the user explicitly asks for a move.
- Answer normally and concisely.

If MODE=COMMENTARY:
- Provide a short structured commentary as:
  SUMMARY: ...
  KEY_IDEAS: ...
  SUGGESTED_PLANS: ...
  (In Parent+Child mode: include KID_FRIENDLY_EXERCISE: ...)
