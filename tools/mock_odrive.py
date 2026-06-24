"""A faithful in-memory fake of an ODrive device + a stub of the ``odrive`` package.

This lets the GUI run (and be screenshotted / tested) with **no hardware attached**.
It mirrors exactly the attribute graph that ``src/controls.py`` reads and writes.

Two entry points:

* ``install_odrive_stub()`` -- registers fake ``odrive``, ``odrive.pyfibre.fibre``
  and ``odrive.utils`` modules in ``sys.modules`` so ``import odrive`` /
  ``from odrive.utils import dump_errors`` succeed without the real package.
* ``make_mock_odrive(serial=...)`` -- returns one fake device whose config
  objects accept ``setattr`` (so NiceGUI two-way bindings work) and whose
  telemetry fields animate over time (so plots/labels look alive in a capture).
"""

from __future__ import annotations

import math
import sys
import time
import types

_T0 = time.time()


def _wave(period: float, amp: float, offset: float = 0.0) -> float:
    return offset + amp * math.sin(2 * math.pi * (time.time() - _T0) / period)


class _Config:
    """A plain settable namespace -- NiceGUI bindings get/set attributes here."""

    def __init__(self, **kw: object) -> None:
        self.__dict__.update(kw)


class _CurrentControl:
    Iq_setpoint = 0.4
    Id_setpoint = 0.0

    @property
    def Iq_measured(self) -> float:
        return _wave(2.0, 0.05, 0.42)

    @property
    def Id_measured(self) -> float:
        return _wave(2.0, 0.03, 0.0)

    @property
    def v_current_control_integral_q(self) -> float:
        return _wave(3.0, 0.2, 1.1)


class _MockAxis:
    def __init__(self, calibrated: bool = True) -> None:
        self.error = 0
        self.requested_state = 1
        self.current_state = 1
        self.current_control = _CurrentControl()
        self.motor = types.SimpleNamespace(
            is_calibrated=calibrated,
            current_control=self.current_control,
            config=_Config(current_lim=10.0, current_control_bandwidth=1000.0, torque_lim=float('inf'), requested_current_range=60.0),
            fet_thermistor=self,  # exposes .temperature below
        )
        self.controller = types.SimpleNamespace(
            input_torque=0.0,
            input_vel=0.0,
            input_pos=0.0,
            config=_Config(
                control_mode=2,
                input_mode=1,
                pos_gain=20.0,
                vel_gain=0.16,
                vel_integrator_gain=0.32,
                vel_differentiator_gain=0.0,
                vel_limit=10.0,
                inertia=0.0,
                vel_ramp_rate=10.0,
                input_filter_bandwidth=2.0,
                torque_ramp_rate=0.01,
                mirror_ratio=1.0,
                axis_to_mirror=255,
            ),
        )
        self.encoder = _Encoder()
        self.trap_traj = types.SimpleNamespace(config=_Config(vel_limit=2.0, accel_limit=0.5, decel_limit=0.5))

    # telemetry (read-only, animated)
    @property
    def temperature(self) -> float:
        return _wave(20.0, 4.0, 32.0)

    def clear_errors(self) -> None:
        self.error = 0


class _Encoder:
    """Encoder with a settable config and animated position/velocity estimates."""

    def __init__(self) -> None:
        self.config = _Config(bandwidth=1000.0)

    @property
    def pos_estimate(self) -> float:
        return _wave(4.0, 1.0)

    @property
    def vel_estimate(self) -> float:
        return _wave(4.0, 2.0)


def make_mock_odrive(serial: int = 0x208E39855253, two_axes: bool = True):
    """Return a fake ODrive device exposing everything ``controls()`` reads."""
    ax0 = _MockAxis(calibrated=True)
    ax1 = _MockAxis(calibrated=two_axes)

    class _Dev:
        serial_number = serial
        hw_version_major, hw_version_minor, hw_version_variant = 3, 6, 56
        fw_version_major, fw_version_minor, fw_version_revision = 0, 5, 6
        fw_version_unreleased = 1

        def __init__(self) -> None:
            self.axis0 = ax0
            self.axis1 = ax1

        @property
        def vbus_voltage(self) -> float:
            return _wave(8.0, 0.3, 24.0)

        def save_configuration(self) -> None:
            pass

        def reboot(self) -> None:
            pass

        def clear_errors(self) -> None:  # present on 0.6.x firmware; drives the hasattr() True branch
            pass

    return _Dev()


def build_mock_page() -> None:
    """Build the themed dev/test page (header + control panel) for one mock device.

    Shared by ``tools/run_mock.py`` and ``tests/app_under_test.py`` so the dev runner,
    the screenshots and the render tests all show byte-identical chrome. Imports are
    local because ``controls``/``theme`` live under ``src`` (on the path at call time)
    and ``controls`` requires ``install_odrive_stub()`` to have run first.
    """
    from nicegui import ui

    from controls import controls
    from theme import apply_theme

    apply_theme()
    ui.markdown('## ODrive GUI')
    with ui.row().classes('gap-4 items-stretch'):
        controls(make_mock_odrive())


def install_odrive_stub() -> None:
    """Register fake ``odrive`` submodules so the app imports without hardware."""
    if 'odrive' in sys.modules and getattr(sys.modules['odrive'], '_is_mock', False):
        return
    odrive = types.ModuleType('odrive')
    odrive._is_mock = True  # type: ignore[attr-defined]
    pyfibre = types.ModuleType('odrive.pyfibre')
    fibre = types.ModuleType('odrive.pyfibre.fibre')
    fibre.libfibre = types.SimpleNamespace(EmptyInterface=type('EmptyInterface', (), {}))
    pyfibre.fibre = fibre
    utils = types.ModuleType('odrive.utils')
    utils.dump_errors = lambda odrv, clear=False: None  # type: ignore[attr-defined]
    odrive.pyfibre = pyfibre  # type: ignore[attr-defined]
    odrive.utils = utils  # type: ignore[attr-defined]
    sys.modules.update(
        {
            'odrive': odrive,
            'odrive.pyfibre': pyfibre,
            'odrive.pyfibre.fibre': fibre,
            'odrive.utils': utils,
        }
    )
