# Schach (Tkinter) – Engine & LLM‑Roadmap

**Stand heute:** lauffähiges Tkinter‑Schach mit stabilisierter *En Passant*‑Erkennung, korrekter Schach-/Schachmatt‑Logik, legaler Rochade, gelber Zugmarkierung und Dame‑Umwandlung. Einstieg über `chess_fixed.py`. Die ursprüngliche, einteilige Implementierung war `chess.py`. 

---

## Inhaltsverzeichnis

* **Teil 1 – Projektstand & Code‑Erklärung**

  * Quickstart
  * Architekturüberblick (UI, Engine, Datenmodell)
  * Zugerzeugung & Regelprüfung (inkl. En Passant, Rochade, Schach/Matt/Patt)
  * Spielablauf & Zustandswechsel
  * Wichtige Invarianten
* **Teil 2 – Weiterentwicklung zur Vision**

  * 1. Aufteilung in mehrere Module/Dateien (vorgeschlagene Struktur)
  * 2. KI‑Gegner (OpenAI‑Modelle, agentischer 3‑Phasen‑Flow, Logging‑Panel)
  * 3. Spielermodi: Mensch vs. KI, KI vs. KI
  * 4. Kommentator‑Funktion (separates KI‑Modell, linkes Panel)
  * 5. Anbieterabstraktion: Start mit OpenAI, danach Google/Anthropic
  * Querschnittsthemen: Robustheit, Validierung, Tests, Telemetrie
  * Konkreter Umsetzungsplan (Meilensteine)

---

## Teil 1 – Projektstand & Code‑Erklärung

### Quickstart

* **Voraussetzungen:** Python ≥ 3.10, Standardbibliothek (Tkinter ist bei den meisten Python‑Distributionen enthalten).
* **Starten:**

  ```bash
  python chess_fixed.py
  ```
* **Steuerung:** Klick auf eine eigene Figur zeigt **gelb** alle legalen Felder. Klick auf ein gelbes Feld führt den Zug aus. Statuszeile meldet **Schach**, **Schachmatt** oder **Patt**.

### Architekturüberblick

**GUI (Tkinter)**

* `Tk()`‑Root, **Controls‑Leiste** (neues Spiel, Farbanzeige, Status) und **Brett‑Frame** (8×8 `Label`‑Widgets).
* Click‑Handler `on_square_click(r, c)`:

  1. Figur wählen → `get_valid_moves` berechnet legale Züge → **gelb** markieren.
  2. Ziel wählen → `move_piece` → `change_player` → Status prüfen/anzeigen.

**Engine (im selben File, klar getrennte Methoden)**

* **Board**: `dict[(row, col)] -> (color, pieceType)`; leere Felder sind `None`.
  Koordinaten laufen von **0..7**. Weiss auf Reihe 7/6, Schwarz auf 0/1.
* **Staat & Regeln**:

  * `current_player` – am Zug.
  * **Rochaderechte** pro Farbe: `{'K': True, 'Q': True}` (kurz/lang).
  * **En Passant**: `en_passant_target` + `en_passant_expires` (Halbzug‑Ablauf).
  * **halfmove_clock** – Halbzugzähler zur präzisen En‑Passant‑Gültigkeit.
  * `game_over` – blockiert Eingaben nach Matt/Patt.

**Darstellung**

* Unicode‑Symbole (♔♕♖♗♘♙ bzw. ♚♛♜♝♞♟).
* Hintergrundfarben des Bretts bleiben klassisch weiss/grau; **gelb** markiert mögliche Züge.

### Zugerzeugung & Regelprüfung (Kernlogik)

**Allgemein**

* `get_valid_moves(r, c)` erzeugt *pseudo‑legale* Kandidaten (gemäss Figurentyp) und filtert danach alle Züge heraus, die den eigenen König **im Schach** lassen würden.
  Dies geschieht über `simulate_move(start, end)` → `is_in_check_for_board(board_copy, color)`.

**Bauern**

* Vorwärts 1 Feld (wenn frei), vom Start 2 Felder, **Schlagen** diagonal.
* **En Passant**:

  * Beim Doppelzug wird `en_passant_target` (Zwischenfeld) gesetzt und `en_passant_expires = halfmove_clock + 1`.
  * Nur im **unmittelbar folgenden Halbzug** des Gegners ist dieses Ziel gültig.
  * Beim Ausführen eines En‑Passant‑Zuges wird der übersprungene Bauer auf `(start.row, end.col)` entfernt.
* **Promotion**: Erreicht ein Bauer Grundreihe, wird er automatisch zur Dame (`'Q'`).

**Türme/Läufer/Dame**

* Lineare Strahlen per `get_linear_moves(...)` mit Blockade an erster besetzter Kachel.
* **König als Schlagziel ausgeschlossen** (regelkonform; König kann nicht „weggenommen“ werden).

**Springer**

* Klassische L‑Muster; Ziel darf leer oder gegnerisch sein (ausser König).

**König**

* 8 Nachbarfelder, ohne in Schach zu ziehen.
* **Rochade**:

  * Kurz: König e→g (Spalte 4→6), Turm h→f.
  * Lang: König e→c (4→2), Turm a→d.
  * Bedingungen:

    1. König/Turm auf Startfeldern, entsprechende **Rochaderechte** vorhanden.
    2. Zwischenfelder frei.
    3. Felder **e**, **Zwischenfeld** und **Zielfeld des Königs** sind **nicht angegriffen**.
  * Rechte werden beim Königszug stets, beim Turmzug **vom Startfeld** sowie beim **Schlagen eines Startturms** korrekt zurückgesetzt.

**Schach, Schachmatt, Patt**

* `is_square_attacked(board, square, by_color)` prüft Angriffe über *pseudo‑legale* Gegenzüge (für Bauern nur Diagonalfelder als Drohung).
* `is_in_check_for_board` findet die König‑Position **aus dem Board** (kein veralteter Cache).
* `is_checkmate(color)`: **im Schach** und **kein legaler Zug**.
* `is_stalemate(color)`: **nicht** im Schach und **kein legaler Zug**.
* Nach jedem Zug: `change_player()` erhöht `halfmove_clock`, räumt abgelaufenes En Passant auf, wechselt Spieler und bewertet **Schach/Matt/Patt**.

### Spielablauf & Zustandswechsel

1. **Auswahl**: Klick auf eigene Figur → `get_valid_moves` → gelbe Felder.
2. **Zug**: Klick auf gelbes Feld → `move_piece` (inkl. Spezialfälle En Passant/Rochade/Promotion) → `update_board`.
3. **Zustand**: `change_player` behandelt En‑Passant‑Ablauf, Seitenwechsel, Endzustände (Dialog + `game_over = True`).
4. **Sperre**: Bei `game_over` werden weitere Klicks ignoriert.

### Wichtige Invarianten (für künftige Änderungen)

* Ein König **darf nie** als Schlagziel auftauchen; Legalität filtert solche Kandidaten.
* En Passant ist **ausschliesslich** im Halbzug **direkt nach** dem Doppelzug erlaubt (über `en_passant_expires`).
* Rochaderechte hängen **immer** an König/Turm‑Startfeldern und werden **sofort** aktualisiert, wenn König/Turm ziehen oder Starttürme geschlagen werden.
* Legale Züge prüfen **immer** die Königsicherheit **nach** Simulation.

---

## Teil 2 – Weiterentwicklung zur Vision

### Zielbild (kurz)

* **Saubere Modulstruktur** (Engine/GUI/Adapter).
* **KI‑Gegner** via OpenAI‑Modelle (z. B. GPT‑4o‑mini) mit 3‑stufiger „agentischer“ Abfrage und **rechtsseitigem Log‑Panel**.
* **Spielermodi**: Mensch vs. KI, KI vs. KI (beide Seiten frei wählbar).
* **Kommentator** (separates Modell, linkes Panel).
* **Provider‑Abstraktion**: Start mit OpenAI; später Google & Anthropic.

---

### 1) Aufteilung in mehrere sinnvoll gewählte Dateien

**Vorgeschlagene Paketstruktur**

```
chess_app/
  app/
    __init__.py
    main.py                 # Tkinter-Start; Composition-Root
    config.py               # App-Konfiguration, Modell-Liste, API Keys
  ui/
    __init__.py
    board_view.py           # Rendering, gelbe Markierungen, Symbole
    controls.py             # Buttons, Dropdowns, Panels (Log/Kommentar)
    controller.py           # UI-Event-Handling, ruft Engine/AI
  engine/
    __init__.py
    types.py                # @dataclass Move, Piece, Color, CastlingRights
    board.py                # Board-Struct, Laden/Speichern/FEN
    rules.py                # Legalität, Angriffe, Simulation, Spezialzüge
    game.py                 # Spielzustand, Zughistorie, Endzustände
    fen.py                  # FEN-Export/Import (für LLM & Tests)
  ai/
    __init__.py
    provider.py             # Abstrakte Schnittstelle LLMProvider
    openai_client.py        # OpenAI-Adapter (Responses/Tools/JSON Schema)
    strategist.py           # 3-Phasen-Agentik orchestriert die Abfragen
    move_parser.py          # Robust: LLM-Ausgaben -> interner Move
  commentary/
    __init__.py
    commentator.py          # LLM-Kommentator-Adapter
    formatter.py            # Knappes, UI-taugliches Format
  telemetry/
    __init__.py
    logger.py               # Request/Response-Logs, Metriken, Latenzen
  tests/
    test_rules.py
    test_special_moves.py
    test_fen_roundtrip.py
    test_llm_contracts.py
```

**Begründung**

* Sauberes **Separation of Concerns**: Engine ist UI‑frei; UI kennt Engine, nicht umgekehrt.
* **Adapter‑Pattern** für LLM‑Provider verhindert Vendor‑Lock‑in.
* **FEN** als Standardrepräsentation nach aussen (LLM/Kommentator/Tests).

**Technische Leitplanken**

* **Type Hints** überall, `@dataclass` für `Move`.
* **Pure Engine**: keine Tkinter‑Abhängigkeiten in `engine/*`.
* **Deterministische Tests** (ohne API‑Zugriffe) für Regeln; API‑Tests als „contract tests“ mit Mock/Recorded Fixtures.
* **CI‑Checks**: `ruff`, `black`, `mypy`, `pytest -q`.

**Alternative Wege (mit Konsequenzen)**

* **Option A (Empfehlung):** Eigene Rule‑Engine fortführen (wie jetzt), FEN/PGN selbst ergänzen.

  * **Pro:** Vollständige Kontrolle, keine Zusatzabhängigkeit.
  * **Contra:** Höherer Pflegeaufwand (Edge Cases).
* **Option B:** **python‑chess** integrieren und UI darauf aufsetzen.

  * **Pro:** Vollständige, battle‑tested Regeln/Notation.
  * **Contra:** Umbau der Engine‑APIs; Abhängigkeit Dritter.

---

### 2) KI‑Gegner (OpenAI) inkl. agentischer 3‑Phasen‑Logik & Log‑Panel

**Zielbild in der UI**

* **Dropdown „KI‑Modell“** auf der rechten Seite (z. B. `gpt-4o-mini`).
* **Log‑Panel rechts**: zeigt pro Anfrage kompakte **Prompts** und **LLM‑Antworten** (gefiltert/strukturiert).
* **Modus‑Schalter**: „Mensch vs. KI“ oder „KI vs. KI“.

**Provider‑Abstraktion**

* Interface `LLMProvider.move_suggestion(fen: str, legal_moves: list[Move], history: list[str], phase: Literal[1,2,3]) -> AIDecision`.
* **OpenAI‑Adapter** implementiert obiges mit offizieller OpenAI‑SDK.

  * *Modelle*: `gpt-4o-mini` (Text+Vision, kosteneffizient), siehe Modellübersicht. ([platform.openai.com][1])
  * **Structured Outputs / JSON‑Schema** für robuste Antworten (empfohlen). ([platform.openai.com][2])
  * **Function Calling / Tools** als Alternative, falls JSON‑Schema nicht passt. ([platform.openai.com][3])
  * **Hinweis:** Preise/Verfügbarkeit ändern; prüfe aktuelle **Pricing‑Seite** vor Produktivsetzung. ([platform.openai.com][4])

**Agentischer 3‑Phasen‑Ablauf (konkret)**

* **Phase 1 – Kandidat finden:**
  Prompt enthält **FEN**, **Liste legaler Züge** (UCI/SAN), knappe Partie‑Historie.
  Ziel: **Top‑3 Kandidaten** als JSON (Zug + 1‑Satz‑Begründung).
* **Phase 2 – Gegenzug antizipieren:**
  Für jeden Kandidaten wird **eine Fiktivvariante** (1 Antwortzug Gegner) simuliert; Modell bewertet den erwarteten Outcome (Material, Königssicherheit, Taktikrisiken).
* **Phase 3 – Entscheidung:**
  Modell wählt finalen Zug aus den Kandidaten und liefert **genau einen** legalen Zug im **strikten JSON‑Format** (kein Fliesstext).
* **Wichtig:** Engine validiert **immer**: Zug muss in `legal_moves` enthalten sein. Ungültig → Retry mit Fehlermeldung im Log‑Panel.

**Strukturierte Ausgaben (Beispiel‑Schema)**

```json
{
  "type": "object",
  "properties": {
    "final_move": {"type": "string", "pattern": "^[a-h][1-8][a-h][1-8][qrbn]?$"},
    "short_summary": {"type": "string", "maxLength": 160}
  },
  "required": ["final_move"]
}
```

Mit OpenAI lässt sich das per **Structured Outputs**/`response_format` erzwingen; nutze das offizielle Schema‑Feature gemäss Dokumentation. ([platform.openai.com][2])

**Prompting‑Guidelines**

* Keine „Gedankenketten“ loggen; nur knappe **Stichwörter/Begründungen** speichern.
* Immer **FEN + legal_moves** liefern; dadurch minimierst du Halluzinationen.
* Setze klare **Abbruchkriterien** (Timeout, max. Tokens); handhabe Rate‑Limits robust (Retry‑Backoff).

**Beispiel‑Flow (Pseudo‑Code)**

```python
fen = fen_export(board)  # engine/fen.py
legal_moves = engine.rules.legal_moves(state)

log.phase(1, prompt_inputs={fen, legal_moves})
kandidaten = llm.phase1_candidates(fen, legal_moves)

log.phase(2, prompt_inputs=kandidaten)
bewertungen = llm.phase2_opp_responses(fen, kandidaten)

log.phase(3, prompt_inputs=bewertungen)
decision = llm.phase3_decide(fen, kandidaten, bewertungen, response_format=json_schema)

move = parse_and_validate(decision.final_move, legal_moves)
controller.apply_move(move)
log.info("LLM move executed", move=move)
```

**Rechte Seite (Log‑Panel)**

* Tabellarisch: **Phase**, **Dauer**, **Tokenkosten** (falls verfügbar), **kompakte** Prompt/Antwort‑Snippets.
* Export Funktion (TXT/JSON) für spätere Analysen.

---

### 3) Spielermodi: Mensch vs. KI und KI vs. KI

**Konzept**

* Einheitliche `Player`‑Schnittstelle: `HumanPlayer`, `AIPlayer(provider, model)`.
* **KI vs. KI**: Beide Seiten instanziieren `AIPlayer` mit eigener Konfiguration (gleiches 3‑Phasen‑Protokoll).
* **UI‑Sperre**: Während KI rechnet, Inputs auf dem Brett deaktivieren (Button „Stop/Abbrechen“ bereitstellen).
* **Determinismus/Sicherheit**: Jeder KI‑Zug wird engine‑seitig legal geprüft; misslingt Parsing → Retry oder Fallback (z. B. besten legalen Kandidaten aus Phase 1 nehmen).

**Zwei Umsetzungsvarianten**

* **Variante A (Threaded, empfohlen):** LLM‑Aufrufe in Hintergrund‑Thread; UI‑Thread bleibt responsiv.

  * **Pro:** Bessere UX.
  * **Contra:** Thread‑Synchronisation (Queue/Locks) nötig.
* **Variante B (Sync, blockierend):** UI blockiert während der Anfrage.

  * **Pro:** Einfach.
  * **Contra:** Schlechte UX, Risiko „keine Rückmeldung“.

---

### 4) Kommentator‑Funktion (linkes Panel)

**Ziel**

* Separates Modell liefert **kurze, verständliche Kommentare** pro Position/Zugfolge:

  * Erkennen von Eröffnungsvarianten, Druck/Besserstellung, Drohungen, Taktikmotive.
* **Input:** FEN + letzte N Züge; optional Bewertungen (Materialbilanz, Königssicherheit) aus Engine.
* **Output (strukturiert):**

  ```json
  {
    "variant_hint": "Sizilianisch (Najdorf) ...",
    "eval_trend": "leicht besser für Weiss",
    "key_ideas": ["Druck auf d6", "Hebel b5 in Vorbereitung"],
    "blunders_last_moves": []
  }
  ```
* **UI:** Linker Rand, scrollbarer Feed. **Kompakt**; keine langen Erklärmonologe.

---

### 5) Anbieterabstraktion: Start OpenAI, später Google & Anthropic

**Warum jetzt OpenAI?** Gute Abdeckung und offizielle Features wie **Structured Outputs** und **Function Calling** (stabil dokumentiert). Später können **Google (Gemini)** und **Anthropic (Claude)** via denselben `LLMProvider` integriert werden.

* **Modelle (OpenAI, Beispiel):** `gpt-4o-mini` – schnelles, günstiges Modell für Zugempfehlungen; offizielle Modellseite beschreibt Fähigkeiten und Einsatz. Verfügbarkeit/Preise bitte vor Einsatz prüfen. ([platform.openai.com][1])
* **Structured Outputs:** Offizieller Leitfaden zum Erzwingen validen JSONs (empfohlen). ([platform.openai.com][2])
* **Function Calling:** Offizieller Leitfaden für Tool‑Aufrufe/validierte Parameter. ([platform.openai.com][3])

> **Hinweis zu Namenswirrwarr**: OpenAI hat Modelle und Benennungen mehrfach verändert; richte dich **immer** nach den aktuellen **Modelldokumenten** und Pricing‑Seiten. Hardcode keine veralteten Modellnamen. ([platform.openai.com][5])

---

## Querschnittsthemen

**Robuste Validierung**

* LLM‑Antworten **nie** blind ausführen. Immer:

  1. **Schema‑Validierung** (JSON‑Schema/Tools).
  2. **Move‑Validierung** gegen Engine‑Legalität.
  3. **Fallbacks** (Retry, Top‑Kandidat aus Phase 1).

**Konfiguration**

* `.env` / `config.py` mit `OPENAI_API_KEY`, Default‑Modell, Token‑Budgets, Timeouts.

**Telemetrie**

* Logge Metriken (Latenz, Token, Fehlversuche).
* Exportiere Logs (JSON/CSV) für spätere Auswertung.

**Tests (empfohlen)**

* **Regeltests**: En Passant (nur im Folgehalbzug), Rochaderechte (Verlust bei Turmzug/Schlag), König nie schlagbar, Matt/Patt.
* **FEN‑Roundtrip**: `fen_export` ➜ `fen_import` ➜ Gleichheit.
* **Contract‑Tests KI**: Golden‑Files für Beispielprompts, Schema‑Parsing, Illegal‑Move‑Fehlerpfad.

---

## Konkreter Umsetzungsplan (Meilensteine)

**M0 – Codequalität & Stabilisierung**

* Type Hints, `ruff`, `black`, `pytest`.
* Engine extrahieren: `engine/{board.py,rules.py,game.py,fen.py,types.py}`.
* FEN‑Export/Import + PGN‑Dump (einfach).

**M1 – UI‑Reorganisation**

* `ui/{board_view.py,controls.py,controller.py}`.
* Rechts: **Log‑Panel**, Modell‑Dropdown.
* Links: **Kommentator‑Panel** (Platzhalter).

**M2 – OpenAI‑Adapter (KI‑Züge)**

* `ai/provider.py`, `ai/openai_client.py`, `ai/move_parser.py`, `ai/strategist.py`.
* 3‑Phasen‑Flow, JSON‑Schema/Function‑Calling, Validierung + Retries.
* KI vs. Mensch lauffähig.

**M3 – KI vs. KI + Kommentator**

* Zwei `AIPlayer` Instanzen mit getrennten Einstellungen.
* Kommentator an Trigger **nach jedem Zug**, Ausgabe links.

**M4 – Erweiterungen**

* Konfigurationsdialog, Logging‑Export, Undo/Redo, einstellbare Think‑Time.
* Optionale Integration von weiteren Anbietern (Google/Anthropic) via `LLMProvider`.

---

## Anhang: Unterschiede zur ursprünglichen `chess.py`

* **König nie schlagbar**, Legalität filtert solche Züge konsequent.
* **En Passant** korrekt **nur** im direkt folgenden Halbzug gültig (Target + Ablauf).
* **Rochaderechte** pro Seite (K/L), saubere Aktualisierung bei König/Turmzug und beim **Schlagen** eines Startturms.
* **Schach/Matt/Patt**: Königslage wird **aus dem Board** bestimmt (kein Cache), Simulationen sind regelkonform.
* **Game‑Over** blockiert weitere Züge.
* **Gelbe Markierung & Rochadeanzeige** unverändert.

> Ausgangspunkt der Überarbeitung war der einteilige Code in `chess.py`, der u. a. Königslage gecached und En Passant unpräzise gehandhabt hat. Diese Probleme sind jetzt beseitigt. 

---

## Referenzen (Auswahl)

* **OpenAI Structured Outputs (JSON‑Schema/`response_format`)** – offizielle Doku. ([platform.openai.com][2])
* **OpenAI Function Calling / Tools** – offizielle Doku. ([platform.openai.com][3])
* **OpenAI Modelle – GPT‑4o‑mini & GPT‑4o** – Modellseiten. ([platform.openai.com][1])
* **OpenAI Pricing** – Preisdokumentation (Änderungen möglich). ([platform.openai.com][4])

---

### Nächste Schritte (klare To‑Dos)

1. **Engine extrahieren** in `engine/*`, FEN implementieren, Tests aufsetzen.
2. **UI splitten**, Panels (rechts/links) hinzufügen, Controller zentralisieren.
3. **OpenAI‑Adapter** implementieren (JSON‑Schema oder Tools), Modell‑Dropdown anbinden.
4. **Agentik‑Flow (3 Phasen)** integrieren, Logging‑Panel rechts.
5. **Spielermodi** schalten (Mensch/KI/KI vs. KI), sauberes Threading.
6. **Kommentator** hinzufügen (links), strukturierte Kurzkommentare statt Fliesstext.
7. **CI/CD**: Lint, Typprüfung, Tests; optional Paketsupport (`pyproject.toml`).

Damit hat jeder neue Entwickler sofort einen **klaren Einstieg**, eine **präzise Roadmap** und robuste Leitplanken für die Umsetzung deiner Vision.

[1]: https://platform.openai.com/docs/models/gpt-4o-mini?utm_source=chatgpt.com "Model - OpenAI API"
[2]: https://platform.openai.com/docs/guides/structured-outputs?utm_source=chatgpt.com "OpenAI's structured outputs documentation"
[3]: https://platform.openai.com/docs/guides/function-calling?utm_source=chatgpt.com "OpenAI Function Calling Guide"
[4]: https://platform.openai.com/docs/pricing?utm_source=chatgpt.com "Pricing - OpenAI API"
[5]: https://platform.openai.com/docs/models?utm_source=chatgpt.com "Models - OpenAI API"
