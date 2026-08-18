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
from theme import apply_theme, header

logging.getLogger('nicegui').setLevel(logging.ERROR)
log = logging.getLogger('odrive_gui')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

dark = apply_theme()

# panels currently rendered, keyed by device serial number; held on a namespace
# so its truthiness can drive the "waiting…" placeholder via a visibility binding.
state = SimpleNamespace(devices={})

header(dark)
ui.markdown('Waiting for ODrive devices to connect…').classes('p-4').bind_visibility_from(state, 'devices', backward=lambda d: not d)
# one full-width panel per device, stacked: each starts with its info strip docked
# under the header (or under the previous device's cards).
container = ui.column().classes('w-full gap-0')


async def discovery_loop() -> None:
    """Continuously reconcile the rendered panels with the connected devices."""
    odrive.start_discovery(odrive.default_usb_search_path)
    while True:
        for device in odrive.connected_devices:
            # controls() does many live reads; if the device leaves the bus mid-build it
            # raises ObjectLostError. Isolate the per-device body so one failure neither
            # kills this loop nor leaves a half-built column registered in state.devices
            # (the serial is only recorded after controls() fully succeeds).
            try:
                serial_number = device.serial_number
                if serial_number in state.devices:
                    continue
                log.info('Adding ODrive %x', serial_number)
                with container:
                    column = ui.column().classes('w-full gap-0')
                try:
                    with column:
                        controls(device)
                except Exception:
                    container.remove(column)  # discard the half-built panel before re-raising
                    raise
                state.devices[serial_number] = column
            except Exception:
                log.exception('Failed to build ODrive panel (device left the bus mid-enumeration?)')
        for serial_number in list(state.devices):
            try:
                still_connected = any(d.serial_number == serial_number for d in odrive.connected_devices)
            except Exception:
                # a device going stale mid-check raises ObjectLostError on the live
                # serial read; skip this cycle (keep the panel) rather than let it kill
                # the loop — the next connected_devices_changed retries with a clean read.
                log.exception('Failed to read connected devices during removal check; retrying next cycle')
                continue
            if not still_connected:
                log.info('Removing ODrive %x', serial_number)
                # container.remove() deletes the column and all its descendants; NiceGUI
                # cancels each panel timer on deletion (Timer._handle_delete / _should_stop
                # checks is_deleted), so no manual timer teardown is needed.
                container.remove(state.devices.pop(serial_number))
        await asyncio.wrap_future(odrive.connected_devices_changed)


app.on_startup(discovery_loop)

ui.run(title='ODrive Motor Tuning', favicon='⚙️')
