"""Markdown-to-HTML renderer for AI output windows.

Converts Markdown text to themed HTML suitable for QTextBrowser display.
Sanitises raw HTML from AI output before parsing.
"""

from __future__ import annotations

import html
import re

from ui_qt.theme.palette import (
    BG_CARD,
    BORDER_DEFAULT,
    NEON_CYAN,
    NEON_LIME,
    NEON_PINK,
    TEXT_DIM,
    TEXT_MUTED,
    TEXT_PRIMARY,
)

# Pre-compiled patterns
_MOVE_LINE = re.compile(r"^(MOVE:\s*.+)$", re.MULTILINE)
_HEADING3 = re.compile(r"^###\s+(.+)$", re.MULTILINE)
_HEADING2 = re.compile(r"^##\s+(.+)$", re.MULTILINE)
_HEADING1 = re.compile(r"^#\s+(.+)$", re.MULTILINE)
_BOLD = re.compile(r"\*\*(.+?)\*\*")
_ITALIC = re.compile(r"\*(.+?)\*")
_CODE_BLOCK = re.compile(r"```(?:\w*)\n(.*?)```", re.DOTALL)
_INLINE_CODE = re.compile(r"`([^`]+)`")
_UNORDERED_LIST = re.compile(r"^[\-\*]\s+(.+)$", re.MULTILINE)
_ORDERED_LIST = re.compile(r"^\d+\.\s+(.+)$", re.MULTILINE)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_HORIZONTAL_RULE = re.compile(r"^---+$", re.MULTILINE)


def _sanitise(text: str) -> str:
    """Escape raw HTML tags from AI output to prevent injection."""
    return html.escape(text, quote=False)


def markdown_to_html(text: str) -> str:
    """Convert Markdown text to themed HTML for QTextBrowser.

    Sanitises HTML first, then applies Markdown transformations.
    """
    # Sanitise raw HTML from AI
    text = _sanitise(text)

    # Code blocks (before other transforms to avoid nested processing)
    def _code_block_repl(m: re.Match) -> str:
        code = m.group(1).strip()
        return (
            f'<div style="background-color: {BG_CARD}; border: 1px solid {BORDER_DEFAULT}; '
            f'border-radius: 4px; padding: 8px; margin: 4px 0;">'
            f'<pre style="color: {NEON_LIME}; margin: 0; white-space: pre-wrap;">{code}</pre></div>'
        )

    text = _CODE_BLOCK.sub(_code_block_repl, text)

    # Inline code
    text = _INLINE_CODE.sub(
        rf'<code style="color: {NEON_LIME}; background-color: {BG_CARD}; '
        rf'padding: 1px 4px; border-radius: 3px;">\1</code>',
        text,
    )

    # MOVE lines (special highlight)
    text = _MOVE_LINE.sub(
        rf'<div style="font-family: monospace; color: {NEON_LIME}; '
        rf"background-color: {BG_CARD}; border: 1px solid {BORDER_DEFAULT}; "
        rf'border-radius: 4px; padding: 4px 8px; margin: 4px 0; font-weight: bold;">'
        r"\1</div>",
        text,
    )

    # Headings (process h3 before h2 before h1)
    text = _HEADING3.sub(
        rf'<h3 style="color: {NEON_CYAN}; font-size: 14px; margin: 8px 0 4px 0;">\1</h3>',
        text,
    )
    text = _HEADING2.sub(
        rf'<h2 style="color: {NEON_CYAN}; font-size: 15px; margin: 8px 0 4px 0;">\1</h2>',
        text,
    )
    text = _HEADING1.sub(
        rf'<h1 style="color: {NEON_CYAN}; font-size: 16px; margin: 8px 0 4px 0;">\1</h1>',
        text,
    )

    # Bold/italic (bold first to avoid conflict)
    text = _BOLD.sub(rf'<b style="color: {TEXT_PRIMARY};">\1</b>', text)
    text = _ITALIC.sub(rf'<i style="color: {TEXT_MUTED};">\1</i>', text)

    # Links
    text = _LINK.sub(rf'<a style="color: {NEON_CYAN};" href="\2">\1</a>', text)

    # Horizontal rules
    text = _HORIZONTAL_RULE.sub(
        f'<hr style="border: 1px solid {BORDER_DEFAULT}; margin: 8px 0;">',
        text,
    )

    # Lists: unordered
    text = _UNORDERED_LIST.sub(
        r'<div style="padding-left: 16px; margin: 2px 0;">&bull; \1</div>',
        text,
    )

    # Lists: ordered
    text = _ORDERED_LIST.sub(
        r'<div style="padding-left: 16px; margin: 2px 0;">\g<0></div>',
        text,
    )

    # Convert remaining newlines to <br> for proper line breaks
    text = text.replace("\n", "<br>")

    return text


def format_role_message(role: str, text: str) -> str:
    """Format a message with role-based styling.

    Roles: "system", "user", "ai", "error", "move"
    """
    if role == "system":
        escaped = _sanitise(text)
        return (
            f'<div style="color: {TEXT_DIM}; font-size: 12px; margin: 4px 0;">'
            f"[System] {escaped}</div>"
        )

    if role == "user":
        escaped = _sanitise(text)
        return (
            f'<div style="margin: 6px 0;">'
            f'<span style="color: {NEON_CYAN}; font-weight: bold;">You:</span> '
            f'<span style="color: {TEXT_PRIMARY};">{escaped}</span></div>'
        )

    if role == "ai":
        rendered = markdown_to_html(text)
        return f'<div style="margin: 6px 0;">{rendered}</div>'

    if role == "error":
        escaped = _sanitise(text)
        return f'<div style="color: {NEON_PINK}; margin: 4px 0;">' f"{escaped}</div>"

    if role == "move":
        escaped = _sanitise(text)
        return (
            f'<div style="font-family: monospace; color: {NEON_LIME}; '
            f"background-color: {BG_CARD}; border: 1px solid {BORDER_DEFAULT}; "
            f'border-radius: 4px; padding: 4px 8px; margin: 4px 0; font-weight: bold;">'
            f"{escaped}</div>"
        )

    # Default: render as markdown
    return f'<div style="margin: 4px 0;">{markdown_to_html(text)}</div>'


__all__ = ["format_role_message", "markdown_to_html"]
