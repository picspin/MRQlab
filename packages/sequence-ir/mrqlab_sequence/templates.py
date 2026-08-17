import math
from numbers import Integral, Real

from .models import Channel, Event, SequenceIR

def _ch(name, pairs): return Channel(name=name, events=[Event(time=t, value=v) for t, v in pairs])


def _finite_parameter(params: dict, name: str, default: float) -> float:
    value = params.get(name, default)
    if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _echo_count(params: dict, default: int) -> int:
    value = params.get("echoes", default)
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError("echoes must be a strict positive integer")
    return int(value)

def build_sequence(template: str, params: dict | None = None) -> SequenceIR:
    p = params or {}; kind = template.upper()
    if kind not in {"GRE", "SE", "TSE"}:
        raise ValueError(f"unknown template {template!r}")
    te = _finite_parameter(p, "te", .03); tr = _finite_parameter(p, "tr", .5)
    if not 0 < te < tr: raise ValueError("require 0 < te < tr")
    flip = _finite_parameter(p, "flip_angle", 30 if kind == "GRE" else 90)
    refocusing_flip = _finite_parameter(p, "refocusing_flip_angle", 180.0)
    if not 0 < refocusing_flip <= 180:
        raise ValueError("refocusing_flip_angle must satisfy 0 < angle <= 180")
    echoes = _echo_count(p, 4 if kind == "TSE" else 1)
    train_overflows = (
        te + .002 > tr
        if kind == "GRE"
        else tr <= .002 or echoes > (tr - .002) / te
    )
    if train_overflows:
        raise ValueError("echo train and ADC gate must fit within tr")
    rf = [(0., flip)]
    adc = []
    if kind == "GRE":
        adc = [(te, 1), (te + .002, 0)]
    elif kind in {"SE", "TSE"}:
        for n in range(echoes):
            center = te * (n + 1); rf.append((center - te / 2, refocusing_flip)); adc += [(center, 1), (center + .002, 0)]
    gx = [item for t, v in adc if v == 1 for item in [(max(0., t - .003), -1), (t, 1), (t + .002, 0)]]
    rf_phases = [0.0] + ([90.0] * (len(rf) - 1) if kind in {"SE", "TSE"} else [0.0] * (len(rf) - 1))
    metadata = {"template": kind, "te": te, "tr": tr, "echoes": echoes,
                "refocusing_flip_angle": refocusing_flip,
                "preferred_engine": "epg" if kind == "TSE" else "bloch"}
    if kind == "TSE":
        metadata["epg_dk_events"] = [
            {"time": center - 0.75 * te, "dk": [1, 0, 0]}
            for n in range(echoes)
            for center in (te * (n + 1),)
        ] + [
            {"time": center - 0.25 * te, "dk": [1, 0, 0]}
            for n in range(echoes)
            for center in (te * (n + 1),)
        ]
        metadata["epg_dk_events"].sort(key=lambda event: event["time"])
        for event in metadata["epg_dk_events"]:
            event["time"] = round(event["time"], 12)
    return SequenceIR(name=kind, duration=tr, channels=[
        _ch("rf_amp", rf), _ch("rf_phase", list(zip((t for t, _ in rf), rf_phases))),
        _ch("gx", gx), _ch("gy", []), _ch("gz", [(0, 1), (.001, 0)]),
        _ch("adc_gate", adc), _ch("nco_freq", [(0, 0)]), _ch("nco_phase", [(0, 0)]),
    ], metadata=metadata)

def fid(duration: float = .1) -> SequenceIR:
    """Small demo/test helper; templates are the product path."""
    return SequenceIR(name="FID demo", duration=duration, channels=[_ch("rf_amp", [(0, 90)]), _ch("adc_gate", [(.001, 1), (duration, 0)])])
