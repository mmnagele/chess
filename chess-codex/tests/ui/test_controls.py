"""Tests for :class:`ui.controls.ChessControls`."""

from __future__ import annotations

from ui.controls import CUSTOM_MODEL_OPTION, ChessControls


def test_create_board_view_returns_instance(qapp) -> None:
    controls = ChessControls()
    board = controls.create_board_view()
    assert board.parent() is controls.board_container


def test_player_type_conversion(qapp) -> None:
    controls = ChessControls()
    assert controls.get_player_type("white") == "human"
    controls.set_player_type("white", "ai")
    assert controls.get_player_type("white") == "ai"


def test_provider_metadata_and_models(qapp) -> None:
    controls = ChessControls()
    controls.set_provider_metadata(
        provider_items=[("OpenAI", "openai"), ("Anthropic", "anthropic")],
        model_presets={"openai": ("gpt-4o-mini",), "anthropic": ("claude",)},
        availability={"openai": True, "anthropic": False},
    )

    white_provider = controls._player_provider_selectors[
        "white"
    ]  # pylint: disable=protected-access
    values = [white_provider.itemText(i) for i in range(white_provider.count())]
    assert values == ["OpenAI", "Anthropic (missing key)"]

    controls.set_player_type("white", "ai")
    assert white_provider.isEnabled() is True

    model_combo = controls._player_model_selectors["white"]  # pylint: disable=protected-access
    model_values = [model_combo.itemText(i) for i in range(model_combo.count())]
    assert model_values == ["gpt-4o-mini", CUSTOM_MODEL_OPTION]


def test_commentator_fields(qapp) -> None:
    controls = ChessControls()
    controls.set_provider_metadata(
        provider_items=[("OpenAI", "openai")],
        model_presets={"openai": ("gpt-4o-mini",)},
        availability={"openai": True},
    )

    controls._commentator_toggle.setCurrentText("On")  # pylint: disable=protected-access
    controls._commentator_type.setCurrentText("Adult Coach")  # pylint: disable=protected-access

    assert controls.get_commentator_enabled() is True
    assert controls.get_commentator_type() == "Adult Coach"
    assert controls.get_commentator_provider() == "openai"


def test_chat_send_callbacks(qapp) -> None:
    controls = ChessControls()
    calls: list[tuple[str, str]] = []
    controls.set_chat_send_callback(lambda chat_id, message: calls.append((chat_id, message)))

    controls.commentary_chat._entry.setText("hello")  # pylint: disable=protected-access
    controls.commentary_chat._send_btn.click()  # pylint: disable=protected-access

    controls.white_chat._entry.setText("w")  # pylint: disable=protected-access
    controls.white_chat._send_btn.click()  # pylint: disable=protected-access

    controls.black_chat._entry.setText("b")  # pylint: disable=protected-access
    controls.black_chat._send_btn.click()  # pylint: disable=protected-access

    assert calls == [("commentator", "hello"), ("white", "w"), ("black", "b")]


def test_reload_keys_callback(qapp) -> None:
    controls = ChessControls()
    calls: list[str] = []
    controls.set_reload_keys_callback(lambda: calls.append("reload"))

    controls.reload_keys_button.click()
    assert calls == ["reload"]


def test_key_diagnostics_callback_and_dialog(qapp) -> None:
    controls = ChessControls()
    calls: list[str] = []
    controls.set_key_diagnostics_callback(lambda: calls.append("diag"))

    controls.key_diagnostics_button.click()
    assert calls == ["diag"]

    controls.show_key_diagnostics("line-1\nline-2")
    dialog = controls._key_diagnostics_dialog  # pylint: disable=protected-access
    assert dialog is not None
    assert "line-2" in dialog._text.toPlainText()  # pylint: disable=protected-access


def test_custom_model_entry_roundtrip(qapp) -> None:
    controls = ChessControls()
    controls.set_provider_metadata(
        provider_items=[("OpenAI", "openai")],
        model_presets={"openai": ("gpt-4o-mini",)},
        availability={"openai": True},
    )
    controls.set_player_type("white", "ai")
    combo = controls._player_model_selectors["white"]  # pylint: disable=protected-access
    combo.setCurrentText(CUSTOM_MODEL_OPTION)
    combo.setEditText("custom-model")

    assert controls.get_player_model("white") == "custom-model"


def test_chat_entry_renders_markdown_and_move_lines(qapp) -> None:
    controls = ChessControls()

    controls.append_chat_entry(
        "white",
        "# Title\n\nMOVE: e2e4\n\n- one\n- two",
        role="ai",
        source="[AI]",
    )

    transcript = controls.white_chat._text.toPlainText()  # pylint: disable=protected-access
    html = controls.white_chat._text.toHtml()  # pylint: disable=protected-access
    assert "Title" in transcript
    assert "MOVE: e2e4" in transcript
    assert "JetBrains Mono" in html
    assert "#a3e635" in html


def test_turn_badge_uses_theme_property_state(qapp) -> None:
    controls = ChessControls()
    controls.set_current_player("black")
    assert controls.player_indicator.property("side") == "black"
    assert controls.player_indicator.styleSheet() == ""
