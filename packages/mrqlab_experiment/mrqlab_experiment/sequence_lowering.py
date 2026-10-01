from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from .clinical import ScannerProfile
from .executable_sequence import (
    ExecutableBlock,
    ExecutableSequenceIR,
    LogicalSequenceIR,
)


def _quantize(value: float, raster: float) -> float:
    ticks = (Decimal(str(value)) / Decimal(str(raster))).quantize(
        Decimal("1"), rounding=ROUND_HALF_UP
    )
    return float(ticks * Decimal(str(raster)))


def _exact_multiple(value: float, raster: float, tolerance: float = 1e-12) -> bool:
    return abs(value - _quantize(value, raster)) <= tolerance


def lower_sequence(
    logical: LogicalSequenceIR, profile: ScannerProfile
) -> ExecutableSequenceIR:
    blocks = []
    adjustments = []
    rf_guard_until = 0.0
    for block in sorted(logical.blocks, key=lambda item: (item.start_s, item.id)):
        raster = (
            profile.rf_raster_s
            if block.rf is not None
            else profile.gradient_raster_s
        )
        start = _quantize(block.start_s, raster)
        if start != block.start_s:
            adjustments.append(f"{block.id}.start_s: {block.start_s:g} -> {start:g}")

        durations = []
        if block.rf is not None:
            if not _exact_multiple(block.rf.raster_s, profile.rf_raster_s):
                raise ValueError("RF raster must be an exact rf_raster_s multiple")
            durations.append(len(block.rf.samples_ut) * block.rf.raster_s)
        for gradient in block.gradients:
            if not _exact_multiple(gradient.raster_s, profile.gradient_raster_s):
                raise ValueError(
                    "gradient raster must be an exact gradient_raster_s multiple"
                )
            durations.append(len(gradient.samples_mt_m) * gradient.raster_s)
        if block.adc is not None:
            if not _exact_multiple(block.adc.dwell_s, profile.adc_raster_s):
                raise ValueError("ADC dwell must be an exact adc_raster_s multiple")
            adc_start = start + block.adc.delay_s
            if adc_start < rf_guard_until:
                raise ValueError(
                    "ADC begins before RF dead time and ringdown complete"
                )
            durations.append(
                block.adc.delay_s
                + block.adc.dwell_s * block.adc.sample_count
                + profile.adc_dead_time_s
            )
        duration = max(durations)
        if start + duration > logical.duration_s:
            raise ValueError(f"block {block.id!r} exceeds logical sequence duration")
        if block.rf is not None:
            rf_guard_until = (
                start
                + duration
                + profile.rf_dead_time_s
                + profile.rf_ringdown_time_s
            )
        blocks.append(
            ExecutableBlock(
                id=block.id,
                start_s=start,
                duration_s=duration,
                rf=block.rf,
                gradients=block.gradients,
                adc=block.adc,
            )
        )
    return ExecutableSequenceIR(
        logical_sequence_id=logical.id,
        scanner_profile=f"{profile.id}@{profile.version}",
        duration_s=_quantize(logical.duration_s, profile.gradient_raster_s),
        blocks=tuple(blocks),
        timing_adjustments=tuple(adjustments),
    )
