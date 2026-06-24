"""Run the GUI against a mock ODrive (no hardware). For dev / screenshots / tests.

Usage:  python tools/run_mock.py [port]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, os.path.dirname(__file__))

from mock_odrive import install_odrive_stub, make_mock_odrive  # noqa: E402

install_odrive_stub()

from nicegui import ui  # noqa: E402

from controls import controls  # noqa: E402
from theme import apply_theme  # noqa: E402

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8113

apply_theme()
ui.markdown('## ODrive GUI')
with ui.row().classes('gap-4 items-stretch'):
    controls(make_mock_odrive())

ui.run(title='ODrive Motor Tuning (mock)', port=PORT, reload=False, show=False)
