"""The page the NiceGUI ``user`` fixture loads: the control panel against a mock ODrive.

The fixture resets globals and (re)imports this module per test to register the page,
so the page must live in an importable module rather than inside the test itself.
``conftest.install_odrive_stub()`` has already run by import time.
"""

from mock_odrive import make_mock_odrive
from nicegui import ui

from controls import controls
from theme import apply_theme


@ui.page('/')
def index() -> None:
    apply_theme()
    controls(make_mock_odrive())


ui.run()  # intercepted by the NiceGUI test harness; required for the `user` fixture
