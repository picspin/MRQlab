import os
from dataclasses import replace
from typing import Any
import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator
from mrqlab_sequence import SequenceIR, TemplateRequest, build_sequence
from mrqlab_physics import (
    EngineOptions,
    Isochromat,
    Phantom,
    ScannerModel,
    SpectralPool,
    get_engine,
    list_engines,
)
from mrqlab_recon import fft_reconstruct

MAX_MATRIX = int(os.getenv("SIM_MAX_MATRIX", "64"))
MAX_WORK = int(os.getenv("SIM_MAX_WORK", "2000000"))

class SimulateRequest(BaseModel):
    sequence: SequenceIR | None = None
    template: TemplateRequest | None = None
    engine: str | None = None
    phantom: dict[str, Any] = Field(default_factory=dict)
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


def _phantom_from_payload(payload: dict[str, Any]) -> Phantom:
    values = dict(payload)
    values["isochromats"] = tuple(Isochromat(**item) for item in values.get("isochromats", ()))
    values["pools"] = tuple(SpectralPool(**item) for item in values.get("pools", ()))
    return Phantom(**values)

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
    if request.matrix > MAX_MATRIX:
        raise HTTPException(422, f"matrix exceeds SIM_MAX_MATRIX ({MAX_MATRIX})")
    try:
        sequence = request.sequence or build_sequence(request.template.template, request.template.params)
        requested_options = EngineOptions(**request.options)
        options = replace(requested_options, max_work=min(requested_options.max_work, MAX_WORK))
        engine_name = request.engine or str(sequence.metadata.get("preferred_engine", "bloch"))
        result = get_engine(engine_name).simulate(
            sequence, _phantom_from_payload(request.phantom), ScannerModel(**request.scanner), options,
        )
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise HTTPException(422, str(exc)) from exc
    recon = fft_reconstruct(result.signal) if result.signal.size else np.array([])
    return {
        "signal": [{"real": float(value.real), "imag": float(value.imag)} for value in result.signal],
        "k_trajectory": result.k_trajectory.tolist(),
        "reconstruction_magnitude": np.abs(recon).tolist(),
        "meta": result.meta,
        "timing": result.timing,
    }
