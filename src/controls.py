"""Per-device control panel for a connected ODrive.

``controls(odrv)`` renders the full tuning UI for one ODrive: a header with
identity/telemetry and global actions, then one card per calibrated axis with
mode/state toggles, live input controls, gains, limits and live plots.

The ``odrv`` argument is a live `fibre` remote object, so it is dynamically
typed (``Any``); every attribute accessed here mirrors the ODrive 0.5.x/0.6.x
object tree. A faithful in-memory stand-in lives in ``tools/mock_odrive.py`` for
hardware-free runs and tests.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from nicegui import ui
from nicegui.events import ValueChangeEventArguments
from odrive.pyfibre import fibre
from odrive.utils import dump_errors

log = logging.getLogger('odrive_gui')

MODES: dict[int, str] = {
    0: 'Voltage',
    1: 'Torque',
    2: 'Velocity',
    3: 'Position',
}

INPUT_MODES: dict[int, str] = {
    0: 'Inactive',
    1: 'Through',
    2: 'V-ramp',
    3: 'P-filter',
    5: 'Trap traj',
    6: 'T-ramp',
    7: 'Mirror',
}

STATES: dict[int, str] = {
    0: 'Undefined',
    1: 'Idle',
    8: 'Loop',
}


def controls(odrv: Any) -> None:
    """Render the control panel for a single connected ODrive device."""

    # Read the serial once, while the device is guaranteed on the bus. Reused for the SN
    # chip and the reboot log so reboot() never does a live read on `odrv` — that read
    # would raise ObjectLostError if the panel outlived the device leaving the bus, and
    # it saves a blocking USB round-trip per reboot click.
    serial = odrv.serial_number

    def reboot() -> None:
        try:
            odrv.reboot()
        except fibre.ObjectLostError:
            # the device drops off the USB bus mid-reboot; that specific loss is expected.
            # do NOT touch `odrv` here — a live read on the just-disconnected device raises again.
            log.info('ODrive %x rebooting (connection dropped as expected)', serial)

    with ui.row().classes('w-full items-center justify-between gap-4 gui-strip'):
        with ui.row().classes('items-center gap-4'):
            _chip(f'SN {hex(serial).removeprefix("0x").upper()}')
            _chip(f'HW {odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
            _chip(f'FW {odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision}{" (dev)" if odrv.fw_version_unreleased else ""}')
            voltage = ui.label().classes('text-lg font-medium text-primary')
            ui.timer(1.0, lambda: voltage.set_text(f'{odrv.vbus_voltage:.2f} V'))
        with ui.row().classes('gap-1'):
            # wrap in a lambda (like the original): passing the bare fibre RemoteFunction makes
            # NiceGUI introspect its signature, which is brittle on the C-backed proxy.
            ui.button(icon='save', on_click=lambda: odrv.save_configuration()).props('dense').tooltip('Save configuration')
            ui.button(icon='bug_report', on_click=lambda: dump_errors(odrv, hasattr(odrv, 'clear_errors'))).props('dense').tooltip(
                'Dump and clear errors'
            )
            ui.button(icon='restart_alt', on_click=reboot).props('dense').tooltip('Reboot ODrive')

    with ui.row().classes('gap-4 items-stretch p-4'):
        for index, axis in enumerate([odrv.axis0, odrv.axis1]):
            if not axis.motor.is_calibrated:
                continue
            with ui.card().props('flat bordered'), ui.column():
                _create_axis_column(index, axis)


def _chip(text: str) -> ui.label:
    """A device identity value (serial, HW/FW version): plain monospace, no box."""
    return ui.label(text).classes('text-sm font-mono opacity-80')


def _field_value(field: ui.number) -> float:
    """The number field's value as a float, treating an empty field (``None`` in
    NiceGUI 3.x) as 0. This is a safety guard: without it ``float(None)`` raises and
    the motion handler aborts — so pressing *stop* (``sign * 0``) on a spinning motor
    with a cleared input box would fail to write 0 and the motor would keep running.
    """
    return float(field.value or 0)


def _create_axis_column(index: int, axis: Any) -> None:
    with ui.row().classes('w-full items-center justify-between'):
        ui.label(f'Axis {index}').classes('text-xl font-medium')
        with ui.row().classes('items-center gap-2'):
            power = ui.label()
            # access via lambda, not `on_click=axis.clear_errors`: the method is optional on
            # older firmware, so it must not be read until the button (if shown) is clicked.
            button = ui.button(icon='bug_report', color='negative', on_click=lambda: axis.clear_errors()).props('dense').tooltip('Clear errors')
            button.set_visibility(hasattr(axis, 'clear_errors'))

    ctr_cfg = axis.controller.config
    mtr_cfg = axis.motor.config
    enc_cfg = axis.encoder.config
    trp_cfg = axis.trap_traj.config
    cc = axis.motor.current_control

    def update_power() -> None:
        if axis.__class__ is fibre.libfibre.EmptyInterface:
            return
        power.set_text(f'{cc.Iq_measured * cc.v_current_control_integral_q:.1f} W')

    # every property read is a blocking USB round-trip on the event loop, so keep the
    # 10 Hz path to the two values that must feel live; the error flag only enables a
    # button and can follow at 1 Hz.
    ui.timer(0.1, update_power)
    ui.timer(1.0, lambda: button.set_enabled(axis.error != 0))

    def request_state(e: ValueChangeEventArguments) -> None:
        # Only a *user* choice becomes a request. The toggle also changes when the
        # binding below mirrors a new current_state into it (then value == current_state)
        # or coerces a state outside STATES (calibration, homing) to None — neither may be
        # written back: a two-way bind did exactly that and e.g. re-requested CLOSED_LOOP
        # for an axis that came up in it, which makes 0.5.x firmware leave and re-enter
        # closed loop (a brief disarm of a live motor).
        if e.value is not None and e.value != axis.current_state:
            axis.requested_state = e.value

    with ui.row().classes('gap-2'):
        mode = ui.toggle(MODES).bind_value(ctr_cfg, 'control_mode')
        ui.toggle(STATES, on_change=request_state).bind_value_from(axis, 'current_state')

    with ui.row().classes('gap-4 items-start'):
        for value, name, attr, icons in _MOTION_INPUTS:
            with ui.column().classes('gap-1').bind_visibility_from(mode, 'value', value=value):
                _motion_input(axis, name, attr, icons)

        with ui.column().classes('gap-1'):
            ui.markdown('**Gains**')
            ui.number('pos_gain', format='%.3f').bind_value(ctr_cfg, 'pos_gain')
            ui.number('vel_gain', format='%.3f').bind_value(ctr_cfg, 'vel_gain')
            ui.number('vel_integrator_gain', format='%.3f').bind_value(ctr_cfg, 'vel_integrator_gain')
            if hasattr(ctr_cfg, 'vel_differentiator_gain'):
                ui.number('vel_differentiator_gain', format='%.3f').bind_value(ctr_cfg, 'vel_differentiator_gain')

        with ui.column().classes('gap-1'):
            ui.markdown('**Limits & bandwidth**')
            ui.number('vel_limit', format='%.3f').bind_value(ctr_cfg, 'vel_limit')
            ui.number('enc_bandwidth', format='%.3f').bind_value(enc_cfg, 'bandwidth')
            ui.number('current_lim', format='%.1f').bind_value(mtr_cfg, 'current_lim')
            ui.number('cur_bandwidth', format='%.3f').bind_value(mtr_cfg, 'current_control_bandwidth')
            ui.number('torque_lim', format='%.1f').bind_value(mtr_cfg, 'torque_lim')
            ui.number('requested_cur_range', format='%.1f').bind_value(mtr_cfg, 'requested_current_range')

    input_mode = ui.toggle(INPUT_MODES).bind_value(ctr_cfg, 'input_mode')
    with ui.row().classes('gap-2 items-start'):
        ui.number('inertia', format='%.3f').bind_value(ctr_cfg, 'inertia').bind_visibility_from(
            input_mode, 'value', backward=lambda m: m in [2, 3, 5]
        )
        ui.number('velocity ramp rate', format='%.3f').bind_value(ctr_cfg, 'vel_ramp_rate').bind_visibility_from(input_mode, 'value', value=2)
        ui.number('input filter bandwidth', format='%.3f').bind_value(ctr_cfg, 'input_filter_bandwidth').bind_visibility_from(
            input_mode, 'value', value=3
        )
        with ui.row().classes('gap-2').bind_visibility_from(input_mode, 'value', value=5):
            ui.number('trajectory velocity limit', format='%.3f').bind_value(trp_cfg, 'vel_limit')
            ui.number('trajectory acceleration limit', format='%.3f').bind_value(trp_cfg, 'accel_limit')
            ui.number('trajectory deceleration limit', format='%.3f').bind_value(trp_cfg, 'decel_limit')
        ui.number('torque ramp rate', format='%.3f').bind_value(ctr_cfg, 'torque_ramp_rate').bind_visibility_from(input_mode, 'value', value=6)
        ui.number('mirror ratio', format='%.3f').bind_value(ctr_cfg, 'mirror_ratio').bind_visibility_from(input_mode, 'value', value=7)
        ui.toggle({0: 'Axis 0', 1: 'Axis 1'}).bind_value(ctr_cfg, 'axis_to_mirror', forward=lambda x: 255 if x is None else x).bind_visibility_from(
            input_mode, 'value', value=7
        )

    with ui.expansion('Live plots', icon='show_chart').classes('w-full'):
        _live_plots(axis)


# the torque / velocity / position inputs: (control_mode value, label, controller attribute, icons)
_MOTION_INPUTS: list[tuple[int, str, str, tuple[str, str, str]]] = [
    (1, 'Torque', 'input_torque', ('remove', 'radio_button_unchecked', 'add')),
    (2, 'Velocity', 'input_vel', ('fast_rewind', 'stop', 'fast_forward')),
    (3, 'Position', 'input_pos', ('skip_previous', 'exposure_zero', 'skip_next')),
]


def _motion_input(axis: Any, name: str, attr: str, icons: tuple[str, str, str]) -> None:
    """A labelled number field plus -/0/+ buttons that write ``sign * value`` to ``axis.controller.<attr>``."""
    ui.markdown(f'**{name}**')
    field = ui.number(f'input {name.lower()}', value=0)

    def send(sign: int) -> None:
        setattr(axis.controller, attr, sign * _field_value(field))

    with ui.row().classes('w-full justify-around gap-0'):
        for icon, sign in zip(icons, (-1, 0, 1), strict=True):
            ui.button(icon=icon, on_click=lambda sign=sign: send(sign))


def _live_plots(axis: Any) -> None:
    """Checkbox-gated live plots. One 20 Hz timer per axis samples the device for every
    enabled plot, and it only exists while at least one plot is enabled — an idle
    NiceGUI timer still wakes every interval, and five per axis added up."""
    cc = axis.motor.current_control
    plots: list[tuple[ui.checkbox, ui.line_plot, Callable[[], list[list[float]]]]] = []
    timer: ui.timer | None = None

    def push() -> None:
        now = datetime.now()
        for check, plot, sample in plots:
            if check.value:
                # line_plot uses a datetime x-axis (matplotlib handles it); the stub types x as float.
                plot.push([now], sample())  # type: ignore[list-item]

    def update_timer() -> None:
        nonlocal timer
        if any(check.value for check, _, _ in plots):
            if timer is None:
                timer = ui.timer(0.05, push)
        elif timer is not None:
            timer.cancel()
            timer.delete()
            timer = None

    for name, legend, sample in (
        ('Position', ['input_pos', 'pos_estimate'], lambda: [[axis.controller.input_pos], [axis.encoder.pos_estimate]]),
        ('Velocity', ['input_vel', 'vel_estimate'], lambda: [[axis.controller.input_vel], [axis.encoder.vel_estimate]]),
        ('Id', ['Id_setpoint', 'Id_measured'], lambda: [[cc.Id_setpoint], [cc.Id_measured]]),
        ('Iq', ['Iq_setpoint', 'Iq_measured'], lambda: [[cc.Iq_setpoint], [cc.Iq_measured]]),
        ('Temperature', ['fet_temperature'], lambda: [[axis.motor.fet_thermistor.temperature]]),
    ):
        check = ui.checkbox(f'{name} plot', on_change=update_timer)
        plot = ui.line_plot(n=len(legend), update_every=10).with_legend(legend, loc='upper left', ncol=2)
        check.bind_value_to(plot, 'visible')
        plots.append((check, plot, sample))
