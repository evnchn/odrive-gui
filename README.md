# ODrive GUI

A web-based GUI to tweak and debug the [ODrive](https://odriverobotics.com) motor controller.
It discovers ODrives on the USB bus and renders one live control panel per device.
It also comes packaged in a Docker image for easy usage.

<img src="https://github.com/zauberzeug/odrive-gui/raw/main/screenshot.png" width="100%">

## Usage

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.
Install the dependencies into a virtual environment:

```bash
uv sync
```

and start the app:

```bash
uv run python src/main.py
```

Then open <http://localhost:8080/>.

Or just start the Docker container with

```bash
docker run -p 8080:8080 --name odrive --rm -it --privileged zauberzeug/odrive-gui:latest
```

It is convenient (but insecure) to use the `--privileged` parameter to allow access to USB.
You can also provide only the device you want to use with `--device=/dev/ttyUSB0` or similar.

## Development

No ODrive on hand? Run the GUI against a built-in **mock device** — useful for UI work,
screenshots and tests with no hardware attached:

```bash
uv run python tools/run_mock.py        # opens on http://localhost:8113/
```

Run the checks (the same gates as CI):

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
```

The mock and its faithful object graph live in `tools/mock_odrive.py`; see
[`CLAUDE.md`](CLAUDE.md) for the project map and a hardware-safety note.
