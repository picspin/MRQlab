from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SequenceModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def _finite(values: tuple[float, ...], label: str) -> tuple[float, ...]:
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{label} samples must be finite")
    return values


class RfWaveform(SequenceModel):
    samples_ut: tuple[float, ...]
    phase_rad: tuple[float, ...]
    raster_s: float = Field(gt=0)
    carrier_offset_hz: float = 0.0

    @model_validator(mode="after")
    def valid_samples(self):
        _finite(self.samples_ut, "RF amplitude")
        _finite(self.phase_rad, "RF phase")
        if not self.samples_ut or len(self.samples_ut) != len(self.phase_rad):
            raise ValueError("RF amplitude and phase sample counts must match")
        return self


class GradientWaveform(SequenceModel):
    axis: Literal["gx", "gy", "gz"]
    samples_mt_m: tuple[float, ...]
    raster_s: float = Field(gt=0)

    @model_validator(mode="after")
    def valid_samples(self):
        _finite(self.samples_mt_m, "gradient")
        if len(self.samples_mt_m) < 2:
            raise ValueError("gradient waveform requires at least two samples")
        return self


class AdcWindow(SequenceModel):
    delay_s: float = Field(ge=0)
    dwell_s: float = Field(gt=0)
    sample_count: int = Field(gt=0)
    frequency_offset_hz: float = 0.0
    phase_offset_rad: float = 0.0


class LogicalBlock(SequenceModel):
    id: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    rf: RfWaveform | None = None
    gradients: tuple[GradientWaveform, ...] = ()
    adc: AdcWindow | None = None

    @model_validator(mode="after")
    def unique_gradient_axes(self):
        axes = [gradient.axis for gradient in self.gradients]
        if len(axes) != len(set(axes)):
            raise ValueError(
                "a logical block may contain at most one waveform per gradient axis"
            )
        if self.rf is None and not self.gradients and self.adc is None:
            raise ValueError("logical block must contain RF, gradient, or ADC content")
        return self


class LogicalSequenceIR(SequenceModel):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(min_length=1)
    duration_s: float = Field(gt=0)
    blocks: tuple[LogicalBlock, ...]

    @model_validator(mode="after")
    def unique_block_ids(self):
        ids = [block.id for block in self.blocks]
        if len(ids) != len(set(ids)):
            raise ValueError("logical block ids must be unique")
        return self


class ExecutableBlock(SequenceModel):
    id: str
    start_s: float
    duration_s: float
    rf: RfWaveform | None = None
    gradients: tuple[GradientWaveform, ...] = ()
    adc: AdcWindow | None = None


class ExecutableSequenceIR(SequenceModel):
    schema_version: Literal["1.0"] = "1.0"
    logical_sequence_id: str
    scanner_profile: str
    duration_s: float
    blocks: tuple[ExecutableBlock, ...]
    timing_adjustments: tuple[str, ...] = ()
