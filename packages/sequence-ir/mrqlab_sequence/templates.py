from .models import Channel, Event, SequenceIR

def _ch(name, pairs): return Channel(name=name, events=[Event(time=t, value=v) for t, v in pairs])

def build_sequence(template: str, params: dict | None = None) -> SequenceIR:
    p = params or {}; kind = template.upper(); te = float(p.get("te", .03)); tr = float(p.get("tr", .5))
    if not 0 < te < tr: raise ValueError("require 0 < te < tr")
    flip = float(p.get("flip_angle", 30 if kind == "GRE" else 90))
    echoes = int(p.get("echoes", 4 if kind == "TSE" else 1))
    rf = [(0., flip)]
    adc = []
    if kind == "GRE":
        adc = [(te, 1), (te + .002, 0)]
    elif kind in {"SE", "TSE"}:
        for n in range(echoes):
            center = te * (n + 1); rf.append((center - te / 2, 180)); adc += [(center, 1), (center + .002, 0)]
    else: raise ValueError(f"unknown template {template!r}")
    gx = [item for t, v in adc if v == 1 for item in [(max(0., t - .003), -1), (t, 1), (t + .002, 0)]]
    return SequenceIR(name=kind, duration=tr, channels=[
        _ch("rf_amp", rf), _ch("rf_phase", [(t, 0) for t, _ in rf]),
        _ch("gx", gx), _ch("gy", []), _ch("gz", [(0, 1), (.001, 0)]),
        _ch("adc_gate", adc), _ch("nco_freq", [(0, 0)]), _ch("nco_phase", [(0, 0)])],
        metadata={"template": kind, "te": te, "tr": tr, "echoes": echoes})

def fid(duration: float = .1) -> SequenceIR:
    """Small demo/test helper; templates are the product path."""
    return SequenceIR(name="FID demo", duration=duration, channels=[_ch("rf_amp", [(0, 90)]), _ch("adc_gate", [(.001, 1), (duration, 0)])])
