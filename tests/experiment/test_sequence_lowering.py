import pytest

from mrqlab_experiment.clinical_catalog import RESEARCH_3T
from mrqlab_experiment.executable_sequence import (
    AdcWindow,
    GradientWaveform,
    GradientWaveform,
    LogicalBlock,
    LogicalSequenceIR,
    RfWaveform,
)
from mrqlab_experiment.sequence_lowering import lower_sequence


def test_lowering_quantizes_to_profile_rasters_and_records_adjustment():
    logical = LogicalSequenceIR(
        id="q",
        duration_s=0.01,
        blocks=(
            LogicalBlock(
                id="rf",
                start_s=1.4e-6,
                rf=RfWaveform(
                    samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6
                ),
            ),
        ),
    )
    executable = lower_sequence(logical, RESEARCH_3T)
    assert executable.blocks[0].start_s == pytest.approx(1e-6)
    assert executable.timing_adjustments == ("rf.start_s: 1.4e-06 -> 1e-06",)


def test_lowering_fails_when_adc_begins_inside_rf_dead_time():
    logical = LogicalSequenceIR(
        id="bad",
        duration_s=0.01,
        blocks=(
            LogicalBlock(
                id="rf",
                start_s=0,
                rf=RfWaveform(
                    samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6
                ),
            ),
            LogicalBlock(
                id="adc",
                start_s=50e-6,
                adc=AdcWindow(delay_s=0, dwell_s=1e-6, sample_count=4),
            ),
        ),
    )
    with pytest.raises(
        ValueError, match="ADC begins before RF dead time and ringdown complete"
    ):
        lower_sequence(logical, RESEARCH_3T)


def test_lowering_rejects_adc_dwell_off_profile_raster():
    logical = LogicalSequenceIR(
        id="bad-dwell",
        duration_s=0.01,
        blocks=(
            LogicalBlock(
                id="adc",
                start_s=0.001,
                adc=AdcWindow(delay_s=0, dwell_s=1.05e-6, sample_count=4),
            ),
        ),
    )
    with pytest.raises(
        ValueError, match="ADC dwell must be an exact adc_raster_s multiple"
    ):
        lower_sequence(logical, RESEARCH_3T)


def test_lowering_rejects_adc_in_same_rf_block_and_preserves_longest_rf_guard():
    simultaneous = LogicalSequenceIR(
        id="same-block",
        duration_s=0.01,
        blocks=(LogicalBlock(
            id="rf-adc", start_s=0,
            rf=RfWaveform(samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6),
            adc=AdcWindow(delay_s=0, dwell_s=1e-6, sample_count=4),
        ),),
    )
    with pytest.raises(ValueError, match="ADC begins before RF dead time"):
        lower_sequence(simultaneous, RESEARCH_3T)

    overlapping = LogicalSequenceIR(
        id="overlap", duration_s=0.01,
        blocks=(
            LogicalBlock(id="long", start_s=0, rf=RfWaveform(samples_ut=(1,) * 200, phase_rad=(0,) * 200, raster_s=1e-6)),
            LogicalBlock(id="short", start_s=50e-6, rf=RfWaveform(samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6)),
            LogicalBlock(id="adc", start_s=250e-6, adc=AdcWindow(delay_s=0, dwell_s=1e-6, sample_count=4)),
        ),
    )
    with pytest.raises(ValueError, match="ADC begins before RF dead time"):
        lower_sequence(overlapping, RESEARCH_3T)


def test_lowering_rejects_mixed_raster_start_and_off_raster_adc_delay():
    mixed = LogicalSequenceIR(id="mixed", duration_s=0.01, blocks=(LogicalBlock(
        id="mixed", start_s=1e-6,
        rf=RfWaveform(samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6),
        gradients=(GradientWaveform(axis="gx", samples_mt_m=(0, 1), raster_s=10e-6),),
    ),))
    with pytest.raises(ValueError, match="block start must align"):
        lower_sequence(mixed, RESEARCH_3T)
    delayed = LogicalSequenceIR(id="delay", duration_s=0.01, blocks=(LogicalBlock(
        id="adc", start_s=0.001,
        adc=AdcWindow(delay_s=1.05e-6, dwell_s=1e-6, sample_count=4),
    ),))
    with pytest.raises(ValueError, match="ADC delay must be an exact"):
        lower_sequence(delayed, RESEARCH_3T)


def test_lowering_rejects_duration_rounding_below_events_and_gradient_limits():
    duration = LogicalSequenceIR(id="duration", duration_s=14e-6, blocks=(LogicalBlock(
        id="rf", start_s=10e-6,
        rf=RfWaveform(samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6),
    ),))
    with pytest.raises(ValueError, match="quantized sequence duration"):
        lower_sequence(duration, RESEARCH_3T)
    amplitude = LogicalSequenceIR(id="amplitude", duration_s=0.01, blocks=(LogicalBlock(
        id="g", start_s=0,
        gradients=(GradientWaveform(axis="gx", samples_mt_m=(0, 81), raster_s=10e-6),),
    ),))
    with pytest.raises(ValueError, match="gradient amplitude"):
        lower_sequence(amplitude, RESEARCH_3T)
    slew = LogicalSequenceIR(id="slew", duration_s=0.01, blocks=(LogicalBlock(
        id="g", start_s=0,
        gradients=(GradientWaveform(axis="gx", samples_mt_m=(0, 3), raster_s=10e-6),),
    ),))
    with pytest.raises(ValueError, match="gradient slew rate"):
        lower_sequence(slew, RESEARCH_3T)


def test_lowering_rejects_adc_during_rf_in_the_same_block():
    logical = LogicalSequenceIR(
        id="same-block",
        duration_s=0.01,
        blocks=(
            LogicalBlock(
                id="rf-adc",
                start_s=0,
                rf=RfWaveform(
                    samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6
                ),
                adc=AdcWindow(delay_s=50e-6, dwell_s=1e-6, sample_count=4),
            ),
        ),
    )
    with pytest.raises(
        ValueError, match="ADC begins before RF dead time and ringdown complete"
    ):
        lower_sequence(logical, RESEARCH_3T)


@pytest.mark.parametrize(
    ("samples", "message"),
    (((0, 81), "gradient amplitude"), ((0, 80), "gradient slew rate")),
)
def test_lowering_rejects_gradient_hardware_limit_violations(samples, message):
    logical = LogicalSequenceIR(
        id="gradient-limit",
        duration_s=0.01,
        blocks=(
            LogicalBlock(
                id="g",
                start_s=0,
                gradients=(
                    GradientWaveform(
                        axis="gx", samples_mt_m=samples, raster_s=10e-6
                    ),
                ),
            ),
        ),
    )
    with pytest.raises(ValueError, match=message):
        lower_sequence(logical, RESEARCH_3T)


def test_lowering_uses_adc_raster_and_requires_exact_adc_delay():
    quantized = lower_sequence(
        LogicalSequenceIR(
            id="adc-raster",
            duration_s=0.01,
            blocks=(
                LogicalBlock(
                    id="adc",
                    start_s=1.4e-6,
                    adc=AdcWindow(delay_s=1e-6, dwell_s=1e-6, sample_count=4),
                ),
            ),
        ),
        RESEARCH_3T,
    )
    assert quantized.blocks[0].start_s == pytest.approx(1.4e-6)
    assert quantized.blocks[0].timing_unit == "s"
    assert quantized.rf_dead_time_s == RESEARCH_3T.rf_dead_time_s
    assert quantized.lowering_provenance == (
        "deterministic ROUND_HALF_UP raster quantization",
    )

    invalid = LogicalSequenceIR(
        id="adc-delay",
        duration_s=0.01,
        blocks=(
            LogicalBlock(
                id="adc",
                start_s=0,
                adc=AdcWindow(delay_s=1.05e-6, dwell_s=1e-6, sample_count=4),
            ),
        ),
    )
    with pytest.raises(
        ValueError, match="ADC delay must be an exact adc_raster_s multiple"
    ):
        lower_sequence(invalid, RESEARCH_3T)


def test_lowering_rejects_block_past_quantized_sequence_duration():
    logical = LogicalSequenceIR(
        id="duration-rounding",
        duration_s=14.996e-6,
        blocks=(
            LogicalBlock(
                id="adc",
                start_s=0.9e-6,
                adc=AdcWindow(delay_s=0, dwell_s=1e-6, sample_count=4),
            ),
        ),
    )
    with pytest.raises(ValueError, match="quantized sequence duration"):
        lower_sequence(logical, RESEARCH_3T)
