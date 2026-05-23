# UI Sanity Checklist

Use this checklist before release to verify the PySide6 neon chess UI behavior.

## 1) Button Readability

1. Open the app and inspect at least these buttons: `New Game`, `Reset`, `Reload Keys`, `Send`, `Clear`, and one disabled control.
2. Verify text remains readable in all states: normal, hover, pressed, checked, disabled.
3. Verify ghost/transparent-style buttons still show enough contrast over dark and textured backgrounds.

## 2) Coordinate Scaling (Including 4K)

1. Resize the window to a very small size and confirm rank/file labels are visible and not clipped.
2. Use normal desktop size and verify alignment to board edges.
3. Run fullscreen on a 4K display and verify no coordinate clipping on top/bottom/left/right.

## 3) Provider Key Detection

1. Set environment variables before launch:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GEMINI_API_KEY`
2. Start app and click `Reload Keys`.
3. Verify provider dropdown entries no longer show `(missing key)` when corresponding keys are present.
4. Open `Key Diagnostics` and verify process hints + troubleshooting guidance are visible.
5. Verify move/event log contains safe diagnostics (`present` and key `length`) and never prints full keys.

## 4) Move/Capture Visuals

1. Select a piece and verify legal non-capture targets show strong neon yellow-green dots.
2. Verify capture targets show blue rings.
3. Play a move and verify from/to squares are highlighted in red until next move.
4. Execute a capture and verify the ring animation plays once: inflate then implode.

## 5) Piece Proportions

1. Confirm SVG piece alignment is centered on all squares.
2. Confirm king crown is visibly larger than before.
3. Confirm knight neck appears slightly longer.
4. Confirm pawn torso appears slimmer without distortion.
