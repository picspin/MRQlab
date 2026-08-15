import os
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from mrqlab_experiment import (
    ExperimentGraph,
    build_preset,
    build_result_graph,
    run_experiment,
    validate_experiment,
)
from mrqlab_physics import list_engines
from mrqlab_recon import fft_reconstruct
from mrqlab_sequence import SequenceIR, TemplateRequest, build_sequence

MAX_MATRIX = int(os.getenv("SIM_MAX_MATRIX", "64"))
MAX_WORK = int(os.getenv("SIM_MAX_WORK", "2000000"))

_TEMPLATE_PRESET = {
    "SE": "spin-echo",
    "GRE": "gradient-echo",
    "TSE": "dark-blood-tse",
}


class SimulateRequest(BaseModel):
    sequence: SequenceIR | None = None
    template: TemplateRequest | None = None
    engine: str | None = None
    phantom: dict[str, Any] = Field(default_factory=dict)
    scanner: dict[str, Any] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    matrix: int = Field(default=32, ge=1, strict=True)

    @model_validator(mode="after")
    def one_source(self):
        if (self.sequence is None) == (self.template is None):
            raise ValueError("provide exactly one of sequence or template")
        return self


app = FastAPI(title="MRQLab Simulation API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _legacy_response(result) -> dict[str, Any]:
    recon = fft_reconstruct(result.signal) if result.signal.size else np.array([])
    return {
        "signal": [{"real": float(value.real), "imag": float(value.imag)} for value in result.signal],
        "k_trajectory": result.k_trajectory.tolist(),
        "reconstruction_magnitude": np.abs(recon).tolist(),
        "meta": result.meta,
        "timing": result.timing,
    }


def _api_engine_options(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate client options first, then force API snapshot flags off."""
    from dataclasses import asdict, replace

    from mrqlab_physics import EngineOptions

    validated = EngineOptions(**raw)
    forced = replace(validated, return_magnetization=False, return_configurations=False)
    return asdict(forced)


def _graph_from_simulate(request: SimulateRequest) -> ExperimentGraph:
    if request.template is not None:
        sequence = build_sequence(request.template.template, request.template.params)
    else:
        sequence = request.sequence
    assert sequence is not None
    template_name = str(sequence.metadata.get("template", "SE")).upper()
    preset_name = _TEMPLATE_PRESET.get(template_name, "spin-echo")
    graph = build_preset(preset_name)
    # Mutate validated graph fields in place (Pydantic models are mutable by default).
    graph.sequence = sequence
    graph.engine.preferred = request.engine
    graph.engine.options = _api_engine_options(request.options)
    graph.sample = graph.sample.model_validate(request.phantom or {})
    graph.scanner = graph.scanner.model_validate(request.scanner or {})
    graph.constraints.matrix = request.matrix
    graph.constraints.max_work = MAX_WORK
    return graph


@app.get("/health")
def health():
    return {"status": "ok", "service": "mrqlab-api"}


@app.get("/engines")
def engines():
    return {"default": "bloch", "engines": list_engines()}


@app.get("/presets")
def presets():
    names = ("spin-echo", "gradient-echo", "dark-blood-tse")
    return {
        "presets": [
            {"name": name, "experiment": build_preset(name).model_dump(mode="json")}
            for name in names
        ]
    }


@app.post("/sequences/build", response_model=SequenceIR)
def sequences_build(request: TemplateRequest):
    try:
        return build_sequence(request.template, request.params)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/experiments/validate")
def experiments_validate(graph: ExperimentGraph):
    return validate_experiment(graph)


@app.post("/experiments/run")
def experiments_run(graph: ExperimentGraph):
    if graph.constraints.matrix > MAX_MATRIX:
        raise HTTPException(422, f"matrix exceeds SIM_MAX_MATRIX ({MAX_MATRIX})")
    graph.constraints.max_work = min(graph.constraints.max_work, MAX_WORK)
    try:
        graph.engine.options = _api_engine_options(graph.engine.options)
        return build_result_graph(run_experiment(graph))
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise HTTPException(422, str(exc)) from exc


@app.post("/simulate")
def simulate(request: SimulateRequest):
    if request.matrix > MAX_MATRIX:
        raise HTTPException(422, f"matrix exceeds SIM_MAX_MATRIX ({MAX_MATRIX})")
    try:
        graph = _graph_from_simulate(request)
        return _legacy_response(run_experiment(graph).sim_result)
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise HTTPException(422, str(exc)) from exc
