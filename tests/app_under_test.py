"""The page the NiceGUI ``user`` fixture loads: the control panel against a mock ODrive.

The fixture resets globals and (re)imports this module per test to register the page,
so the page must live in an importable module rather than inside the test itself.
``conftest.install_odrive_stub()`` has already run by import time. The page is built by
the shared ``build_mock_page()`` helper so tests exercise the same chrome the dev runner shows.
"""

from mock_odrive import build_mock_page
from nicegui import ui


@ui.page('/')
def index() -> None:
    build_mock_page()


ui.run()  # intercepted by the NiceGUI test harness; required for the `user` fixture
