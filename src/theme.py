"""Shared visual theme, applied by both the real app and the mock dev runner."""

from __future__ import annotations

from nicegui import ui

PRIMARY = '#6e93d6'

# The theme toggle's options -> the value bound onto ``ui.dark_mode`` (None = follow the OS).
_THEME_OPTIONS = {None: 'Auto', False: 'Light', True: 'Dark'}


def apply_theme(dark: bool | None = None) -> ui.dark_mode:
    """Apply the ODrive GUI colour scheme and return the dark-mode handle.

    ``dark=None`` (default) follows the operating system's light/dark setting; pass
    ``True``/``False`` to force it. The returned ``ui.dark_mode`` can be bound to a
    toggle (see :func:`header`) so the user can override it at runtime.
    """
    ui.colors(primary=PRIMARY)
    return ui.dark_mode(dark)


def header(dark: ui.dark_mode) -> None:
    """The page's top app bar: the title plus a Light/Dark/Auto theme toggle.

    Kept compact and shared by the app and the mock runner so both show identical chrome
    and neither wastes vertical space on a large standalone title.
    """
    with ui.header().props('elevated').classes('items-center justify-between px-4 py-2'):
        ui.label('ODrive GUI').classes('text-lg font-medium')
        # ``toggle-color=white`` keeps the *selected* option readable: the default fills it with
        # ``primary``, which is invisible on the primary-coloured header.
        ui.toggle(_THEME_OPTIONS).props('unelevated toggle-color=white toggle-text-color=primary').bind_value(dark, 'value')
