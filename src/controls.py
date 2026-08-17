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
from datetime import datetime
from typing import Any

from nicegui import ui
from odrive.pyfibre import fibre
from odrive.utils import dump_errors

log = logging.getLogger('odrive_gui')

MODES: dict[int, str] = {
    0: 'voltage',
    1: 'torque',
    2: 'velocity',
    3: 'position',
}

INPUT_MODES: dict[int, str] = {
    0: 'inactive',
    1: 'through',
    2: 'v-ramp',
    3: 'p-filter',
    5: 'trap traj',
    6: 't-ramp',
    7: 'mirror',
}

STATES: dict[int, str] = {
    0: 'undefined',
    1: 'idle',
    8: 'loop',
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
        except Exception as err:
            # the device drops off the USB bus mid-reboot; that specific loss is expected.
            # do NOT touch `odrv` here — a live read on the just-disconnected device raises again.
            if type(err).__name__ == 'ObjectLostError':
                log.info('ODrive %x rebooting (connection dropped as expected)', serial)
            else:
                raise

    with ui.row().classes('w-full items-center justify-between gap-4'):
        with ui.row().classes('items-center gap-2'):
            _chip(f'SN {hex(serial).removeprefix("0x").upper()}')
            _chip(f'HW {odrv.hw_version_major}.{odrv.hw_version_minor}.{odrv.hw_version_variant}')
            _chip(f'FW {odrv.fw_version_major}.{odrv.fw_version_minor}.{odrv.fw_version_revision}{" (dev)" if odrv.fw_version_unreleased else ""}')
            voltage = ui.label().classes('text-lg font-medium text-primary')
            ui.timer(1.0, lambda: voltage.set_text(f'{odrv.vbus_voltage:.2f} V'))
        with ui.row().classes('gap-1'):
            # wrap in a lambda (like the original): passing the bare fibre RemoteFunction makes
            # NiceGUI introspect its signature, which is brittle on the C-backed proxy.
            ui.button(on_click=lambda: odrv.save_configuration()).props('icon=save flat round').tooltip('Save configuration')
            ui.button(on_click=lambda: dump_errors(odrv, hasattr(odrv, 'clear_errors'))).props('icon=bug_report flat round').tooltip(
                'Dump and clear errors'
            )
            ui.button(on_click=reboot).props('icon=restart_alt flat round').tooltip('Reboot ODrive')

    with ui.row().classes('gap-4 items-stretch'):
        for index, axis in enumerate([odrv.axis0, odrv.axis1]):
            if not axis.motor.is_calibrated:
                continue
            with ui.card(), ui.column():
                _create_axis_column(index, axis)


def _chip(text: str) -> ui.label:
    return ui.label(text).classes('px-2 py-1 rounded bg-slate-500/15 text-sm font-mono')


def _field_value(field: ui.number) -> float:
    """The number field's value as a float, treating an empty field (``None`` in
    NiceGUI 3.x) as 0. This is a safety guard: without it ``float(None)`` raises and
    the motion handler aborts — so pressing *stop* (``sign * 0``) on a spinning motor
    with a cleared input box would fail to write 0 and the motor would keep running.
    """
    return float(field.value or 0)


def _create_axis_column(index: int, axis: Any) -> None:
    with ui.row().classes('w-full items-center justify-between'):
        ui.markdown(f'### Axis {index}')
        with ui.row().classes('items-center gap-2'):
            power = ui.label()
            # access via lambda, not `on_click=axis.clear_errors`: the method is optional on
            # older firmware, so it must not be read until the button (if shown) is clicked.
            button = ui.button(on_click=lambda: axis.clear_errors()).props('icon=bug_report flat round dense color=negative').tooltip('Clear errors')
            button.set_visibility(hasattr(axis, 'clear_errors'))

    def update() -> None:
        if axis.__class__ is fibre.libfibre.EmptyInterface:
            return
        cc = axis.motor.current_control
        power.set_text(f'{cc.Iq_measured * cc.v_current_control_integral_q:.1f} W')
        button.set_enabled(axis.error != 0)

    ui.timer(0.1, update)

    ctr_cfg = axis.controller.config
    mtr_cfg = axis.motor.config
    enc_cfg = axis.encoder.config
    trp_cfg = axis.trap_traj.config

    with ui.row().classes('gap-2'):
        mode = ui.toggle(MODES).bind_value(ctr_cfg, 'control_mode')
        ui.toggle(STATES).bind_value_to(axis, 'requested_state', forward=lambda x: x or 0).bind_value_from(axis, 'current_state')

    with ui.row().classes('gap-4 items-start'):
        with ui.card().props('flat bordered').bind_visibility_from(mode, 'value', value=1):
            ui.markdown('**Torque**')
            torque = ui.number('input torque', value=0)

            def send_torque(sign: int) -> None:
                axis.controller.input_torque = sign * _field_value(torque)

            with ui.row():
                ui.button(on_click=lambda: send_torque(-1)).props('round flat icon=remove')
                ui.button(on_click=lambda: send_torque(0)).props('round flat icon=radio_button_unchecked')
                ui.button(on_click=lambda: send_torque(1)).props('round flat icon=add')

        with ui.card().props('flat bordered').bind_visibility_from(mode, 'value', value=2):
            ui.markdown('**Velocity**')
            velocity = ui.number('input velocity', value=0)

            def send_velocity(sign: int) -> None:
                axis.controller.input_vel = sign * _field_value(velocity)

            with ui.row():
                ui.button(on_click=lambda: send_velocity(-1)).props('round flat icon=fast_rewind')
                ui.button(on_click=lambda: send_velocity(0)).props('round flat icon=stop')
                ui.button(on_click=lambda: send_velocity(1)).props('round flat icon=fast_forward')

        with ui.card().props('flat bordered').bind_visibility_from(mode, 'value', value=3):
            ui.markdown('**Position**')
            position = ui.number('input position', value=0)

            def send_position(sign: int) -> None:
                axis.controller.input_pos = sign * _field_value(position)

            with ui.row():
                ui.button(on_click=lambda: send_position(-1)).props('round flat icon=skip_previous')
                ui.button(on_click=lambda: send_position(0)).props('round flat icon=exposure_zero')
                ui.button(on_click=lambda: send_position(1)).props('round flat icon=skip_next')

        with ui.column().classes('gap-1'):
            ui.markdown('**Gains**')
            ui.number('pos_gain', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'pos_gain')
            ui.number('vel_gain', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'vel_gain')
            ui.number('vel_integrator_gain', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'vel_integrator_gain')
            if hasattr(ctr_cfg, 'vel_differentiator_gain'):
                ui.number('vel_differentiator_gain', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'vel_differentiator_gain')

        with ui.column().classes('gap-1'):
            ui.markdown('**Limits & bandwidth**')
            ui.number('vel_limit', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'vel_limit')
            ui.number('enc_bandwidth', format='%.3f').props('outlined dense').bind_value(enc_cfg, 'bandwidth')
            ui.number('current_lim', format='%.1f').props('outlined dense').bind_value(mtr_cfg, 'current_lim')
            ui.number('cur_bandwidth', format='%.3f').props('outlined dense').bind_value(mtr_cfg, 'current_control_bandwidth')
            ui.number('torque_lim', format='%.1f').props('outlined dense').bind_value(mtr_cfg, 'torque_lim')
            ui.number('requested_cur_range', format='%.1f').props('outlined dense').bind_value(mtr_cfg, 'requested_current_range')

    input_mode = ui.toggle(INPUT_MODES).bind_value(ctr_cfg, 'input_mode')
    with ui.row().classes('gap-2 items-start'):
        ui.number('inertia', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'inertia').bind_visibility_from(
            input_mode, 'value', backward=lambda m: m in [2, 3, 5]
        )
        ui.number('velocity ramp rate', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'vel_ramp_rate').bind_visibility_from(
            input_mode, 'value', value=2
        )
        ui.number('input filter bandwidth', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'input_filter_bandwidth').bind_visibility_from(
            input_mode, 'value', value=3
        )
        ui.number('trajectory velocity limit', format='%.3f').props('outlined dense').bind_value(trp_cfg, 'vel_limit').bind_visibility_from(
            input_mode, 'value', value=5
        )
        ui.number('trajectory acceleration limit', format='%.3f').props('outlined dense').bind_value(trp_cfg, 'accel_limit').bind_visibility_from(
            input_mode, 'value', value=5
        )
        ui.number('trajectory deceleration limit', format='%.3f').props('outlined dense').bind_value(trp_cfg, 'decel_limit').bind_visibility_from(
            input_mode, 'value', value=5
        )
        ui.number('torque ramp rate', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'torque_ramp_rate').bind_visibility_from(
            input_mode, 'value', value=6
        )
        ui.number('mirror ratio', format='%.3f').props('outlined dense').bind_value(ctr_cfg, 'mirror_ratio').bind_visibility_from(
            input_mode, 'value', value=7
        )
        ui.toggle({0: 'axis 0', 1: 'axis 1'}).bind_value(ctr_cfg, 'axis_to_mirror', forward=lambda x: 255 if x is None else x).bind_visibility_from(
            input_mode, 'value', value=7
        )

    with ui.expansion('Live plots', icon='show_chart').classes('w-full'):
        _plot(axis, 'Position', lambda ax: ([ax.controller.input_pos], [ax.encoder.pos_estimate]), ['input_pos', 'pos_estimate'])
        _plot(axis, 'Velocity', lambda ax: ([ax.controller.input_vel], [ax.encoder.vel_estimate]), ['input_vel', 'vel_estimate'])
        _plot(axis, 'Id', lambda ax: ([ax.motor.current_control.Id_setpoint], [ax.motor.current_control.Id_measured]), ['Id_setpoint', 'Id_measured'])
        _plot(axis, 'Iq', lambda ax: ([ax.motor.current_control.Iq_setpoint], [ax.motor.current_control.Iq_measured]), ['Iq_setpoint', 'Iq_measured'])
        _plot(axis, 'Temperature', lambda ax: ([ax.motor.fet_thermistor.temperature],), None)


def _plot(axis: Any, name: str, sample: Any, legend: list[str] | None) -> None:
    """One checkbox-gated live line plot. ``sample(axis)`` returns the per-line value lists.

    The number of lines is taken from ``legend`` (or 1 when there is none) so the
    device is not read until a timer push actually fires.
    """
    check = ui.checkbox(f'{name} plot')
    plot = ui.line_plot(n=len(legend) if legend else 1, update_every=10)
    if legend:
        plot.with_legend(legend, loc='upper left', ncol=2)

    def push() -> None:
        # line_plot uses a datetime x-axis (matplotlib handles it); the stub types x as float.
        plot.push([datetime.now()], list(sample(axis)))  # type: ignore[list-item]

    timer = ui.timer(0.05, push)
    check.bind_value_to(plot, 'visible').bind_value_to(timer, 'active')
