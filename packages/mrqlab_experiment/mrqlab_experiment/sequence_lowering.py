from __future__ import annotations

from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from functools import reduce
from math import gcd

from .clinical import ScannerProfile
from .executable_sequence import ExecutableBlock, ExecutableSequenceIR, LogicalSequenceIR


def _quantize(value: float, raster: float) -> float:
    ticks = (Decimal(str(value)) / Decimal(str(raster))).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return float(ticks * Decimal(str(raster)))


def _quantize_ceil(value: float, raster: float) -> float:
    ticks = (Decimal(str(value)) / Decimal(str(raster))).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return float(ticks * Decimal(str(raster)))


def _exact_multiple(value: float, raster: float, tolerance: float = 1e-12) -> bool:
    return abs(value - _quantize(value, raster)) <= tolerance


def _raster_lcm_s(rasters: list[float]) -> float:
    if not rasters:
        return 1e-6
    dec_rasters = [Decimal(str(r)) for r in rasters]
    max_places = max(-d.as_tuple().exponent for d in dec_rasters)
    scale = 10 ** max_places
    integers = [int(d * scale) for d in dec_rasters]
    lcm_int = reduce(lambda a, b: (a * b) // gcd(a, b), integers)
    return float(Decimal(lcm_int) / Decimal(scale))


def _block_raster(block, profile: ScannerProfile) -> float:
    rasters = []
    if block.rf is not None:
        rasters.append(profile.rf_raster_s)
    if block.gradients:
        rasters.append(profile.gradient_raster_s)
    if block.adc is not None:
        rasters.append(profile.adc_raster_s)
    return _raster_lcm_s(rasters)


def _validate_gradient_boundaries(blocks, profile: ScannerProfile) -> None:
    """Check nominal sampled slew at joins and at implicit zero-valued gaps.

    Samples are held for their raster. At an adjacent block boundary, the
    previous last sample and next first sample are separated by the previous
    waveform's raster. An idle channel is zero. These finite-difference checks
    are not a continuous-time gradient or hardware safety model.
    """
    by_axis = {axis: [] for axis in ("gx", "gy", "gz")}
    for block in blocks:
        for gradient in block.gradients:
            start = Decimal(str(block.start_s))
            raster = Decimal(str(gradient.raster_s))
            end = start + len(gradient.samples_mt_m) * raster
            by_axis[gradient.axis].append((start, end, raster, gradient, block.id))

    def check(axis, label, first, second, interval):
        slew = abs(Decimal(str(second)) - Decimal(str(first))) / Decimal(1000) / interval
        if slew > Decimal(str(profile.max_slew_rate_t_m_s)):
            raise ValueError(
                f"gradient boundary slew rate {slew:g} T/m/s on {axis} "
                f"at {label} exceeds scanner limit {profile.max_slew_rate_t_m_s:g} T/m/s"
            )

    for axis, waveforms in by_axis.items():
        waveforms.sort(key=lambda item: (item[0], item[4]))
        for index, (start, end, raster, waveform, block_id) in enumerate(waveforms):
            previous = waveforms[index - 1] if index else None
            if previous is not None and previous[1] == start:
                check(axis, f"{previous[4]} -> {block_id}", previous[3].samples_mt_m[-1],
                      waveform.samples_mt_m[0], previous[2])
            else:
                # A later waveform enters over its idle gap; the first waveform
                # on an axis enters over the idle time from the sequence start
                # (t=0), not over its own raster. A block starting at t=0 has no
                # idle time and is checked over its raster (zero one raster
                # earlier), matching the nonzero-initial-jump check.
                gap = start - previous[1] if previous is not None else start
                check(axis, f"start of {block_id}", 0.0, waveform.samples_mt_m[0],
                      min(raster, gap) if gap > 0 else raster)
            following = waveforms[index + 1] if index + 1 < len(waveforms) else None
            if following is None or following[0] > end:
                check(axis, f"end of {block_id}", waveform.samples_mt_m[-1], 0.0, raster)


def lower_sequence(logical: LogicalSequenceIR, profile: ScannerProfile) -> ExecutableSequenceIR:
    # Pass 1: derive actual quantized executable start_s for each block, and build RF guards from THAT exact start
    block_starts: dict[str, float] = {}
    rf_guards: list[tuple[Decimal, Decimal]] = []
    channel_intervals: dict[str, list[tuple[Decimal, Decimal, str]]] = {}

    for block in logical.blocks:
        raster = _block_raster(block, profile)
        actual_start = _quantize(block.start_s, raster)
        block_starts[block.id] = actual_start
        start_decimal = Decimal(str(actual_start))
        if block.rf is not None:
            rf_end = start_decimal + len(block.rf.samples_ut) * Decimal(str(block.rf.raster_s))
            guard_end = rf_end + Decimal(str(profile.rf_dead_time_s)) + Decimal(str(profile.rf_ringdown_time_s))
            rf_guards.append((start_decimal, guard_end))
            channel_intervals.setdefault("rf", []).append((start_decimal, rf_end, block.id))
        for gradient in block.gradients:
            end = start_decimal + len(gradient.samples_mt_m) * Decimal(str(gradient.raster_s))
            channel_intervals.setdefault(gradient.axis, []).append((start_decimal, end, block.id))
        if block.adc is not None:
            adc_start = start_decimal + Decimal(str(block.adc.delay_s))
            adc_end = adc_start + Decimal(str(block.adc.dwell_s)) * block.adc.sample_count
            channel_intervals.setdefault("adc", []).append((adc_start, adc_end, block.id))

    # Distinct channels may overlap, but two blocks cannot drive the same
    # physical channel at the same time. Check quantized, not logical, times.
    for channel, intervals in channel_intervals.items():
        ordered = sorted(intervals)
        for previous, current in zip(ordered, ordered[1:]):
            if current[0] < previous[1]:
                raise ValueError(f"overlapping {channel} channel in blocks {previous[2]!r} and {current[2]!r}")

    blocks = []
    adjustments = []
    max_block_end = 0.0

    for block in sorted(logical.blocks, key=lambda item: (item.start_s, item.id)):
        start = block_starts[block.id]
        if start != block.start_s:
            adjustments.append(f"{block.id}.start_s: {block.start_s:g} -> {start:g}")

        durations = []
        if block.rf is not None:
            if not _exact_multiple(block.rf.raster_s, profile.rf_raster_s):
                raise ValueError("RF raster must be an exact rf_raster_s multiple")
            durations.append(len(block.rf.samples_ut) * block.rf.raster_s)

        for gradient in block.gradients:
            if not _exact_multiple(gradient.raster_s, profile.gradient_raster_s):
                raise ValueError("gradient raster must be an exact gradient_raster_s multiple")
            for sample in gradient.samples_mt_m:
                if abs(sample) > profile.max_gradient_mt_m:
                    raise ValueError(f"gradient amplitude {sample:g} mT/m exceeds scanner limit {profile.max_gradient_mt_m:g} mT/m")
            for i in range(len(gradient.samples_mt_m) - 1):
                delta_mt_m = abs(Decimal(str(gradient.samples_mt_m[i + 1])) - Decimal(str(gradient.samples_mt_m[i])))
                slew = delta_mt_m / Decimal(1000) / Decimal(str(gradient.raster_s))
                if slew > Decimal(str(profile.max_slew_rate_t_m_s)):
                    raise ValueError(f"gradient slew rate {slew:g} T/m/s exceeds scanner limit {profile.max_slew_rate_t_m_s:g} T/m/s")
            durations.append(len(gradient.samples_mt_m) * gradient.raster_s)

        if block.adc is not None:
            if not _exact_multiple(block.adc.dwell_s, profile.adc_raster_s):
                raise ValueError("ADC dwell must be an exact adc_raster_s multiple")
            if not _exact_multiple(block.adc.delay_s, profile.adc_raster_s):
                raise ValueError("ADC delay must be an exact adc_raster_s multiple")
            adc_start = Decimal(str(start)) + Decimal(str(block.adc.delay_s))
            adc_end = adc_start + Decimal(str(block.adc.dwell_s)) * block.adc.sample_count
            for rf_start, rf_end in rf_guards:
                if max(adc_start, rf_start) < min(adc_end, rf_end):
                    raise ValueError("ADC acquisition overlaps with RF pulse, dead time, or ringdown")
            durations.append(block.adc.delay_s + block.adc.dwell_s * block.adc.sample_count + profile.adc_dead_time_s)

        duration = max(durations)
        if start + duration > logical.duration_s:
            raise ValueError(f"block {block.id!r} exceeds logical sequence duration")

        max_block_end = max(max_block_end, start + duration)
        blocks.append(ExecutableBlock(
            id=block.id, start_s=start, duration_s=duration,
            rf=block.rf, gradients=block.gradients, adc=block.adc,
        ))

    _validate_gradient_boundaries(blocks, profile)

    seq_dur = _quantize_ceil(logical.duration_s, profile.gradient_raster_s)
    if seq_dur < max_block_end:
        raise ValueError("quantized sequence duration cannot be smaller than block end time")

    return ExecutableSequenceIR(
        logical_sequence_id=logical.id,
        scanner_profile=f"{profile.id}@{profile.version}",
        duration_s=seq_dur,
        blocks=tuple(blocks), timing_adjustments=tuple(adjustments),
    )
