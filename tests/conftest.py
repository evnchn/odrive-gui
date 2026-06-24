"""Test config: install the fake ``odrive`` package before any source import.

``src/controls.py`` imports ``odrive`` at module load, so the stub must be
registered first. ``pythonpath = ['src', 'tools']`` (pyproject) puts both on the
path; importing ``mock_odrive`` here and calling ``install_odrive_stub()`` at
collection time makes ``from controls import controls`` work hardware-free.
"""

import pytest
from mock_odrive import install_odrive_stub, make_mock_odrive

install_odrive_stub()

# app_under_test.py is the app the `user` fixture executes via runpy (with the
# simulation env set); it must NOT be collected/imported as a test module, or its
# top-level ui.run() would try to bind a real socket at collection time.
collect_ignore = ['app_under_test.py']

# the lightweight in-process fixtures only — avoids nicegui.testing.plugin pulling
# in the selenium-based Screen plugin, which we do not use.
pytest_plugins = ['nicegui.testing.general_fixtures', 'nicegui.testing.user_plugin']


@pytest.fixture
def mock_odrive():
    return make_mock_odrive()
