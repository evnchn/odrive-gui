"""Hardware-free tests for the control panel against a mock ODrive.

Two layers of safety net, neither of which needs a real ODrive:
- render tests prove the panel *builds* (every widget/binding is constructed);
- a path test proves the mock mirrors every device attribute the UI *reads*, and a
  handler test runs every ``on_click`` against the mock, so a broken attribute path or
  handler fails CI instead of only surfacing when hardware is plugged in.
"""

import types

from mock_odrive import make_mock_odrive
from nicegui import ui
from nicegui.testing import User

from controls import _field_value


async def test_panel_renders(user: User) -> None:
    await user.open('/')
    await user.should_see('Axis 0')
    await user.should_see('Axis 1')
    await user.should_see('SN 208E39855253')


async def test_modes_and_gains_present(user: User) -> None:
    await user.open('/')
    await user.should_see('P-filter')  # INPUT_MODES toggle option
    await user.should_see('pos_gain')
    await user.should_see('current_lim')
    await user.should_see('Live plots')


async def test_action_buttons_run_without_error(user: User) -> None:
    """Fire ``click`` on every button so the save/reboot/dump/clear/motion ``on_click``
    handlers execute against the mock. The NiceGUI ``user`` fixture fails the test on any
    ERROR log, and a raising handler is logged via ``app.handle_exception`` — so a bad
    attribute path, arity or the empty-field ``TypeError`` is caught here.

    Two things this has to get right, both of which silently narrowed the old coverage:
    - ``.trigger('click')`` fires the event on *all* found buttons; ``.click()`` only
      dispatches to the single lowest-id element (here the save button), so the motion
      handlers were never invoked at all under ``.click()``.
    - ``User.find`` returns only *visible* elements, and each control mode hides two of the
      three motion cards — so we render every mode in turn, else ``send_torque`` /
      ``send_position`` stay hidden behind the default velocity mode.
    (control_mode: 1=torque, 2=velocity, 3=position — see ``MODES`` in controls.py.)"""
    for mode in (1, 2, 3):
        await user.open(f'/mode/{mode}')
        user.find(ui.button).trigger('click')


def test_field_value_guards_empty_input() -> None:
    """The motion-handler safety guard (regression cover): an empty ``ui.number`` reads as
    ``None`` in NiceGUI 3.x, and ``_field_value`` must map it to ``0.0`` without raising —
    so ``sign * _field_value(...)`` on the stop button still commands 0 on a spinning motor.
    The click test can't cover this: its fields default to 0, never the cleared ``None`` case."""
    assert _field_value(types.SimpleNamespace(value=None)) == 0.0  # empty field → 0, not TypeError
    assert _field_value(types.SimpleNamespace(value=0)) == 0.0
    assert _field_value(types.SimpleNamespace(value=5.0)) == 5.0
    assert _field_value(types.SimpleNamespace(value=-3.5)) == -3.5  # valid negatives pass through


def test_mock_mirrors_every_read_path() -> None:
    """The mock must expose every attribute the UI reads (CLAUDE.md mirroring rule), so the
    plot ``push()`` and telemetry-label paths stay covered without hardware."""
    dev = make_mock_odrive()
    assert hasattr(dev, 'clear_errors')  # 0.6.x firmware branch of dump_errors(...)
    _ = dev.vbus_voltage
    for axis in (dev.axis0, dev.axis1):
        cc = axis.motor.current_control
        _ = cc.Iq_measured * cc.v_current_control_integral_q  # power label
        _ = cc.Id_setpoint, cc.Id_measured, cc.Iq_setpoint, cc.Iq_measured  # Id/Iq plots
        _ = axis.controller.input_pos, axis.encoder.pos_estimate  # position plot
        _ = axis.controller.input_vel, axis.encoder.vel_estimate  # velocity plot
        _ = axis.motor.fet_thermistor.temperature  # temperature plot
        _ = axis.error, axis.current_state, axis.requested_state
