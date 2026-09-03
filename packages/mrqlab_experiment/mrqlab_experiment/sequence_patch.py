from typing import Literal

from pydantic import BaseModel, Field

from mrqlab_sequence import Event, SequenceIR

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

    rf_patch: RfEventPatch | None = None
    gradient_patch: GradientEventPatch | None = None
    if channel_name == "rf_amp":
        rf_patch = RfEventPatch.model_validate(request.patch)
        PulseInspectRequest(
            duration_ms=rf_patch.duration_s * 1000,
            time_bandwidth=rf_patch.time_bandwidth,
            flip_angle_deg=rf_patch.flip_angle_deg,
            phase_deg=rf_patch.phase_deg,
        )
        overlay = rf_patch.model_dump(mode="json")
    else:
        gradient_patch = GradientEventPatch.model_validate(request.patch)
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
        overlay = gradient_patch.model_dump(mode="json")

    result = request.ir.model_copy(deep=True)
    overlays = dict(result.metadata.get("event_overlays", {}))
    overlays[f"{channel_name}:{request.event.index}"] = overlay
    result.metadata["event_overlays"] = overlays
    events = result.channel(channel_name)
    start = events[request.event.index]
    if rf_patch is not None:
        start.value = rf_patch.flip_angle_deg
        phases = result.channel("rf_phase")
        if request.event.index >= len(phases):
            raise ValueError("rf_phase event missing")
        if phases[request.event.index].time != start.time:
            raise ValueError("rf_phase event does not match rf_amp time")
        phases[request.event.index].value = rf_patch.phase_deg
        blocks = result.metadata.get("blocks")
        if isinstance(blocks, list) and blocks:
            rf_blocks = sorted(
                (block for block in blocks if isinstance(block, dict) and block.get("kind") in ("excite_sinc", "refocus_sinc")),
                key=lambda block: block.get("t0_s", 0),
            )
            if request.event.index >= len(rf_blocks):
                raise ValueError("unknown RF block for overlay index")
            params = dict(rf_blocks[request.event.index].get("params") or {})
            params.update(overlay)
            rf_blocks[request.event.index]["params"] = params
    elif gradient_patch is not None and result.metadata.get("gradient_units") == "mt_m":
        blocks = result.metadata.get("blocks")
        gradient_blocks = None
        if isinstance(blocks, list):
            gradient_blocks = sorted(
                (
                    block
                    for block in blocks
                    if isinstance(block, dict) and block.get("kind") == f"trap_{channel_name}"
                ),
                key=lambda block: block.get("t0_s", 0),
            )
            if request.event.index >= len(gradient_blocks):
                raise ValueError("unknown gradient block for overlay index")
            block_start = gradient_blocks[request.event.index].get("t0_s")
            matching_event = next(
                ((index, event) for index, event in enumerate(events) if event.time == block_start),
                None,
            )
            if matching_event is None:
                raise ValueError("gradient block start event missing")
            start_index, start = matching_event
        else:
            start_index = request.event.index
        start.value = gradient_patch.amplitude_mt_m
        new_stop = start.time + gradient_patch.duration_s
        if new_stop > result.duration:
            raise ValueError("block extends beyond requested duration")
        nxt = start_index + 1
        if nxt < len(events) and events[nxt].value == 0:
            if nxt + 1 < len(events) and new_stop > events[nxt + 1].time:
                raise ValueError(f"overlapping blocks on {channel_name}")
            events[nxt].time = new_stop
        else:
            if nxt < len(events) and new_stop > events[nxt].time:
                raise ValueError(f"overlapping blocks on {channel_name}")
            events.insert(nxt, Event(time=new_stop, value=0))
        if gradient_blocks is not None:
            params = dict(gradient_blocks[request.event.index].get("params") or {})
            params.update(overlay)
            gradient_blocks[request.event.index]["params"] = params
    return SequenceIR.model_validate(result.model_dump())
