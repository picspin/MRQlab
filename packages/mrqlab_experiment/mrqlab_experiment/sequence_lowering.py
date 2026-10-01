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
    sequence_duration = _quantize(logical.duration_s, profile.gradient_raster_s)
    for block in sorted(logical.blocks, key=lambda item: (item.start_s, item.id)):
        if block.rf is not None:
            raster = profile.rf_raster_s
        elif block.gradients:
            raster = profile.gradient_raster_s
        else:
            raster = profile.adc_raster_s
        start = _quantize(block.start_s, raster)
        if start != block.start_s:
            adjustments.append(f"{block.id}.start_s: {block.start_s:g} -> {start:g}")
        required_start_rasters = []
        if block.rf is not None:
            required_start_rasters.append(profile.rf_raster_s)
        if block.gradients:
            required_start_rasters.append(profile.gradient_raster_s)
        if block.adc is not None:
            required_start_rasters.append(profile.adc_raster_s)
        if any(not _exact_multiple(start, item) for item in required_start_rasters):
            raise ValueError("block start must align to every event raster")

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
            if max(abs(sample) for sample in gradient.samples_mt_m) > profile.max_gradient_mt_m:
                raise ValueError("gradient amplitude exceeds scanner profile limit")
            max_slew = max(
                abs(right - left) * 1e-3 / gradient.raster_s
                for left, right in zip(
                    gradient.samples_mt_m, gradient.samples_mt_m[1:]
                )
            )
            if max_slew > profile.max_slew_rate_t_m_s:
                raise ValueError("gradient slew rate exceeds scanner profile limit")
            durations.append(len(gradient.samples_mt_m) * gradient.raster_s)
        if block.adc is not None:
            if not _exact_multiple(block.adc.dwell_s, profile.adc_raster_s):
                raise ValueError("ADC dwell must be an exact adc_raster_s multiple")
            if not _exact_multiple(block.adc.delay_s, profile.adc_raster_s):
                raise ValueError("ADC delay must be an exact adc_raster_s multiple")
            adc_start = start + block.adc.delay_s
            same_block_rf_guard = rf_guard_until
            if block.rf is not None:
                same_block_rf_guard = max(
                    same_block_rf_guard,
                    start
                    + len(block.rf.samples_ut) * block.rf.raster_s
                    + profile.rf_dead_time_s
                    + profile.rf_ringdown_time_s,
                )
            if adc_start < same_block_rf_guard:
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
        if start + duration > sequence_duration:
            raise ValueError(
                f"block {block.id!r} exceeds quantized sequence duration"
            )
        if block.rf is not None:
            rf_duration = len(block.rf.samples_ut) * block.rf.raster_s
            rf_guard_until = max(
                rf_guard_until,
                start
                + rf_duration
                + profile.rf_dead_time_s
                + profile.rf_ringdown_time_s,
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
    if sequence_duration != logical.duration_s:
        adjustments.append(
            f"sequence.duration_s: {logical.duration_s:g} -> {sequence_duration:g}"
        )
    return ExecutableSequenceIR(
        logical_sequence_id=logical.id,
        scanner_profile=f"{profile.id}@{profile.version}",
        duration_s=sequence_duration,
        blocks=tuple(blocks),
        timing_adjustments=tuple(adjustments),
        rf_dead_time_s=profile.rf_dead_time_s,
        rf_ringdown_time_s=profile.rf_ringdown_time_s,
        adc_dead_time_s=profile.adc_dead_time_s,
        lowering_provenance=(
            "deterministic ROUND_HALF_UP raster quantization",
        ),
    )
