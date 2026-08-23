import pytest

from mrqlab_experiment import (
    CapabilityMismatch,
    build_preset,
    compile_sequence,
    plan_experiment,
    run_experiment,
)
from mrqlab_experiment.observations import build_result_graph
from mrqlab_experiment.physics_ir import compile_physics_ir
from mrqlab_physics import EngineOptions
import mrqlab_physics.registry as engine_registry


def _hybrid_graph():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    graph.engine.required_capabilities = frozenset(
        {"hard_rf", "shaped_rf", "configuration_states"}
    )
    return graph


def test_hybrid_tse_spans_cover_scheduled_operators():
    graph = _hybrid_graph()
    ir = compile_physics_ir(
        compile_sequence(graph), plan_experiment(graph).representation, EngineOptions(epg_kmax=8)
    )

    assert ir.representation == "hybrid"
    assert {span.kind for span in ir.compiler_spans} >= {"Bloch", "EPG"}
    assert ir.compiler_spans[0].start == 0
    assert ir.compiler_spans[-1].stop == len(ir.operators)
    assert all(
        left.stop == right.start
        for left, right in zip(ir.compiler_spans, ir.compiler_spans[1:])
    )


def test_hard_pulse_spin_echo_stays_one_epg_span():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    graph.engine.required_capabilities = frozenset({"hard_rf", "configuration_states"})
    ir = compile_physics_ir(compile_sequence(graph), "epg", EngineOptions(epg_kmax=8))

    assert ir.representation == "epg"
    assert len(ir.compiler_spans) == 1
    assert ir.compiler_spans[0].kind == "EPG"
    assert ir.compiler_spans[0].start == 0
    assert ir.compiler_spans[0].stop == len(ir.operators)


def test_hybrid_run_and_observation_provenance_are_hybrid():
    run = run_experiment(_hybrid_graph())
    result = build_result_graph(run)

    assert run.sim_result.meta["engine"] == "hybrid"
    assert result.observations[0].provenance.engine == "hybrid"
    assert result.observations[0].provenance.representation == "hybrid"
    assert run.physics_ir.representation == "hybrid"


def test_empty_required_capabilities_do_not_select_hybrid():
    from mrqlab_experiment.capabilities import select_representation

    assert select_representation(frozenset(), None).name == "bloch"


def test_missing_hybrid_runner_fails_closed(monkeypatch):
    monkeypatch.setattr(
        engine_registry,
        "_engines",
        {name: value for name, value in engine_registry._registry().items() if name != "hybrid"},
    )

    with pytest.raises(CapabilityMismatch, match="hybrid"):
        run_experiment(_hybrid_graph())
