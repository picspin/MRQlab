import os
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from mrqlab_experiment import (
    ExperimentGraph,
    build_clinical_recipe,
    build_preset,
    build_result_graph,
    list_clinical_recipes,
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
    """Validate client options first, then force legacy /simulate snapshots off."""
    from dataclasses import asdict, replace

    from mrqlab_physics import EngineOptions

    validated = EngineOptions(**raw)
    forced = replace(validated, return_magnetization=False, return_configurations=False)
    return asdict(forced)


def _experiment_engine_options(graph: ExperimentGraph) -> dict[str, Any]:
    """Honor snapshot flags only when the matching product was requested."""
    from dataclasses import asdict, replace

    from mrqlab_physics import EngineOptions

    requested = set(graph.readout.products)
    validated = EngineOptions(**graph.engine.options)
    return asdict(
        replace(
            validated,
            return_magnetization=validated.return_magnetization and "magnetization" in requested,
            return_configurations=validated.return_configurations and "configurations" in requested,
        )
    )


def _graph_from_simulate(request: SimulateRequest) -> ExperimentGraph:
    if request.template is not None:
        sequence = build_sequence(request.template.template, request.template.params)
    else:
        sequence = request.sequence
    assert sequence is not None
    template_name = str(sequence.metadata.get("template", "SE")).upper()
    preset_name = _TEMPLATE_PRESET.get(template_name, "spin-echo")
    base = build_preset(preset_name)
    return base.model_copy(
        update={
            "sequence": sequence,
            "engine": base.engine.model_copy(
                update={
                    "preferred": request.engine,
                    "options": _api_engine_options(request.options),
                }
            ),
            "sample": base.sample.model_validate(request.phantom or {}),
            "scanner": base.scanner.model_validate(request.scanner or {}),
            "constraints": base.constraints.model_copy(
                update={"matrix": request.matrix, "max_work": MAX_WORK}
            ),
        }
    )


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


@app.get("/clinical-recipes")
def clinical_recipes():
    recipes = list_clinical_recipes()
    return {
        "recipes": [
            {"id": name, "experiment": build_clinical_recipe(name).model_dump(mode="json")}
            for name in recipes
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
    resolved = graph.model_copy(deep=True)
    resolved.constraints.max_work = min(resolved.constraints.max_work, MAX_WORK)
    try:
        resolved.engine.options = _experiment_engine_options(resolved)
        return build_result_graph(run_experiment(resolved))
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
