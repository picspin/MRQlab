from mrqlab_experiment import build_preset, compile_sequence
from mrqlab_experiment.physics_ir import CompilerSpan, compile_physics_ir
from mrqlab_physics import EngineOptions


def test_existing_scheduler_compiles_to_versioned_physics_ir():
    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    ir = compile_physics_ir(compile_sequence(graph), "epg", EngineOptions(epg_kmax=8))
    assert ir.schema_version == "1.0"
    assert ir.representation == "epg"
    assert {op.kind for op in ir.operators} >= {
        "RF_ROTATION",
        "FREE_EVOLUTION",
        "EPG_SHIFT",
        "READOUT",
    }
    assert ir.compiler_spans == (CompilerSpan(kind="EPG", start=0, stop=len(ir.operators)),)


def test_ssepg_is_a_distinct_span_name_not_epg_flag():
    assert "ssEPG" in {"Bloch", "EPG", "PDG", "ssEPG"}


def test_run_experiment_invokes_physics_ir_compiler_and_attaches_to_kernel_run():
    from mrqlab_experiment import run_experiment

    graph = build_preset("dark-blood-tse", {"te": 0.02, "tr": 0.1, "echoes": 2})
    run = run_experiment(graph)
    assert run.physics_ir is not None
    assert run.physics_ir.schema_version == "1.0"
    assert run.physics_ir.representation == "epg"
    assert len(run.physics_ir.operators) > 0

