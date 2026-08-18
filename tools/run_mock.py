"""Run the GUI against a mock ODrive (no hardware). For dev / screenshots / tests.

Runs the real ``src/main.py`` (page + discovery loop) on top of the stubbed ``odrive``
package with one mock device "plugged in", so what you see is exactly what a browser
sees with hardware attached — the same chrome, the same code path.

Usage:  python tools/run_mock.py [port]
"""

import os
import sys

for path in (os.path.join(os.path.dirname(__file__), '..', 'src'), os.path.dirname(__file__)):
    if path not in sys.path:
        sys.path.insert(0, path)

from mock_odrive import install_odrive_stub, make_mock_odrive, set_connected_devices  # noqa: E402

install_odrive_stub()
set_connected_devices([make_mock_odrive()])

from nicegui import ui  # noqa: E402

import main  # noqa: E402, F401  # registers the page and the discovery loop; its ui.run() is guarded

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8113

ui.run(title='ODrive Motor Tuning (mock)', favicon='⚙️', port=PORT, reload=False, show=False)
