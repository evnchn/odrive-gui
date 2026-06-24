"""Hardware-free tests for the control panel against a mock ODrive.

Two layers of safety net, neither of which needs a real ODrive:
- render tests prove the panel *builds* (every widget/binding is constructed);
- a path test proves the mock mirrors every device attribute the UI *reads*, and a
  handler test runs every ``on_click`` against the mock, so a broken attribute path or
  handler fails CI instead of only surfacing when hardware is plugged in.
"""

from mock_odrive import make_mock_odrive
from nicegui import ui
from nicegui.testing import User


async def test_panel_renders(user: User) -> None:
    await user.open('/')
    await user.should_see('Axis 0')
    await user.should_see('Axis 1')
    await user.should_see('SN 208E39855253')


async def test_modes_and_gains_present(user: User) -> None:
    await user.open('/')
    await user.should_see('velocity')  # MODES toggle option (CSS uppercases it in the UI)
    await user.should_see('pos_gain')
    await user.should_see('current_lim')
    await user.should_see('Live plots')


async def test_action_buttons_run_without_error(user: User) -> None:
    """Click every button so the save/reboot/dump/clear/motion ``on_click`` handlers
    execute against the mock. The NiceGUI ``user`` fixture fails the test on any ERROR log,
    so a handler that raises (e.g. a bad arity or attribute) is caught here."""
    await user.open('/')
    user.find(ui.button).click()


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
