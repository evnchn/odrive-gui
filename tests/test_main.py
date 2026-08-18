"""Hardware-free tests for the real entry point, ``src/main.py``.

The render tests in ``test_render.py`` drive ``controls()`` through a test page; these
run the actual ``main.py`` (its page + startup discovery loop) against the stubbed
``odrive`` module, so the discovery -> registry -> per-client render path is covered.
This is the path that silently broke when NiceGUI 3.x turned module-scope UI into
"script mode" and every browser only ever saw the "Waiting…" placeholder.
"""

import asyncio

import pytest
from mock_odrive import make_mock_odrive, set_connected_devices
from nicegui import ui
from nicegui.testing import User

from controls import STATES

pytestmark = pytest.mark.nicegui_main_file('src/main.py')


async def test_placeholder_without_devices(user: User) -> None:
    set_connected_devices([])
    await user.open('/')
    await user.should_see('Waiting for ODrive devices to connect')


async def test_panels_follow_hotplug(user: User) -> None:
    first = make_mock_odrive(serial=0x1111)
    set_connected_devices([first])
    await user.open('/')
    await user.should_see('SN 1111')
    await user.should_not_see('Waiting for ODrive devices to connect')

    # a second device is plugged in: the open page refreshes without a reload
    set_connected_devices([first, make_mock_odrive(serial=0x2222)])
    await user.should_see('SN 2222')
    await user.should_see('SN 1111')

    # both are unplugged: the placeholder is back
    set_connected_devices([])
    await user.should_see('Waiting for ODrive devices to connect')
    await user.should_not_see('SN 1111')


async def test_every_client_sees_the_devices(user: User, create_user) -> None:
    """The panels are rendered per client from the shared registry, not into a single
    global container — so a second browser tab sees the same devices."""
    set_connected_devices([make_mock_odrive(serial=0x3333)])
    await user.open('/')
    await user.should_see('SN 3333')
    other = create_user()
    await other.open('/')
    await other.should_see('SN 3333')


async def test_state_toggle_only_writes_user_choices(user: User) -> None:
    """The axis-state toggle mirrors ``current_state`` but must not echo it back as a
    request: only a state picked in the UI is written to ``requested_state``."""
    dev = make_mock_odrive(two_axes=False)  # one axis -> exactly one state toggle on the page
    axis = dev.axis0
    axis.current_state = 8  # came up in CLOSED_LOOP_CONTROL
    axis.requested_state = 'untouched'
    set_connected_devices([dev])
    await user.open('/')
    await user.should_see('Axis 0')
    await asyncio.sleep(0.3)  # a few binding refresh cycles
    assert axis.requested_state == 'untouched'  # rendering did not request anything

    state_toggle = next(t for t in user.find(ui.toggle).elements if t.options == STATES)
    assert state_toggle.value == 8
    state_toggle.set_value(1)  # the user picks Idle
    assert axis.requested_state == 1

    axis.requested_state = 'untouched'
    axis.current_state = 1  # the firmware followed; the toggle mirrors it …
    await asyncio.sleep(0.3)
    assert state_toggle.value == 1
    assert axis.requested_state == 'untouched'  # … without writing it back
    axis.current_state = 3  # a state the toggle has no option for (calibration) …
    await asyncio.sleep(0.3)
    assert state_toggle.value is None
    assert axis.requested_state == 'untouched'  # … is not written back as 0 either


async def test_stop_with_cleared_input_field_still_writes_zero(user: User) -> None:
    """Safety guard: an emptied ``ui.number`` reads as ``None``; the motion buttons must
    still write ``sign * 0 == 0`` (stop) instead of failing on ``float(None)``."""
    dev = make_mock_odrive(two_axes=False, control_mode=1)  # torque input visible
    dev.axis0.controller.input_torque = 'untouched'
    set_connected_devices([dev])
    await user.open('/')
    await user.should_see('input torque')
    field = next(n for n in user.find(ui.number).elements if n.props['label'] == 'input torque')
    field.set_value(None)  # the user cleared the box
    user.find(ui.button).trigger('click')  # includes the torque stop button (visible buttons only)
    assert dev.axis0.controller.input_torque == 0.0
