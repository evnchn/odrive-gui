"""Shared visual theme, applied by both the real app and the mock dev runner."""

from __future__ import annotations

from nicegui import ui

PRIMARY = '#6e93d6'

# ``ui.dark_mode`` value -> (icon, label). ``None`` follows the OS setting.
_THEME_MODES: dict[bool | None, tuple[str, str]] = {
    None: ('brightness_auto', 'Auto'),
    False: ('light_mode', 'Light'),
    True: ('dark_mode', 'Dark'),
}
# Clicking the theme button cycles Auto -> Light -> Dark -> Auto.
_NEXT_THEME_MODE: dict[bool | None, bool | None] = {None: False, False: True, True: None}


def apply_theme(dark: bool | None = None) -> ui.dark_mode:
    """Apply the ODrive GUI colour scheme and return the dark-mode handle.

    ``dark=None`` (default) follows the operating system's light/dark setting; pass
    ``True``/``False`` to force it. The returned ``ui.dark_mode`` can be bound to a
    toggle (see :func:`header`) so the user can override it at runtime.
    """
    ui.colors(primary=PRIMARY)
    return ui.dark_mode(dark)


def header(dark: ui.dark_mode) -> None:
    """The page's top app bar: the title plus a single-icon theme toggle.

    The icon shows the *current* mode (Auto/Light/Dark) and a click cycles to the next
    one, like the theme button on nicegui.io. Kept compact and shared by the app and
    the mock runner so both show identical chrome and neither wastes vertical space on
    a large standalone title.
    """
    with ui.header().props('elevated').classes('items-center justify-between px-4 py-2'):
        ui.label('ODrive GUI').classes('text-lg font-medium')
        button = (
            ui.button(color=None, on_click=lambda: dark.set_value(_NEXT_THEME_MODE[dark.value]))
            .props('flat round dense text-color=white')
            .bind_icon_from(dark, 'value', backward=lambda mode: _THEME_MODES[mode][0])
        )
        with button:
            ui.tooltip().bind_text_from(
                dark,
                'value',
                backward=lambda mode: f'Theme: {_THEME_MODES[mode][1]} — click for {_THEME_MODES[_NEXT_THEME_MODE[mode]][1]}',
            )
