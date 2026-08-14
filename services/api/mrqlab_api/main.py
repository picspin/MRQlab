import os
from typing import Any
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from mrqlab_sequence import SequenceIR, TemplateRequest, build_sequence
from mrqlab_physics import EngineOptions, Phantom, ScannerModel, get_engine, list_engines
from mrqlab_recon import fft_reconstruct

MAX_MATRIX = int(os.getenv("SIM_MAX_MATRIX", "64"))
MAX_RUNTIME = float(os.getenv("SIM_MAX_RUNTIME", "30"))

class SimulateRequest(BaseModel):
    sequence: SequenceIR | None = None
    template: TemplateRequest | None = None
    engine: str = "bloch"
    phantom: dict[str, float] = Field(default_factory=dict)
    scanner: dict[str, float] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    matrix: int = Field(default=32, ge=1)
    @model_validator(mode="after")
    def one_source(self):
        if (self.sequence is None) == (self.template is None):
            raise ValueError("provide exactly one of sequence or template")
        return self

app = FastAPI(title="MRQLab Simulation API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
                   allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health(): return {"status": "ok", "service": "mrqlab-api"}

@app.get("/engines")
def engines(): return {"default": "bloch", "engines": list_engines()}

@app.post("/sequences/build", response_model=SequenceIR)
def sequences_build(request: TemplateRequest):
    try: return build_sequence(request.template, request.params)
    except ValueError as exc: raise HTTPException(422, str(exc)) from exc

@app.post("/simulate")
def simulate(request: SimulateRequest):
    if request.matrix > MAX_MATRIX: raise HTTPException(422, f"matrix exceeds SIM_MAX_MATRIX ({MAX_MATRIX})")
    sequence = request.sequence or build_sequence(request.template.template, request.template.params)
    # Cap pathological IR duration; the Bloch solver is linear in duration/dwell.
    dwell = float(request.options.get("dwell_time", .001))
    if dwell <= 0 or sequence.duration > MAX_RUNTIME:
        raise HTTPException(422, "simulation exceeds configured runtime work cap")
    try:
        result = get_engine(request.engine).simulate(sequence, Phantom(**request.phantom),
                 ScannerModel(**request.scanner), EngineOptions(**request.options))
    except (ValueError, TypeError, NotImplementedError) as exc: raise HTTPException(422, str(exc)) from exc
    recon = fft_reconstruct(result.signal) if result.signal.size else np.array([])
    return {"signal": [{"real": float(x.real), "imag": float(x.imag)} for x in result.signal],
            "k_trajectory": result.k_trajectory.tolist(), "reconstruction_magnitude": np.abs(recon).tolist(),
            "meta": result.meta, "timing": result.timing}
