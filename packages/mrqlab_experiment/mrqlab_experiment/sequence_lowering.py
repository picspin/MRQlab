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


def lower_sequence(logical: LogicalSequenceIR, profile: ScannerProfile) -> ExecutableSequenceIR:
    # Pass 1: derive actual quantized executable start_s for each block, and build RF guards from THAT exact start
    block_starts: dict[str, float] = {}
    rf_guards: list[tuple[float, float]] = []

    for block in logical.blocks:
        raster = _block_raster(block, profile)
        actual_start = _quantize(block.start_s, raster)
        block_starts[block.id] = actual_start
        if block.rf is not None:
            r_dur = len(block.rf.samples_ut) * block.rf.raster_s
            r_end = actual_start + r_dur + profile.rf_dead_time_s + profile.rf_ringdown_time_s
            rf_guards.append((actual_start, r_end))

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
                delta_t_m = abs(gradient.samples_mt_m[i + 1] - gradient.samples_mt_m[i]) / 1000.0
                slew = delta_t_m / gradient.raster_s
                if slew > profile.max_slew_rate_t_m_s:
                    raise ValueError(f"gradient slew rate {slew:g} T/m/s exceeds scanner limit {profile.max_slew_rate_t_m_s:g} T/m/s")
            durations.append(len(gradient.samples_mt_m) * gradient.raster_s)

        if block.adc is not None:
            if not _exact_multiple(block.adc.dwell_s, profile.adc_raster_s):
                raise ValueError("ADC dwell must be an exact adc_raster_s multiple")
            if not _exact_multiple(block.adc.delay_s, profile.adc_raster_s):
                raise ValueError("ADC delay must be an exact adc_raster_s multiple")
            adc_start = start + block.adc.delay_s
            adc_end = adc_start + block.adc.dwell_s * block.adc.sample_count
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

    seq_dur = _quantize_ceil(logical.duration_s, profile.gradient_raster_s)
    if seq_dur < max_block_end:
        raise ValueError("quantized sequence duration cannot be smaller than block end time")

    return ExecutableSequenceIR(
        logical_sequence_id=logical.id,
        scanner_profile=f"{profile.id}@{profile.version}",
        duration_s=seq_dur,
        blocks=tuple(blocks), timing_adjustments=tuple(adjustments),
    )
