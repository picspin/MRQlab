import pytest
from pydantic import ValidationError

from mrqlab_sequence import Channel, Event, SequenceIR, build_sequence


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


def test_sequence_rejects_channel_events_after_declared_duration():
    with pytest.raises(ValidationError, match="duration"):
        SequenceIR(
            name="post-duration",
            duration=0.01,
            channels=[
                Channel(name="adc_gate", events=[Event(time=0.02, value=1.0)])
            ],
        )


@pytest.mark.parametrize("echoes", [0, -1, 1.5, True])
def test_templates_require_strict_positive_integer_echo_count(echoes):
    with pytest.raises(ValueError, match="positive integer"):
        build_sequence("TSE", {"te": 0.02, "tr": 0.1, "echoes": echoes})


@pytest.mark.parametrize("echoes", [2, 10**400])
def test_template_echo_train_must_fit_within_tr(echoes):
    with pytest.raises(ValueError, match="fit within tr"):
        build_sequence("TSE", {"te": 0.03, "tr": 0.05, "echoes": echoes})
