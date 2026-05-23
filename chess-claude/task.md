## Developer Brief: GUI Theming + Rich Markup Rendering + Animated Auto-Moves (PySide6)

### Scope and hard constraints

* **Do not change the chessboard design itself** (marble texture, square look, current board art stays as-is).
* Only adjust **GUI chrome** (panels, buttons, inputs, text windows) + **how AI text is rendered** + **how pieces move (animation + auto-apply for AI moves)**.
* The visual target is **exactly** the dark/clean GUI shown in the screenshots and as defined in the existing theme config (`APP_STYLE_SHEET`, base font settings, widget selectors). 

---

## 1) Theme and GUI styling must match the reference (screenshots + theme.py)

### Goal

Ensure the entire GUI consistently uses the centralized theme configuration and that **every widget actually picks up the intended QSS selectors**.

### Requirements

1. **Single source of truth for styling**

   * Use the existing theme module as the only place that defines:

     * `BASE_FONT_FAMILY`, `BASE_FONT_SIZE`
     * `APP_STYLE_SHEET`
   * Apply it once during app startup:

     * `QApplication.setStyle("Fusion")`
     * set app font from the constants
     * `app.setStyleSheet(APP_STYLE_SHEET)`
       (This must remain stable and not be duplicated elsewhere.) 

2. **QSS selectors must actually match runtime widgets**

   * Wherever the theme uses **object selectors** like `#TopBar`, `#Card`, `#CardTitle`, `#StatusLabel`, `#TurnBadge`, ensure:

     * the corresponding widgets have `setObjectName("TopBar")`, etc.
   * Wherever the theme uses **property selectors** like `QPushButton[variant="ghost"]`, ensure:

     * those buttons set `setProperty("variant", "ghost")` and call `style().unpolish()/polish()` if needed after setting properties.

3. **Extend theme coverage to all text widgets in use**

   * The theme currently styles `QTextEdit` but AI windows should likely use `QTextBrowser` and/or `QPlainTextEdit`.
   * Update the theme stylesheet to include:

     * `QTextBrowser` (read-only rich output windows)
     * `QPlainTextEdit` (if used for input)
   * Keep the same background/border palette as the rest of the UI.

4. **Buttons must be readable in all states**

   * If you use “ghost / transparent” buttons, ensure their text remains readable on dark/gradient backgrounds:

     * explicit `color:` for normal/hover/pressed/disabled
     * hover/pressed states must add enough background/border contrast
   * No state should ever drop below readable contrast.

### Acceptance criteria

* The whole GUI (top bar, cards, tabs, inputs, logs) visually matches the screenshots.
* No widget appears with default Qt grey styling.
* Ghost buttons and labels remain readable in normal/hover/pressed/disabled states.

---

## 2) AI output windows must render markup correctly (Markdown → rich text)

### Problem

AI output (especially commentator) contains Markdown-like formatting (`**bold**`, headings, lists, etc.). It is currently displayed as plain text, which makes it hard to read and wastes the model’s structured output.

### Goal

All text windows that show **AI output** (commentator transcript, White AI chat, Black AI chat; and any other pane showing raw AI responses) must render markup properly and be theme-colored for readability.

### Requirements

1. **Use a rich-output widget**

   * Replace plain text output widgets with `QTextBrowser` (recommended) or `QTextEdit` in read-only mode.
   * Ensure:

     * smooth scrolling
     * selectable text
     * copy/paste works

2. **Markdown rendering pipeline**

   * Treat incoming AI text as **Markdown** by default.
   * Convert Markdown → a `QTextDocumentFragment` and append it to the transcript.
   * **Sanitise raw HTML** from AI output (escape `<` and `>`) before Markdown parsing to avoid unpredictable rendering.

3. **Theme-aware typography + colors**
   Apply consistent formatting rules (use the theme palette already defined):

   * Headings (`h1/h2/h3`): **accent cyan** (same as CardTitle)
   * Strong/bold: high-contrast near-white
   * Emphasis/italic: muted text
   * Inline code: neon-lime text on a slightly darker background
   * Code blocks: dark panel background + border
   * Lists: proper indentation and line spacing
   * Links: cyan, optionally underlined on hover

4. **Role-aware message styling (critical for readability)**
   Every transcript entry must clearly show who produced it:

   * **System/game prompt**: muted, smaller, optionally prefixed `[System]`
   * **User message**: cyan label
   * **AI response**: normal text, headings styled
   * **Errors**: red/pink accent (consistent with the rest of the GUI)

5. **Special formatting: MOVE lines**
   If AI outputs a move line like:

   * `MOVE: e2e4`
     Render it as a visually distinct line:
   * monospace
   * neon-lime text (matches your “beam” motif)
   * subtle background pill or border

6. **Scrolling behaviour**

   * Autoscroll only if the user is already near the bottom.
   * If the user scrolls up, do not force-scroll them down when new messages arrive.

### Acceptance criteria

* The commentator output example in the screenshot renders cleanly (bold headings, bullet lists, structure).
* AI responses are readable and visually structured.
* MOVE lines are clearly highlighted.
* No raw `**` markup remains visible unless the AI output is truly malformed.

---

## 3) AI move responses must auto-apply (not only highlight)

### Goal

When an AI returns a valid move:

* The move is not only highlighted.
* The **piece is moved automatically**.

### Requirements

1. **Auto-apply AI moves**

   * On a valid AI move response:

     * validate legality
     * apply the move to the engine state
     * trigger the move animation (see next section)
     * update move list/log
     * dispatch commentator update (after the move is applied)

2. **No UI blocking**

   * AI calls remain off the UI thread.
   * Apply move and animation on UI thread via signals/slots.

3. **Sequential safety (especially AI vs AI)**

   * Prevent overlapping AI requests and overlapping animations.
   * For AI vs AI:

     * request next AI move only after the current move animation completes.
   * During animation:

     * temporarily disable board input (or ignore clicks) to avoid state corruption.

### Acceptance criteria

* As soon as AI returns `MOVE: ...`, the board updates and the piece starts moving automatically.
* AI vs AI progresses smoothly without race conditions.

---

## 4) Piece movement animation (250ms straight-line)

### Goal

Any move that changes a piece position should be animated:

* straight-line movement
* duration ~**250ms**
* visually smooth

### Requirements

1. **Animation spec**

   * Duration: 250ms (±50ms acceptable)
   * Easing: linear (clean, “tool-like”)
   * Path: straight line from source square center to destination square center

2. **Implementation outline**

   * Use `QVariantAnimation` or `QPropertyAnimation` driving a `progress` value (0.0 → 1.0).
   * During animation:

     * repaint board at frame updates
     * draw the moving piece at interpolated pixel position
     * do not show a duplicate static piece at both source and destination

3. **Special moves must not break**
   Ensure correct behaviour for:

   * **Castling**: animate king and rook (in parallel) or king first then rook; must look intentional
   * **Promotion**: animate pawn to final square; swap to promoted piece at end
   * **En passant**: captured pawn removed correctly; animation still runs normally

4. **Event ordering**

   * Apply engine state in a deterministic way that does not desync the UI.
   * Recommendation:

     * lock input
     * apply engine move (so legality/state is correct)
     * play animation visually
     * unlock input
     * then trigger any “next-step” actions (commentator prompt, next AI prompt)

### Acceptance criteria

* Human moves and AI moves both animate.
* No flicker, no ghost pieces, no double rendering.
* Castling and promotion do not visually glitch.

---

## 5) Done criteria (test checklist)

* GUI theme is consistent everywhere (top bar/cards/tabs/inputs/buttons) and matches the reference theme. 
* All AI-visible output windows render Markdown correctly and are color-formatted for readability.
* AI moves are auto-applied and animated (~250ms).
* No changes were made to the board’s **visual design** (marble/squares look stays unchanged).
* AI vs AI does not pile up requests; move+animation is sequential and stable.
