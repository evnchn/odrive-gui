"""Shared visual theme, applied by both the real app and the mock dev runner."""

from __future__ import annotations

from nicegui import ui

PRIMARY = '#6e93d6'


def apply_theme(dark: bool = True) -> None:
    """Apply the ODrive GUI colour scheme and dark mode."""
    ui.dark_mode(dark)
    ui.colors(primary=PRIMARY)
