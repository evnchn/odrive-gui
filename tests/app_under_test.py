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


@ui.page('/mode/{mode}')
def index_with_mode(mode: int) -> None:
    # same page, but starting in a chosen control mode so tests can render (and click the
    # buttons of) the torque/velocity/position card that mode makes visible.
    build_mock_page(control_mode=mode)


ui.run()  # intercepted by the NiceGUI test harness; required for the `user` fixture
