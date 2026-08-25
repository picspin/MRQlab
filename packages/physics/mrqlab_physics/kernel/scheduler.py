from bisect import bisect_right
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from heapq import merge
from math import ceil, isfinite
from numbers import Real

import numpy as np
from mrqlab_sequence import SequenceIR

from ..models import EngineOptions
from ..ops.types import AdcSample, GradInterval, Operator, Relax, RfOp, Shift
from .units import DEFAULT_FOV_M, GAMMA_BAR_HZ_T, deg_to_rad


MAX_SEQUENCE_EVENTS = 100_000
MAX_ADC_SAMPLES = 250_000


@dataclass(frozen=True, slots=True)
class _EventSeries:
    times: tuple[float, ...]
    values: tuple[float, ...]

    @classmethod
    def from_events(cls, events) -> "_EventSeries":
        return cls(
            tuple(event.time for event in events),
            tuple(float(event.value) for event in events),
        )

    def value_at(self, t: float, default: float = 0.0) -> float:
        index = bisect_right(self.times, t) - 1
        return default if index < 0 else self.values[index]


@dataclass(frozen=True, slots=True)
class _AdcWindow:
    start: float
    count: int


@dataclass(frozen=True, slots=True)
class SchedulePlan:
    adc_windows: tuple[_AdcWindow, ...]
    adc_sample_count: int
    operator_count: int
    explicit_shifts: dict[float, tuple[Shift, ...]]
    series: dict[str, _EventSeries]
    base_times: tuple[float, ...]


def _value_at(series: _EventSeries, t: float, default: float = 0.0) -> float:
    return series.value_at(t, default)


def _window_sample_count(start: float, end: float, dwell: float) -> int:
    ratio = (end - start) / dwell
    if not isfinite(ratio):
        raise ValueError("ADC sample limit exceeded by non-finite dwell count")
    return max(0, ceil(ratio - 1e-12))


def _adc_windows(sequence: SequenceIR, dwell: float) -> tuple[tuple[_AdcWindow, ...], int]:
    windows: list[_AdcWindow] = []
    active: float | None = None
    sample_count = 0
    for event in sequence.channel("adc_gate"):
        if event.value not in (0.0, 1.0):
            raise ValueError("adc_gate values must be 0 or 1")
        if event.value == 1.0:
            if active is not None:
                raise ValueError("adc_gate cannot reopen before it closes")
            active = event.time
        elif active is not None:
            count = _window_sample_count(active, event.time, dwell)
            sample_count += count
            if sample_count > MAX_ADC_SAMPLES:
                raise ValueError(
                    f"ADC sample limit {MAX_ADC_SAMPLES} exceeded by {sample_count} samples"
                )
            windows.append(_AdcWindow(active, count))
            active = None
    if active is not None:
        raise ValueError("adc_gate must close before sequence end")
    return tuple(windows), sample_count


def _iter_adc_sample_times(
    windows: Sequence[_AdcWindow], dwell: float
) -> Iterable[float]:
    for window in windows:
        for index in range(window.count):
            yield window.start + index * dwell


def _metadata_shifts(sequence: SequenceIR) -> dict[float, tuple[Shift, ...]]:
    raw_shifts = sequence.metadata.get("epg_dk_events", [])
    if not isinstance(raw_shifts, (list, tuple)):
        raise ValueError("epg_dk_events must be a list of epg_dk_event mappings")
    shifts: dict[float, list[Shift]] = {}
    for raw in raw_shifts:
        if not isinstance(raw, Mapping) or "time" not in raw or "dk" not in raw:
            raise ValueError(
                "each epg_dk_event requires time in range and three integer dk values"
            )
        raw_time = raw["time"]
        raw_values = raw["dk"]
        if (
            not isinstance(raw_time, Real)
            or isinstance(raw_time, bool)
            or not np.isfinite(raw_time)
            or not isinstance(raw_values, (list, tuple))
            or len(raw_values) != 3
        ):
            raise ValueError(
                "each epg_dk_event requires time in range and three integer dk values"
            )
        t = float(raw_time)
        if (
            not 0 <= t <= sequence.duration
            or any(
                not isinstance(value, Real)
                or isinstance(value, bool)
                or not np.isfinite(value)
                or not float(value).is_integer()
                for value in raw_values
            )
        ):
            raise ValueError(
                "each epg_dk_event requires time in range and three integer dk values"
            )
        values = tuple(int(value) for value in raw_values)
        shifts.setdefault(t, []).append(Shift(t=t, dk=values, source="metadata"))
    return {t: tuple(values) for t, values in shifts.items()}


def _metadata_rf_events(sequence: SequenceIR) -> tuple[dict[str, float], ...]:
    raw_events = sequence.metadata.get("rf_events", [])
    if not isinstance(raw_events, (list, tuple)):
        raise ValueError("rf_events must be a list of mappings")
    events = []
    for raw in raw_events:
        if not isinstance(raw, Mapping) or "t" not in raw:
            raise ValueError("each rf_event requires a finite t")
        values = {}
        for name, default in (("t", None), ("duration_s", 0.0), ("offset_hz", 0.0)):
            value = raw.get(name, default)
            if not isinstance(value, Real) or isinstance(value, bool) or not np.isfinite(value):
                raise ValueError(f"rf_event {name} must be a finite real number")
            values[name] = float(value)
        b1 = raw.get("b1_ut")
        if b1 is not None and (
            not isinstance(b1, Real) or isinstance(b1, bool) or not np.isfinite(b1)
        ):
            raise ValueError("rf_event b1_ut must be a finite real number")
        if values["duration_s"] < 0:
            raise ValueError("rf_event duration_s must be non-negative")
        if values["duration_s"] > 0 and (b1 is None or b1 <= 0):
            raise ValueError("rf_event with positive duration_s requires positive b1_ut")
        values["b1_ut"] = None if b1 is None else float(b1)
        events.append(values)
    return tuple(events)


def _iter_knots(
    base_times: Sequence[float], windows: Sequence[_AdcWindow], dwell: float
) -> Iterable[float]:
    previous: float | None = None
    for t in merge(base_times, _iter_adc_sample_times(windows, dwell)):
        if previous is None or t != previous:
            yield t
            previous = t


def _fallback_shift(
    t: float,
    next_t: float,
    gradients: tuple[_EventSeries, _EventSeries, _EventSeries],
    scale: float,
    *,
    units: str = "teaching",
    fov_m: float = DEFAULT_FOV_M,
) -> Shift | None:
    dt = next_t - t
    gradient = tuple(_value_at(channel, t) for channel in gradients)
    if units == "mt_m":
        scaled_area = tuple(value * 1e-3 * GAMMA_BAR_HZ_T * dt * fov_m for value in gradient)
    elif units == "teaching":
        scaled_area = tuple(value * dt / scale for value in gradient)
    else:
        raise ValueError("gradient_units must be 'teaching' or 'mt_m'")
    if not all(np.isfinite(value) for value in scaled_area):
        raise ValueError("gradient area must remain finite during scheduling")
    dk = tuple(int(np.rint(value)) for value in scaled_area)
    return None if dk == (0, 0, 0) else Shift(next_t, dk, "gradient_area")


def preflight_schedule(
    sequence: SequenceIR,
    options: EngineOptions,
    *,
    max_operators: int | None = None,
) -> SchedulePlan:
    event_count = sum(len(channel.events) for channel in sequence.channels)
    if event_count > MAX_SEQUENCE_EVENTS:
        raise ValueError(
            f"sequence event limit {MAX_SEQUENCE_EVENTS} exceeded by {event_count} events"
        )

    series = {
        name: _EventSeries.from_events(sequence.channel(name))
        for name in (
            "rf_amp",
            "rf_phase",
            "gx",
            "gy",
            "gz",
            "nco_freq",
            "nco_phase",
        )
    }
    windows, adc_sample_count = _adc_windows(sequence, options.dwell_time)
    explicit_shifts = _metadata_shifts(sequence)
    explicit_shift_count = sum(len(values) for values in explicit_shifts.values())
    rf_count = len(sequence.channel("rf_amp"))

    minimum_operators = rf_count + explicit_shift_count + 3 * adc_sample_count
    if max_operators is not None and minimum_operators > max_operators:
        raise ValueError(
            "estimated work requires at least "
            f"{minimum_operators} operators, exceeding preflight operator limit "
            f"{max_operators}"
        )

    base_times = tuple(
        sorted(
            {
                0.0,
                sequence.duration,
                *explicit_shifts.keys(),
                *(
                    event.time
                    for channel in sequence.channels
                    for event in channel.events
                ),
            }
        )
    )
    gradients = (series["gx"], series["gy"], series["gz"])
    units = sequence.metadata.get("gradient_units", "teaching")
    fov_m = float(sequence.metadata.get("fov_m", DEFAULT_FOV_M))
    if not np.isfinite(fov_m) or fov_m <= 0:
        raise ValueError("fov_m must be finite and positive")
    knot_count = 0
    fallback_shift_count = 0
    previous: float | None = None
    for t in _iter_knots(base_times, windows, options.dwell_time):
        if previous is not None and not explicit_shifts:
            fallback_shift_count += _fallback_shift(
                previous, t, gradients, options.epg_dk_scale, units=units, fov_m=fov_m
            ) is not None
        previous = t
        knot_count += 1

    interval_count = max(0, knot_count - 1)
    operator_count = (
        rf_count
        + explicit_shift_count
        + adc_sample_count
        + 2 * interval_count
        + fallback_shift_count
    )
    if max_operators is not None and operator_count > max_operators:
        raise ValueError(
            f"estimated work requires {operator_count} operators, exceeding "
            f"preflight operator limit {max_operators}"
        )
    return SchedulePlan(
        adc_windows=windows,
        adc_sample_count=adc_sample_count,
        operator_count=operator_count,
        explicit_shifts=explicit_shifts,
        series=series,
        base_times=base_times,
    )


def schedule(
    sequence: SequenceIR,
    options: EngineOptions,
    plan: SchedulePlan | None = None,
) -> tuple[Operator, ...]:
    plan = plan or preflight_schedule(sequence, options)
    knots = list(_iter_knots(plan.base_times, plan.adc_windows, options.dwell_time))
    adc_times = set(_iter_adc_sample_times(plan.adc_windows, options.dwell_time))
    gradients = (plan.series["gx"], plan.series["gy"], plan.series["gz"])
    units = sequence.metadata.get("gradient_units", "teaching")
    fov_m = float(sequence.metadata.get("fov_m", DEFAULT_FOV_M))
    rf_at: dict[float, list[float]] = {}
    rf_events = _metadata_rf_events(sequence)
    for event in sequence.channel("rf_amp"):
        rf_at.setdefault(event.time, []).append(float(event.value))

    operators: list[Operator] = []
    for index, t in enumerate(knots):
        for alpha_deg in rf_at.get(t, []):
            declared = next((event for event in rf_events if abs(t - event["t"]) <= 1e-12), None)
            operators.append(
                RfOp(
                    t,
                    deg_to_rad(alpha_deg),
                    deg_to_rad(_value_at(plan.series["rf_phase"], t)),
                    duration_s=0.0 if declared is None else declared["duration_s"],
                    offset_hz=0.0 if declared is None else declared["offset_hz"],
                    b1_ut=None if declared is None else declared["b1_ut"],
                )
            )
        operators.extend(plan.explicit_shifts.get(t, ()))
        if index > 0 and not plan.explicit_shifts:
            fallback = _fallback_shift(
                knots[index - 1], t, gradients, options.epg_dk_scale, units=units, fov_m=fov_m
            )
            if fallback is not None:
                operators.append(fallback)
        if t in adc_times:
            operators.append(
                AdcSample(
                    t,
                    _value_at(plan.series["nco_freq"], t),
                    deg_to_rad(_value_at(plan.series["nco_phase"], t)),
                )
            )
        if index == len(knots) - 1:
            continue
        next_t = knots[index + 1]
        dt = next_t - t
        gradient = tuple(_value_at(channel, t) for channel in gradients)
        operators.append(Relax(t, dt))
        operators.append(GradInterval(t, dt, gradient))

    if len(operators) != plan.operator_count:
        raise RuntimeError("scheduler materialization disagrees with arithmetic preflight")
    return tuple(operators)
