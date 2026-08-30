from typing import Literal

from pydantic import BaseModel, Field

from mrqlab_sequence import SequenceIR

from .gradient import GradientHardwareConstraints, GradientPulseSpec, validate_gradient
from .pulse_inspector import PulseInspectRequest


class EventRef(BaseModel):
    channel: Literal["rf_amp", "gx", "gy", "gz", "adc_gate"]
    index: int = Field(ge=0, strict=True)


class RfEventPatch(BaseModel):
    duration_s: float = Field(gt=0)
    time_bandwidth: float = Field(gt=0)
    flip_angle_deg: float = Field(ge=0, le=360)
    phase_deg: float


class GradientEventPatch(BaseModel):
    amplitude_mt_m: float
    duration_s: float = Field(gt=0)
    ramp_time_s: float = Field(gt=0)
    unit: Literal["mT_m"]


class SequencePatchRequest(BaseModel):
    ir: SequenceIR
    event: EventRef
    patch: dict


def patch_sequence(request: SequencePatchRequest) -> SequenceIR:
    channel_name = request.event.channel
    if channel_name == "adc_gate":
        raise ValueError("adc_gate events are read-only")

    events = request.ir.channel(channel_name)
    if request.event.index >= len(events):
        raise ValueError(f"unknown event {channel_name}:{request.event.index}")

    gradient_patch: GradientEventPatch | None = None
    if channel_name == "rf_amp":
        patch = RfEventPatch.model_validate(request.patch)
        # Reuse the pulse inspector's established pulse constraints.
        PulseInspectRequest(
            duration_ms=patch.duration_s * 1000,
            time_bandwidth=patch.time_bandwidth,
            flip_angle_deg=patch.flip_angle_deg,
            phase_deg=patch.phase_deg,
        )
    else:
        gradient_patch = GradientEventPatch.model_validate(request.patch)
        patch = gradient_patch
        validation = validate_gradient(
            GradientPulseSpec(
                amplitude_mt_m=gradient_patch.amplitude_mt_m,
                duration_ms=gradient_patch.duration_s * 1000,
                ramp_time_ms=gradient_patch.ramp_time_s * 1000,
                channel={"gx": "Gx", "gy": "Gy", "gz": "Gz"}[channel_name],
            ),
            GradientHardwareConstraints(),
        )
        if not validation.is_valid:
            raise ValueError("; ".join(validation.violations))

    result = request.ir.model_copy(deep=True)
    overlays = dict(result.metadata.get("event_overlays", {}))
    overlays[f"{channel_name}:{request.event.index}"] = patch.model_dump(mode="json")
    result.metadata["event_overlays"] = overlays
    if channel_name == "rf_amp":
        result.channel(channel_name)[request.event.index].value = patch.flip_angle_deg
    elif gradient_patch is not None and result.metadata.get("gradient_units") == "mt_m":
        result.channel(channel_name)[request.event.index].value = gradient_patch.amplitude_mt_m
    return SequenceIR.model_validate(result.model_dump())
