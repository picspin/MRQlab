from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .executable_sequence import AdcWindow, ExecutableSequenceIR


class ExportState(StrEnum):
    SIMULATION_VALID = "SIMULATION_VALID"
    IR_VALID = "IR_VALID"
    EXPORTABLE = "EXPORTABLE"
    TARGET_PROFILE_VALID = "TARGET_PROFILE_VALID"
    HARDWARE_REVIEW_REQUIRED = "HARDWARE_REVIEW_REQUIRED"


class ExportModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class ExportShape(ExportModel):
    id: str
    kind: Literal["rf", "gradient"]
    samples: tuple[float, ...]
    phase: tuple[float, ...] = ()
    raster_s: float
    axis: Literal["gx", "gy", "gz"] | None = None
    carrier_offset_hz: float | None = None


class ExportBlock(ExportModel):
    id: str
    start_s: float
    duration_s: float
    rf_shape_id: str | None = None
    gradient_shape_ids: tuple[str, ...] = ()
    adc: AdcWindow | None = None


class ExportIR(ExportModel):
    schema_version: Literal["1.0"] = "1.0"
    source_logical_sequence_id: str
    scanner_profile: str
    shapes: tuple[ExportShape, ...]
    blocks: tuple[ExportBlock, ...]


class ExportAssessment(ExportModel):
    states: tuple[ExportState, ...]
    messages: tuple[str, ...]


def _shape_id(
    kind: str,
    samples: tuple[float, ...],
    phase: tuple[float, ...],
    raster_s: float,
    semantic_discriminator: str | float | None = None,
) -> str:
    raw = json.dumps(
        [kind, samples, phase, raster_s, semantic_discriminator],
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def build_export_ir(sequence: ExecutableSequenceIR) -> ExportIR:
    shapes = {}
    blocks = []
    for block in sequence.blocks:
        rf_id = None
        if block.rf is not None:
            rf_id = _shape_id(
                "rf",
                block.rf.samples_ut,
                block.rf.phase_rad,
                block.rf.raster_s,
                block.rf.carrier_offset_hz,
            )
            shapes[rf_id] = ExportShape(
                id=rf_id,
                kind="rf",
                samples=block.rf.samples_ut,
                phase=block.rf.phase_rad,
                raster_s=block.rf.raster_s,
                carrier_offset_hz=block.rf.carrier_offset_hz,
            )
        gradient_ids = []
        for gradient in block.gradients:
            shape_id = _shape_id(
                "gradient",
                gradient.samples_mt_m,
                (),
                gradient.raster_s,
                gradient.axis,
            )
            shapes[shape_id] = ExportShape(
                id=shape_id,
                kind="gradient",
                samples=gradient.samples_mt_m,
                raster_s=gradient.raster_s,
                axis=gradient.axis,
            )
            gradient_ids.append(shape_id)
        blocks.append(
            ExportBlock(
                id=block.id,
                start_s=block.start_s,
                duration_s=block.duration_s,
                rf_shape_id=rf_id,
                gradient_shape_ids=tuple(gradient_ids),
                adc=block.adc,
            )
        )
    return ExportIR(
        source_logical_sequence_id=sequence.logical_sequence_id,
        scanner_profile=sequence.scanner_profile,
        shapes=tuple(shapes[key] for key in sorted(shapes)),
        blocks=tuple(blocks),
    )


def assess_export(
    export_ir: ExportIR, *, target_profile_valid: bool
) -> ExportAssessment:
    states = [
        ExportState.SIMULATION_VALID,
        ExportState.IR_VALID,
        ExportState.EXPORTABLE,
    ]
    messages = ["simulation and IR validation do not imply scanner safety"]
    if target_profile_valid:
        states.extend(
            (
                ExportState.TARGET_PROFILE_VALID,
                ExportState.HARDWARE_REVIEW_REQUIRED,
            )
        )
        messages.append("independent hardware review remains required")
    return ExportAssessment(states=tuple(states), messages=tuple(messages))
