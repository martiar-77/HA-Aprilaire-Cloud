"""Pure helpers for encoding Aprilaire heat/cool setpoints.

The cloud API speaks Celsius, but the thermostat works in whole degrees
Fahrenheit. Writes that don't land exactly on the 2-decimal Celsius value of a
whole degF (e.g. 67F -> 19.44, 72F -> 22.22) are accepted by the API and then
silently dropped by the device. Heat and cool must also be sent together and
respect the app's limits and 3 degF minimum deadband (the app pushes the
companion setpoint rather than rejecting the change).
"""

from __future__ import annotations

import math

HEAT_MIN_F = 40
HEAT_MAX_F = 90
COOL_MIN_F = 50
COOL_MAX_F = 93
DEADBAND_F = 3


def c_to_whole_f(celsius: float) -> int:
    """Nearest whole degF for a Celsius value (half rounds up)."""
    return int(math.floor(celsius * 9 / 5 + 32 + 0.5 + 1e-9))


def f_to_c(fahrenheit: int) -> float:
    """2-decimal Celsius encoding of a whole degF value."""
    return round((fahrenheit - 32) * 5 / 9, 2)


def snap_c(celsius: float) -> float:
    """Snap a Celsius value to the encoding of the nearest whole degF."""
    return f_to_c(c_to_whole_f(celsius))


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def resolve_setpoints(
    current_heat_c: float | None,
    current_cool_c: float | None,
    heat_c: float | None = None,
    cool_c: float | None = None,
) -> dict[str, float]:
    """Return the full {'heat', 'cool'} payload (Celsius, snapped) to send.

    ``heat_c`` / ``cool_c`` are the requested values (None = unchanged). The
    missing companion is filled from the current settings. Values are clamped
    to the app limits and the deadband is enforced by pushing whichever
    setpoint the user did *not* move (if both moved, cool is pushed).
    """
    req_heat = heat_c if heat_c is not None else current_heat_c
    req_cool = cool_c if cool_c is not None else current_cool_c
    if req_heat is None or req_cool is None:
        raise ValueError("both heat and cool setpoints are required")

    heat = _clamp(c_to_whole_f(req_heat), HEAT_MIN_F, HEAT_MAX_F)
    cool = _clamp(c_to_whole_f(req_cool), COOL_MIN_F, COOL_MAX_F)

    if cool - heat < DEADBAND_F:
        if cool_c is not None and heat_c is None:
            # User moved cool down: push heat down.
            heat = cool - DEADBAND_F
            if heat < HEAT_MIN_F:
                heat = HEAT_MIN_F
                cool = heat + DEADBAND_F
        else:
            # User moved heat (or both): push cool up.
            cool = heat + DEADBAND_F
            if cool > COOL_MAX_F:
                cool = COOL_MAX_F
                heat = cool - DEADBAND_F

    return {"heat": f_to_c(heat), "cool": f_to_c(cool)}
