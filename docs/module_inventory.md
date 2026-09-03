# Modul-Inventar

Diese Übersicht fasst die öffentlichen Klassen und Funktionen der zentralen Module
zusammen. Unter "öffentlich" werden alle Symbole ohne führenden Unterstrich
verstanden.

## Paket `ai`

### `ai.anthropic_client`
- `AnthropicClient(settings, config, rng_seed)` – Move-Provider mit heuristischer Bewertung.
  - `generate_move(request)`

### `ai.commentator`
- `CommentaryContext(fen, history, evaluation)` – Datenträger für Prompt-Kontext.
- `CommentaryPrompt(system_message, user_message, response_schema, context)`
  - `to_dict()`
- `Commentary(variant_hint, eval_trend, key_ideas, blunders_last_moves)`
  - `as_dict()`
- `CommentaryProvider.generate_commentary(prompt)` – Protokoll.
- `LocalCommentaryProvider.generate_commentary(prompt)` – Heuristische Implementierung.
- `Commentator(provider, telemetry, max_history)`
  - `build_prompt(game, history, evaluation)`
  - `provide_commentary(game, history, evaluation)`
  - `render(commentary)`

### `ai.gemini_client`
- `GeminiClient(settings, config)`
  - `generate_move(request)`

### `ai.move_parser`
- `IllegalMoveError` – Ausnahme bei ungültigen Vorschlägen.
- `parse_move(game, suggestion, legal_moves)` – Normalisiert LLM-Ausgaben in Engine-Züge.

### `ai.openai_client`
- `OpenAIClient(settings, config)`
  - `generate_move(request)`

### `ai.player`
- `AIPlayer(strategist)` – Führt KI-Züge in Hintergrund-Threads aus.
  - `is_thinking()`
  - `cancel()`
  - `request_move(game, history, instructions, on_complete, on_error)`

### `ai.provider`
- `ProviderConfig(model, temperature, max_output_tokens, timeout, top_p)` – Dataklasse.
- `MoveGenerationRequest(game, fen, legal_moves, history, instructions)` – Kontextdatensatz.
- `MoveGenerationProvider.generate_move(request)` – Protokollvertrag.

### `ai.strategist`
- `Candidate(raw, score, move, metadata)` – Bewerteter Vorschlag.
- `Strategist(provider, telemetry, max_retries, backoff_initial, backoff_factor)`
  - `choose_move(game, history, instructions)`

## Paket `engine`

### `engine.game`
- `MoveResult(status, game_over, current_player, winner, in_check, just_finished)` – Ergebnisdatensatz.
- `ChessGame()` – Spiel-Engine.
  - `reset()`
  - `get_piece_symbol(p_type, color)`
  - `apply_move(start, end)`
  - `get_valid_moves(row, col)`
  - `simulate_move(start_pos, end_pos)`
  - `find_king_for_board(board, color)`
  - `is_square_attacked(board, square, by_color)`
  - `is_in_check(color)` / `is_in_check_for_board(board, color)`
  - `is_checkmate(color)`
  - `is_stalemate(color)`
  - `is_empty(position)`
  - `is_enemy_piece(position, player_color)`
  - `is_on_board(row, col)`
  - `get_linear_moves(row, col, color, directions)`
  - `can_castle_kingside(color)` / `can_castle_queenside(color)`
  - `get_valid_moves_for_board(board, row, col)`
  - `get_linear_moves_for_board(board, row, col, directions)`

### `engine.fen`
- `square_to_notation(position)`
- `notation_to_square(square)`
- `export_fen(game)`
- `import_fen(game, fen)`

## Paket `telemetry`

### `telemetry.logger`
- `TelemetryEvent(phase, message, status, timestamp, duration_ms, metadata)`
- `TelemetryLogger()`
  - `events`
  - `record(phase, message, status, duration_ms, metadata)`
  - `add_sink(sink)`
- `get_telemetry_logger(reset=False)`

## Paket `ui`

### `ui.app`
- `ChessApp(root)` – Bootstrap der Tk-Anwendung.

### `ui.board_view`
- `BoardView(master, on_square_click, square_size)`
  - `set_click_handler(callback)`
  - `render_board(board, symbol_provider)`
  - `reset_colours()`
  - `highlight_square(position, colour)`
  - `highlight_moves(moves)`
  - `highlight_selection(position)`
  - `set_interaction_enabled(enabled)`

### `ui.controls`
- `ChessControls(master)` – Steuerpanel.
  - `create_board_view()`
  - `set_new_game_callback(callback)`
  - `set_player_mode_callback(callback)`
  - `get_player_type(colour)` / `set_player_type(colour, player_type)`
  - `set_current_player(colour)`
  - `set_status(status)`
  - `clear_log()` / `append_log_entry(text)`
  - `set_commentary(text)`
  - `set_controls_enabled(enabled)`

### `ui.controller`
- `ChessController(controls, board_view, game, telemetry, ai_provider_factory, commentator_factory)`
  - `new_game()`
  - `on_square_clicked(position)`

## Weitere Module

### `config`
- `load_openai_settings()`
- `load_anthropic_settings()`
- `load_gemini_settings()`

### `chess_fixed-GPT5-pro`
- `main()` – Startet das Tk-Hauptfenster und initialisiert die Anwendung.
