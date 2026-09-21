from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mrqlab_sequence import Channel, Event, SequenceIR

from mrqlab_physics.kernel.units import DEFAULT_FOV_M

from .gradient import GradientHardwareConstraints, GradientPulseSpec, validate_gradient
from .pulse_inspector import PulseInspectRequest


class RfBlockParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_s: float = Field(gt=0)
    time_bandwidth: float = Field(gt=0)
    flip_angle_deg: float = Field(ge=0, le=360)
    phase_deg: float


class GradientBlockParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amplitude_mt_m: float
    duration_s: float = Field(gt=0)
    ramp_time_s: float = Field(gt=0)
    unit: Literal["mT_m"]


class AdcBlockParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    duration_s: float = Field(gt=0)


class Block(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: Literal["excite_sinc", "refocus_sinc", "trap_gx", "trap_gy", "trap_gz", "adc_gate"]
    t0_s: float = Field(ge=0)
    params: dict


class ComposeSequenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    blocks: list[Block]
    duration_s: float | None = Field(default=None, gt=0)


def compose_sequence(request: ComposeSequenceRequest) -> SequenceIR:
    channels = {name: [] for name in ("rf_amp", "rf_phase", "gx", "gy", "gz", "adc_gate")}
    overlays: dict[str, dict] = {}
    intervals: dict[str, list[tuple[float, float]]] = {name: [] for name in ("rf_amp", "gx", "gy", "gz", "adc_gate")}
    end_time = 0.0

    for block in request.blocks:
        if block.kind in ("excite_sinc", "refocus_sinc"):
            params = RfBlockParams.model_validate(block.params)
            PulseInspectRequest(duration_ms=params.duration_s * 1000, time_bandwidth=params.time_bandwidth,
                                flip_angle_deg=params.flip_angle_deg, phase_deg=params.phase_deg)
            channel = "rf_amp"
            channels[channel].extend((
                Event(time=block.t0_s, value=params.flip_angle_deg),
                Event(time=block.t0_s + params.duration_s, value=0),
            ))
            channels["rf_phase"].append(Event(time=block.t0_s, value=params.phase_deg))
        elif block.kind.startswith("trap_"):
            params = GradientBlockParams.model_validate(block.params)
            channel = block.kind.removeprefix("trap_")
            result = validate_gradient(GradientPulseSpec(amplitude_mt_m=params.amplitude_mt_m,
                duration_ms=params.duration_s * 1000, ramp_time_ms=params.ramp_time_s * 1000,
                channel=channel.replace("g", "G")), GradientHardwareConstraints())
            if not result.is_valid:
                raise ValueError("; ".join(result.violations))
            channels[channel].extend((
                Event(time=block.t0_s, value=params.amplitude_mt_m),
                Event(time=block.t0_s + params.duration_s, value=0),
            ))
        else:
            params = AdcBlockParams.model_validate(block.params)
            channel = "adc_gate"
            channels[channel].extend((Event(time=block.t0_s, value=1), Event(time=block.t0_s + params.duration_s, value=0)))

        stop = block.t0_s + params.duration_s
        if any(block.t0_s < old_stop and old_start < stop for old_start, old_stop in intervals[channel]):
            raise ValueError(f"overlapping blocks on {channel}")
        intervals[channel].append((block.t0_s, stop))
        end_time = max(end_time, stop)

    duration = request.duration_s if request.duration_s is not None else max(end_time, 1e-3)
    if request.duration_s is not None and duration < end_time:
        raise ValueError("block extends beyond requested duration")
    result_channels = []
    for name, events in channels.items():
        events.sort(key=lambda event: event.time)
        result_channels.append(Channel(name=name, events=events))
        if name in ("gx", "gy", "gz"):
            gradient_blocks = sorted((b for b in request.blocks if b.kind == f"trap_{name}"), key=lambda b: b.t0_s)
            for index, block in enumerate(gradient_blocks):
                overlays[f"{name}:{index}"] = GradientBlockParams.model_validate(block.params).model_dump(mode="json")
        if name == "rf_amp":
            rf_blocks = sorted(
                (b for b in request.blocks if b.kind in ("excite_sinc", "refocus_sinc")),
                key=lambda b: b.t0_s,
            )
            for index, block in enumerate(rf_blocks):
                overlays[f"rf_amp:{index}"] = RfBlockParams.model_validate(block.params).model_dump(mode="json")
        if name == "adc_gate":
            adc_blocks = sorted((b for b in request.blocks if b.kind == "adc_gate"), key=lambda b: b.t0_s)
            for index, block in enumerate(adc_blocks):
                overlays[f"adc_gate:{index}"] = AdcBlockParams.model_validate(block.params).model_dump(mode="json")
    metadata = {
        "blocks": [block.model_dump(mode="json") for block in request.blocks],
        "event_overlays": overlays,
    }
    if any(block.kind.startswith("trap_") for block in request.blocks):
        metadata["gradient_units"] = "mt_m"
        metadata["fov_m"] = DEFAULT_FOV_M
        metadata["preferred_engine"] = "epg"
    return SequenceIR(name=request.name, duration=duration, channels=result_channels, metadata=metadata)
