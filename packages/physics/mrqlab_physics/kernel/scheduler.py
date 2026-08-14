from bisect import bisect_right

import numpy as np
from mrqlab_sequence import SequenceIR

from ..models import EngineOptions
from ..ops.types import AdcSample, GradInterval, Operator, Relax, RfOp, Shift
from .units import deg_to_rad


def _value_at(events, t: float, default: float = 0.0) -> float:
    times = [event.time for event in events]
    index = bisect_right(times, t) - 1
    return default if index < 0 else float(events[index].value)


def _adc_sample_times(sequence: SequenceIR, dwell: float) -> tuple[float, ...]:
    samples: list[float] = []
    active: float | None = None
    for event in sequence.channel("adc_gate"):
        if event.value and active is None:
            active = event.time
        elif not event.value and active is not None:
            count = max(0, int(np.ceil((event.time - active) / dwell - 1e-12)))
            samples.extend(active + index * dwell for index in range(count))
            active = None
    if active is not None:
        raise ValueError("adc_gate must close before sequence end")
    return tuple(samples)


def _metadata_shifts(sequence: SequenceIR) -> dict[float, list[Shift]]:
    shifts: dict[float, list[Shift]] = {}
    for raw in sequence.metadata.get("epg_dk_events", []):
        t = float(raw["time"])
        values = tuple(int(value) for value in raw["dk"])
        if len(values) != 3 or not 0 <= t <= sequence.duration:
            raise ValueError("each epg_dk_event requires time in range and three integer dk values")
        shifts.setdefault(t, []).append(Shift(t=t, dk=values, source="metadata"))
    return shifts


def schedule(sequence: SequenceIR, options: EngineOptions) -> tuple[Operator, ...]:
    rf_amp = sequence.channel("rf_amp")
    rf_phase = sequence.channel("rf_phase")
    gradients = tuple(sequence.channel(name) for name in ("gx", "gy", "gz"))
    nco_frequency = sequence.channel("nco_freq")
    nco_phase = sequence.channel("nco_phase")
    adc_times = _adc_sample_times(sequence, options.dwell_time)
    explicit_shifts = _metadata_shifts(sequence)
    event_times = {
        0.0,
        sequence.duration,
        *adc_times,
        *explicit_shifts.keys(),
        *(event.time for channel in sequence.channels for event in channel.events),
    }
    knots = sorted(event_times)
    rf_at: dict[float, list[float]] = {}
    for event in rf_amp:
        rf_at.setdefault(event.time, []).append(float(event.value))
    adc_set = set(adc_times)
    operators: list[Operator] = []
    use_area_fallback = not explicit_shifts

    for index, t in enumerate(knots):
        for alpha_deg in rf_at.get(t, []):
            operators.append(RfOp(t, deg_to_rad(alpha_deg), deg_to_rad(_value_at(rf_phase, t))))
        operators.extend(explicit_shifts.get(t, ()))
        if t in adc_set:
            operators.append(AdcSample(t, _value_at(nco_frequency, t), deg_to_rad(_value_at(nco_phase, t))))
        if index == len(knots) - 1:
            continue
        next_t = knots[index + 1]
        dt = next_t - t
        gradient = tuple(_value_at(channel, t) for channel in gradients)
        operators.append(Relax(t, dt))
        operators.append(GradInterval(t, dt, gradient))
        if use_area_fallback:
            dk = tuple(int(np.rint(value * dt / options.epg_dk_scale)) for value in gradient)
            if dk != (0, 0, 0):
                operators.append(Shift(next_t, dk, "gradient_area"))
    return tuple(operators)
