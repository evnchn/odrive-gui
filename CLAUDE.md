# ODrive GUI — agent guide

A small [NiceGUI](https://nicegui.io) web app to tune and debug
[ODrive](https://odriverobotics.com) motor controllers. It discovers ODrives on
the USB bus and renders one live control panel per device.

## Layout

| Path | What |
|---|---|
| `src/main.py` | Entry point: USB discovery loop + page scaffold. `python src/main.py`. |
| `src/controls.py` | The per-device control panel — `controls(odrv)`. All the UI lives here. |
| `src/theme.py` | Shared colour scheme + dark mode (`apply_theme()`), used by the app and the mock runner. |
| `tools/mock_odrive.py` | A faithful in-memory fake ODrive **+ a stub of the `odrive` package**. Lets the UI run, be screenshotted and tested with **no hardware attached**. |
| `tools/run_mock.py` | `python tools/run_mock.py [port]` — runs the GUI against the mock. |
| `tests/` | pytest render/smoke tests driving the mock through NiceGUI's `User` fixture. |

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

python src/main.py            # needs a real ODrive on USB
python tools/run_mock.py      # no hardware — opens on :8113
```

## Test / lint / type-check (the CI gates)

```bash
ruff check . && ruff format --check .
mypy src
pytest
```

## How the device object works (important)

`controls(odrv)` takes a **live `fibre` remote object**, so it is dynamically
typed (`Any`). Every attribute it reads (`odrv.axis0.motor.current_control.Iq_measured`,
`odrv.axis0.controller.config.pos_gain`, …) mirrors the ODrive 0.5.x/0.6.x object
tree. When you change the UI, mirror the same attribute path in
`tools/mock_odrive.py` so the hardware-free tests keep covering it.

## Hardware safety (if you connect a real ODrive)

This GUI can command motion (the torque/velocity/position buttons) and switch an
axis into closed-loop control. On a clone board **without hardware overcurrent
protection**, software `current_lim` is the only real-time motor protection.
Do not energize an unattended motor; never run open-loop for long. Treat config
display and telemetry as the safe read-only baseline.
