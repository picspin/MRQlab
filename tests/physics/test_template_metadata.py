from mrqlab_sequence import build_sequence


def test_templates_declare_backend_without_embedding_backend_code():
    assert build_sequence("SE").metadata["preferred_engine"] == "bloch"
    assert build_sequence("GRE").metadata["preferred_engine"] == "bloch"
    tse = build_sequence("TSE", {"te": 0.02, "tr": 0.1, "echoes": 2})
    assert tse.metadata["preferred_engine"] == "epg"
    assert tse.metadata["epg_dk_events"] == [
        {"time": 0.005, "dk": [1, 0, 0]},
        {"time": 0.015, "dk": [1, 0, 0]},
        {"time": 0.025, "dk": [1, 0, 0]},
        {"time": 0.035, "dk": [1, 0, 0]},
    ]
    assert [event.value for event in tse.channel("rf_phase")] == [0.0, 90.0, 90.0]
