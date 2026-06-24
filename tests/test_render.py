"""Render/smoke tests: the control panel must build cleanly against a mock ODrive.

This is the hardware-free safety net — it exercises every binding and widget that
``controls()`` creates (via ``app_under_test.index``), so a broken attribute path or
NiceGUI API drift fails CI instead of only showing up when a real ODrive is plugged in.
"""

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
