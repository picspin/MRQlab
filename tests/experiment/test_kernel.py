from mrqlab_experiment import build_preset, run_experiment, validate_experiment


def test_kernel_runs_existing_bloch_path_without_reimplementing_physics():
    graph = build_preset("spin-echo", {"te": 0.02, "tr": 0.1})
    report = validate_experiment(graph)
    run = run_experiment(graph)
    assert report.valid is True
    assert run.sequence.metadata["experiment_id"] == graph.id
    assert run.sim_result.meta["engine"] == "bloch"
    assert run.sim_result.signal.size > 0
