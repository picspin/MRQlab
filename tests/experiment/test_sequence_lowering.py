import pytest

from mrqlab_experiment.clinical_catalog import RESEARCH_3T
from mrqlab_experiment.executable_sequence import GradientWaveform
from mrqlab_experiment.executable_sequence import (
    AdcWindow,
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


def test_lowering_fails_when_gradient_amplitude_exceeds_scanner_limit():
    logical = LogicalSequenceIR(id="over-amp", duration_s=.01, blocks=(LogicalBlock(
        id="g", start_s=0, gradients=(GradientWaveform(axis="gx", samples_mt_m=(0, 100), raster_s=10e-6),),
    ),))
    with pytest.raises(ValueError, match="exceeds scanner limit"):
        lower_sequence(logical, RESEARCH_3T)


def test_lowering_fails_when_same_block_adc_begins_during_rf_dead_time():
    logical = LogicalSequenceIR(id="same-block-adc", duration_s=.01, blocks=(LogicalBlock(
        id="rf_adc", start_s=0,
        rf=RfWaveform(samples_ut=(1, 1), phase_rad=(0, 0), raster_s=1e-6),
        adc=AdcWindow(delay_s=1e-6, dwell_s=1e-6, sample_count=4),
    ),))
    with pytest.raises(ValueError, match="ADC begins before RF dead time and ringdown complete"):
        lower_sequence(logical, RESEARCH_3T)
