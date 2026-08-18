"""Hardware-free tests for the real entry point, ``src/main.py``.

The render tests in ``test_render.py`` drive ``controls()`` through a test page; these
run the actual ``main.py`` (its page + startup discovery loop) against the stubbed
``odrive`` module, so the discovery -> registry -> per-client render path is covered.
This is the path that silently broke when NiceGUI 3.x turned module-scope UI into
"script mode" and every browser only ever saw the "Waiting…" placeholder.
"""

import pytest
from mock_odrive import make_mock_odrive, set_connected_devices
from nicegui.testing import User

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
