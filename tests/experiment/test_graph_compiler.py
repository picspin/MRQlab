import pytest
from mrqlab_experiment import ExperimentGraph, build_preset, compile_sequence
from mrqlab_experiment.models import ExperimentNode


def test_tse_preset_is_an_experiment_graph_above_sequence_ir():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    assert isinstance(graph, ExperimentGraph)
    assert graph.intent == "clinical_contrast"
    assert [node.kind for node in graph.nodes] == ["RF", "LOOP", "READOUT"]
    sequence = compile_sequence(graph)
    assert sequence.metadata["preferred_engine"] == "epg"
    assert sequence.metadata["experiment_id"] == graph.id


def test_reserved_experiment_node_cannot_execute_in_v0():
    graph = build_preset("spin-echo")
    graph.nodes += (ExperimentNode(id="inject", kind="INJECTION", label="Injection"),)
    with pytest.raises(ValueError, match="reserved node kind INJECTION is not executable in schema 1.0"):
        compile_sequence(graph)
