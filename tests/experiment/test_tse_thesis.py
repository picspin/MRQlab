from mrqlab_experiment import build_preset, run_experiment
from mrqlab_experiment.observations import build_result_graph

def _run(angle):
    graph = build_preset("dark-blood-tse", {
        "te": 0.02, "tr": 0.12, "echoes": 4, "refocusing_flip_angle": angle,
    })
    graph.engine.options = {"epg_kmax": 8, "return_configurations": True}
    graph.readout.products = ("signal", "k_trajectory", "image", "configurations", "echo_train", "sar")
    return build_result_graph(run_experiment(graph))

def test_refocusing_angle_changes_every_tse_thesis_product():
    high, low = _run(180), _run(120)
    by_kind = lambda result: {item.kind: item.data for item in result.observations}
    a, b = by_kind(high), by_kind(low)
    for kind in ("configurations", "echo_train", "image", "sar"):
        assert a[kind] != b[kind]
    assert a["sar"] > b["sar"]
