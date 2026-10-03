import math

import pytest
from pydantic import ValidationError

from mrqlab_experiment.executable_sequence import (
    AdcWindow,
    GradientWaveform,
    LogicalBlock,
    LogicalSequenceIR,
    RfWaveform,
)


def test_logical_ir_carries_shaped_rf_arbitrary_g_and_adc_sampling():
    sequence = LogicalSequenceIR(
        id="tse-logical",
        duration_s=0.02,
        blocks=(
            LogicalBlock(
                id="b0",
                start_s=0,
                rf=RfWaveform(
                    samples_ut=(0, 2, 4, 2, 0),
                    phase_rad=(0, 0, 0, 0, 0),
                    raster_s=1e-6,
                    carrier_offset_hz=0,
                ),
                gradients=(
                    GradientWaveform(
                        axis="gz", samples_mt_m=(0, 10, 10, 0), raster_s=10e-6
                    ),
                ),
                adc=AdcWindow(
                    delay_s=0.005,
                    dwell_s=2e-6,
                    sample_count=128,
                    frequency_offset_hz=0,
                    phase_offset_rad=0,
                ),
            ),
        ),
    )
    assert sequence.blocks[0].adc.sample_count == 128
    assert sequence.blocks[0].rf.samples_ut[2] == 4
    assert sequence.blocks[0].gradients[0].axis == "gz"


def test_contract_rejects_mismatched_rf_samples_and_non_finite_gradient():
    with pytest.raises(
        ValidationError, match="RF amplitude and phase sample counts must match"
    ):
        RfWaveform(samples_ut=(1, 2), phase_rad=(0,), raster_s=1e-6)
    with pytest.raises(ValidationError, match="finite"):
        GradientWaveform(
            axis="gx", samples_mt_m=(0, math.inf), raster_s=10e-6
        )
