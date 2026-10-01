from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .executable_sequence import AdcWindow, ExecutableSequenceIR


class ExportState(StrEnum):
    SIMULATION_VALID = "SIMULATION_VALID"
    IR_VALID = "IR_VALID"
    EXPORTABLE = "EXPORTABLE"
    TARGET_PROFILE_VALID = "TARGET_PROFILE_VALID"
    HARDWARE_REVIEW_REQUIRED = "HARDWARE_REVIEW_REQUIRED"


class ExportModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)


class ExportShape(ExportModel):
    id: str = Field(min_length=1)
    kind: Literal["rf", "gradient"]
    samples: tuple[float, ...] = Field(min_length=1)
    phase: tuple[float, ...] = ()
    raster_s: float = Field(gt=0)
    axis: Literal["gx", "gy", "gz"] | None = None
    carrier_offset_hz: float | None = None


class ExportBlock(ExportModel):
    id: str = Field(min_length=1)
    start_s: float = Field(ge=0)
    duration_s: float = Field(gt=0)
    rf_shape_id: str | None = None
    gradient_shape_ids: tuple[str, ...] = ()
    adc: AdcWindow | None = None


class ExportIR(ExportModel):
    schema_version: Literal["1.0"] = "1.0"
    source_logical_sequence_id: str = Field(min_length=1)
    scanner_profile: str = Field(min_length=1)
    duration_s: float = Field(gt=0)
    shapes: tuple[ExportShape, ...]
    blocks: tuple[ExportBlock, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def references_known_shapes(self):
        shape_ids = [shape.id for shape in self.shapes]
        if len(shape_ids) != len(set(shape_ids)):
            raise ValueError("export shape ids must be unique")
        known = set(shape_ids)
        block_ids = [block.id for block in self.blocks]
        if len(block_ids) != len(set(block_ids)):
            raise ValueError("export block ids must be unique")
        for block in self.blocks:
            references = (*block.gradient_shape_ids,)
            if block.rf_shape_id is not None:
                references = (block.rf_shape_id, *references)
            if any(reference not in known for reference in references):
                raise ValueError("export block references unknown shape")
        return self


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
        duration_s=sequence.duration_s,
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
