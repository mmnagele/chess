"""Tests for :mod:`ui_qt.widgets.markdown_renderer`."""

from __future__ import annotations

from ui_qt.widgets.markdown_renderer import format_role_message, markdown_to_html


class TestMarkdownToHtml:
    """Test the Markdown-to-HTML conversion pipeline."""

    def test_bold_text(self) -> None:
        result = markdown_to_html("**bold text**")
        assert "<b" in result
        assert "bold text" in result
        assert "**" not in result

    def test_italic_text(self) -> None:
        result = markdown_to_html("*italic text*")
        assert "<i" in result
        assert "italic text" in result

    def test_heading1(self) -> None:
        result = markdown_to_html("# Heading One")
        assert "<h1" in result
        assert "Heading One" in result
        # Raw markdown prefix should not appear in output text
        assert "# Heading One" not in result

    def test_heading2(self) -> None:
        result = markdown_to_html("## Heading Two")
        assert "<h2" in result
        assert "Heading Two" in result

    def test_heading3(self) -> None:
        result = markdown_to_html("### Heading Three")
        assert "<h3" in result
        assert "Heading Three" in result

    def test_inline_code(self) -> None:
        result = markdown_to_html("Use `print()` here")
        assert "<code" in result
        assert "print()" in result

    def test_code_block(self) -> None:
        result = markdown_to_html("```python\nprint('hello')\n```")
        assert "<pre" in result
        assert "print(&#x27;hello&#x27;)" in result or "print('hello')" in result

    def test_move_line(self) -> None:
        result = markdown_to_html("MOVE: e2e4")
        assert "MOVE: e2e4" in result
        assert "font-family: monospace" in result

    def test_unordered_list(self) -> None:
        result = markdown_to_html("- Item one\n- Item two")
        assert "&bull;" in result
        assert "Item one" in result
        assert "Item two" in result

    def test_link(self) -> None:
        result = markdown_to_html("[click here](https://example.com)")
        assert "click here" in result
        assert "href" in result

    def test_sanitises_html(self) -> None:
        result = markdown_to_html("<script>alert('xss')</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_newlines_become_br(self) -> None:
        result = markdown_to_html("line1\nline2")
        assert "<br>" in result

    def test_horizontal_rule(self) -> None:
        result = markdown_to_html("---")
        assert "<hr" in result


class TestFormatRoleMessage:
    """Test role-based message formatting."""

    def test_system_role(self) -> None:
        result = format_role_message("system", "Game started")
        assert "[System]" in result
        assert "Game started" in result

    def test_user_role(self) -> None:
        result = format_role_message("user", "What move?")
        assert "You:" in result
        assert "What move?" in result

    def test_ai_role_renders_markdown(self) -> None:
        result = format_role_message("ai", "**Bold** move")
        assert "<b" in result
        assert "Bold" in result
        assert "**" not in result

    def test_error_role(self) -> None:
        result = format_role_message("error", "Something failed")
        assert "Something failed" in result
        # Should use pink/red color
        assert "FB7185" in result or "fb7185" in result.lower()

    def test_move_role(self) -> None:
        result = format_role_message("move", "MOVE: e2e4")
        assert "MOVE: e2e4" in result
        assert "monospace" in result

    def test_sanitises_user_input(self) -> None:
        result = format_role_message("user", "<script>bad</script>")
        assert "<script>" not in result
        assert "&lt;script&gt;" in result
