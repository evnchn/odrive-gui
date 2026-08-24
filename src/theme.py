"""Shared visual theme, applied by both the real app and the mock dev runner."""

from __future__ import annotations

from nicegui import ui

PRIMARY = '#6e93d6'

# A flatter, less "Material" look: no drop shadows anywhere. The header stays in the
# primary colour but flat; each device's info strip docks right underneath it as a
# compact secondary bar; cards sit as plain surfaces on a slightly tinted page
# background (plus a hairline border); toggles are segmented controls (a pill sliding
# in a soft grey track). Where Quasar has a prop for it (`flat`, `bordered`,
# `unelevated`, `no-caps`, …) that prop is used — see the default props in
# apply_theme() and the card in controls.py — and this stylesheet only adds what
# props cannot express: colours, radii, spacing. Colours are translucent slate so
# the same rules work in both light and dark mode.
_CSS = """
:root {
    --gui-page: #f3f4f6;
    --gui-surface: #ffffff;
    --gui-track: rgba(100, 116, 139, 0.14);
    --gui-strip: rgba(110, 147, 214, 0.12);
    --gui-border: rgba(0, 0, 0, 0.08);
    --gui-field-border: rgba(0, 0, 0, 0.22);
    --gui-tooltip-bg: #1f2937;
    --gui-tooltip-fg: #f9fafb;
}
body.body--dark {
    --gui-page: #101114;
    --gui-surface: #1c1e22;
    --gui-track: rgba(148, 163, 184, 0.16);
    --gui-strip: rgba(110, 147, 214, 0.14);
    --gui-border: rgba(255, 255, 255, 0.08);
    --gui-field-border: rgba(255, 255, 255, 0.28);
    --gui-tooltip-bg: #f1f5f9;
    --gui-tooltip-fg: #111827;
}
body, body.body--dark {
    background: var(--gui-page);
}

/* the page content has no outer padding so the device strip can dock to the header;
   the sections that want breathing room (the axis cards) bring their own padding */
.nicegui-content {
    padding: 0;
    gap: 0;
}

/* per-device info strip (identity chips, bus voltage, global actions): a compact
   secondary bar tinted with the primary colour, docked under the header */
.gui-strip {
    background: var(--gui-strip);
    border-bottom: 1px solid var(--gui-border);
    padding: 4px 16px;
}

/* tooltips: rounded, readable, inverted relative to the current mode */
.q-tooltip {
    background: var(--gui-tooltip-bg);
    color: var(--gui-tooltip-fg);
    border-radius: 8px;
    padding: 6px 10px;
    font-size: 12px;
}

/* cards (`flat bordered`): soft radius, hairline border, plain surface */
.q-card, .q-card--dark {
    border-radius: 12px;
    border-color: var(--gui-border);
    background: var(--gui-surface);
}

/* toggles (`unelevated no-caps`): segmented control — a pill in a soft track */
.q-btn-toggle {
    background: var(--gui-track);
    border-radius: 10px;
    padding: 3px;
    gap: 2px;
}
.q-btn-toggle .q-btn {
    border-radius: 8px !important;
    min-height: 2em;
    padding: 0 12px;
    font-weight: 500;
}

/* outlined fields: quieter borders (Quasar's dark-mode border is very bright) */
.q-field--outlined .q-field__control:before {
    border-color: var(--gui-field-border);
}
.q-field--outlined .q-field__control {
    border-radius: 8px;
}

/* expansion header: no separating line jumping in on hover */
.q-expansion-item .q-item {
    border-radius: 8px;
}
"""

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

    Also sets the app-wide default props that make up the flat look, so call sites
    do not repeat them: every button is a flat round icon button, every number field
    is outlined and dense, every toggle is a flat segmented control.
    """
    ui.colors(primary=PRIMARY)
    ui.add_css(_CSS)
    ui.button.default_props('flat round')
    ui.number.default_props('outlined dense')
    ui.toggle.default_props('unelevated no-caps')
    return ui.dark_mode(dark)


def header(dark: ui.dark_mode) -> None:
    """The page's top app bar: the title plus a single-icon theme toggle.

    The icon shows the *current* mode (Auto/Light/Dark) and a click cycles to the next
    one, like the theme button on nicegui.io. Kept compact and shared by the app and
    the mock runner so both show identical chrome and neither wastes vertical space on
    a large standalone title.
    """
    with ui.header().classes('items-center justify-between px-4 py-2'):
        ui.label('ODrive GUI').classes('text-lg font-medium')
        button = (
            ui.button(color=None, on_click=lambda: dark.set_value(_NEXT_THEME_MODE[dark.value]))
            .props('dense text-color=white')
            .bind_icon_from(dark, 'value', backward=lambda mode: _THEME_MODES[mode][0])
        )
        with button:
            ui.tooltip().bind_text_from(
                dark,
                'value',
                backward=lambda mode: f'Theme: {_THEME_MODES[mode][1]} — click for {_THEME_MODES[_NEXT_THEME_MODE[mode]][1]}',
            )
