#!/usr/bin/env python3
"""ODrive GUI — a web UI to tune and debug ODrive motor controllers.

Discovers ODrives on the USB bus and renders one live control panel per device,
adding and removing panels as devices connect and disconnect.
"""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

import odrive
from nicegui import app, ui

from controls import controls
from theme import apply_theme

logging.getLogger('nicegui').setLevel(logging.ERROR)
log = logging.getLogger('odrive_gui')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

apply_theme()

# panels currently rendered, keyed by device serial number; held on a namespace
# so its truthiness can drive the "waiting…" placeholder via a visibility binding.
state = SimpleNamespace(devices={})

ui.markdown('## ODrive GUI')
ui.markdown('Waiting for ODrive devices to connect…').bind_visibility_from(state, 'devices', backward=lambda d: not d)
container = ui.row().classes('gap-4 items-stretch')


async def discovery_loop() -> None:
    """Continuously reconcile the rendered panels with the connected devices."""
    odrive.start_discovery(odrive.default_usb_search_path)
    while True:
        for device in odrive.connected_devices:
            if device.serial_number not in state.devices:
                log.info('Adding ODrive %x', device.serial_number)
                with container:
                    with ui.column() as state.devices[device.serial_number]:
                        controls(device)
        for serial_number in list(state.devices):
            if not any(d.serial_number == serial_number for d in odrive.connected_devices):
                log.info('Removing ODrive %x', serial_number)
                column = state.devices.pop(serial_number)
                # ui.timer does not auto-cancel on element deletion, so the panel's
                # voltage/power/plot timers would keep polling the lost device. Cancel
                # them before removing the column.
                for element in column.descendants():
                    if isinstance(element, ui.timer):
                        element.cancel()
                container.remove(column)
        await asyncio.wrap_future(odrive.connected_devices_changed)


app.on_startup(discovery_loop)

ui.run(title='ODrive Motor Tuning')
