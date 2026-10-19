"""Hardware-free tests for the real entry point, ``src/main.py``.

The render tests in ``test_render.py`` drive ``controls()`` through a test page; these
run the actual ``main.py`` (its page + startup discovery loop) against the stubbed
``odrive`` module, so the discovery -> registry -> per-client render path is covered.
This is the path that silently broke when NiceGUI 3.x turned module-scope UI into
"script mode" and every browser only ever saw the "Waiting…" placeholder.
"""

import asyncio
import threading

import pytest
from mock_odrive import arrive_mid_scan, lose_mock_odrive, make_mock_odrive, set_connected_devices
from nicegui import ui
from nicegui.testing import User
from nicegui.testing.user_interaction import UserInteraction

from controls import STATES, _usb


def pick(user: User, toggle: ui.toggle, state: int) -> None:
    """Click ``state`` on the axis-state toggle, as the browser reports it."""
    UserInteraction(user, {toggle}, None).trigger('update:modelValue', list(STATES).index(state))


async def drain() -> None:
    """Wait until every device write queued so far has run on the USB worker."""
    await asyncio.wrap_future(_usb.submit(lambda: None))


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


async def test_device_arriving_during_the_scan_is_not_missed(user: User) -> None:
    """odrive installs a *new* ``connected_devices_changed`` future before resolving the old
    one, so a device enumerating while the loop scans resolves a future the loop no longer
    holds. Unless the loop captured the signal before scanning, that wake-up is lost: the
    loop awaits the replacement forever and the second panel never appears."""
    first = make_mock_odrive(serial=0x1111)
    trap = arrive_mid_scan(first, make_mock_odrive(serial=0x2222))
    set_connected_devices([first])  # wakes the loop, which then plugs 2222 in mid-scan
    await user.open('/')
    await user.should_see('SN 2222')
    await user.should_see('SN 1111')
    assert trap['fired_mid_scan']  # it really raced the scan, not an ordinary hot-plug


async def test_lost_device_drops_only_its_panel(user: User) -> None:
    """libfibre swaps a lost object's class to ``EmptyInterface`` on its own thread, so a
    device can turn into one between the registry update and a page render (or between
    two reads of a panel build). Its reads then raise ``AttributeError``, not
    ``ObjectLostError``; that must cost only that device's panel, not the page, and
    must not kill the discovery loop either."""
    alive, lost = make_mock_odrive(serial=0x1111), make_mock_odrive(serial=0x2222)
    set_connected_devices([alive, lost])
    await user.open('/')
    await user.should_see('SN 2222')

    lose_mock_odrive(lost)  # the registry still lists it, but every read now fails
    await user.open('/')  # a fresh client renders from the stale registry
    await user.should_see('SN 1111')
    await user.should_not_see('SN 2222')

    # the discovery loop reads the serial of every listed device: a lost one is skipped,
    # the loop survives and still picks up the next hot-plug event
    set_connected_devices([alive, lost])
    await asyncio.sleep(0.1)
    set_connected_devices([alive, make_mock_odrive(serial=0x3333)])
    await user.should_see('SN 3333')


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
    pick(user, state_toggle, 1)  # the user picks Idle
    await drain()
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
    await drain()
    assert dev.axis0.controller.input_torque == 0.0


async def test_gain_edits_reach_the_device_and_device_changes_reach_the_ui(user: User) -> None:
    """The widgets bind to local mirrors, so both directions must still get through: an
    edit is written to the device (and not undone by a refresh that read the old value
    in the meantime), and a change made on the device shows up in the UI."""
    device = make_mock_odrive(two_axes=False)  # one axis -> exactly one pos_gain field
    set_connected_devices([device])
    await user.open('/')
    await user.should_see('pos_gain')
    field = next(n for n in user.find(ui.number).elements if n.props.get('label') == 'pos_gain')
    config = device.axis0.controller.config

    field.set_value(42.0)
    await asyncio.sleep(1.2)
    assert config.pos_gain == 42.0
    assert field.value == 42.0

    config.pos_gain = 7.0  # changed behind the UI's back (odrivetool, another client)
    await asyncio.sleep(1.2)
    assert field.value == 7.0


def _record_state_requests(axis, follow: bool = True) -> list[tuple[int, float]]:
    """Record every ``requested_state`` write, with the ``current_lim`` the device had then."""
    seen: list[tuple[int, float]] = []

    def _request(self, state: int) -> None:
        seen.append((state, self.motor.config.current_lim))
        if follow:
            self.current_state = state  # the firmware follows at once

    axis.__class__ = type(
        'RecordingAxis',
        (type(axis),),
        {'requested_state': property(lambda self: seen[-1][0] if seen else 1, _request)},
    )
    return seen


async def test_a_quick_loop_then_idle_is_not_dropped(user: User) -> None:
    """The toggle's cached state can be a refresh old: the user picks Loop, the firmware
    enters it, and the user picks Idle before the next refresh. Idle then equals the cached
    state, but it is a user choice and must be requested."""
    dev = make_mock_odrive(two_axes=False)
    seen = _record_state_requests(dev.axis0)
    set_connected_devices([dev])
    await user.open('/')
    await user.should_see('Axis 0')
    state_toggle = next(t for t in user.find(ui.toggle).elements if t.options == STATES)
    gate = threading.Event()
    _usb.submit(gate.wait)  # hold the worker: no refresh can run in between
    pick(user, state_toggle, 8)
    pick(user, state_toggle, 1)
    gate.set()
    await drain()
    assert [state for state, _ in seen] == [8, 1]


async def test_a_command_does_not_overtake_a_setting_changed_before_it(user: User) -> None:
    """Lowering ``current_lim`` and then entering closed loop must reach the device in that
    order, even while the USB worker is busy: the limit is the motor's protection."""
    dev = make_mock_odrive(two_axes=False)
    seen = _record_state_requests(dev.axis0)
    set_connected_devices([dev])
    await user.open('/')
    await user.should_see('current_lim')
    limit = next(n for n in user.find(ui.number).elements if n.props.get('label') == 'current_lim')
    state_toggle = next(t for t in user.find(ui.toggle).elements if t.options == STATES)
    gate = threading.Event()
    _usb.submit(gate.wait)  # the worker is busy (a slow read, a refresh)
    limit.set_value(1.0)
    pick(user, state_toggle, 8)
    gate.set()
    await drain()
    assert seen == [(8, 1.0)]


async def test_a_refresh_in_flight_does_not_hide_a_newer_state_choice(user: User) -> None:
    """A refresh reads Idle, the user picks Loop and the firmware enters it, then the
    refresh finishes. Showing its stale Idle would make the toggle's value already Idle,
    so NiceGUI would swallow the user's next Idle click as "no change"."""
    dev = make_mock_odrive(two_axes=False)
    seen = _record_state_requests(dev.axis0)
    set_connected_devices([dev])
    await user.open('/')
    await user.should_see('Axis 0')
    state_toggle = next(t for t in user.find(ui.toggle).elements if t.options == STATES)
    refresh_timer = next(e for e in user.client.elements.values() if isinstance(e, ui.timer) and e.callback.__name__ == 'sync_mirrors')
    refresh_timer.active = False  # drive the refreshes by hand
    await asyncio.sleep(0.2)  # a tick already running has finished
    gate = threading.Event()
    _usb.submit(gate.wait)
    refresh = asyncio.create_task(refresh_timer.callback())
    await asyncio.sleep(0.01)  # its read of the state (Idle) is queued behind the gate
    pick(user, state_toggle, 8)  # the user picks Loop; queued after that read
    gate.set()
    await refresh
    assert state_toggle.value == 8
    pick(user, state_toggle, 1)  # and then Idle
    await drain()
    assert [state for state, _ in seen] == [8, 1]


async def test_idle_goes_through_while_the_shown_state_is_a_refresh_old(user: User) -> None:
    """The user picks Loop; a refresh still reads Idle because the firmware has not switched
    yet, so the toggle shows Idle again; then the firmware enters Loop. The user's Idle click
    (made while the browser still showed Loop, or after) must be requested, although the
    server-side toggle already holds Idle."""
    dev = make_mock_odrive(two_axes=False)
    seen = _record_state_requests(dev.axis0, follow=False)
    set_connected_devices([dev])
    await user.open('/')
    await user.should_see('Axis 0')
    state_toggle = next(t for t in user.find(ui.toggle).elements if t.options == STATES)
    pick(user, state_toggle, 8)
    await asyncio.sleep(0.3)  # refreshes still read Idle
    assert state_toggle.value == 1
    dev.axis0.current_state = 8  # now the firmware switches
    pick(user, state_toggle, 1)
    await drain()
    assert [state for state, _ in seen] == [8, 1]
