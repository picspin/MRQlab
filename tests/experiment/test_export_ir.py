from pathlib import Path

from mrqlab_experiment.clinical_catalog import RESEARCH_3T
from mrqlab_experiment.executable_sequence import (
    GradientWaveform,
    LogicalBlock,
    LogicalSequenceIR,
    RfWaveform,
)
from mrqlab_experiment.export_ir import ExportState, assess_export, build_export_ir
from mrqlab_experiment.sequence_lowering import lower_sequence


def test_export_ir_deduplicates_shapes_and_stops_at_hardware_review():
    rf = RfWaveform(samples_ut=(0, 1, 0), phase_rad=(0, 0, 0), raster_s=1e-6)
    logical = LogicalSequenceIR(
        id="export",
        duration_s=0.01,
        blocks=(
            LogicalBlock(id="a", start_s=0, rf=rf),
            LogicalBlock(id="b", start_s=0.001, rf=rf),
        ),
    )
    export_ir = build_export_ir(lower_sequence(logical, RESEARCH_3T))
    assert len(export_ir.shapes) == 1
    assert export_ir.blocks[0].rf_shape_id == export_ir.blocks[1].rf_shape_id
    assessment = assess_export(export_ir, target_profile_valid=True)
    assert assessment.states == (
        ExportState.SIMULATION_VALID,
        ExportState.IR_VALID,
        ExportState.EXPORTABLE,
        ExportState.TARGET_PROFILE_VALID,
        ExportState.HARDWARE_REVIEW_REQUIRED,
    )


def test_frontend_and_kernel_do_not_gain_a_pulseq_adapter_in_b_core():
    assert not Path("apps/web/lib/pulseq.ts").exists()
    assert not Path(
        "packages/mrqlab_experiment/mrqlab_experiment/pulseq_adapter.py"
    ).exists()


def test_export_shape_identity_preserves_carrier_offset_and_gradient_axis():
    logical = LogicalSequenceIR(
        id="shape-semantics",
        duration_s=0.01,
        blocks=(
            LogicalBlock(
                id="rf-a",
                start_s=0,
                rf=RfWaveform(
                    samples_ut=(0, 1),
                    phase_rad=(0, 0),
                    raster_s=1e-6,
                    carrier_offset_hz=0,
                ),
            ),
            LogicalBlock(
                id="rf-b",
                start_s=0.001,
                rf=RfWaveform(
                    samples_ut=(0, 1),
                    phase_rad=(0, 0),
                    raster_s=1e-6,
                    carrier_offset_hz=100,
                ),
            ),
            LogicalBlock(
                id="gx",
                start_s=0.002,
                gradients=(
                    GradientWaveform(
                        axis="gx", samples_mt_m=(0, 1), raster_s=10e-6
                    ),
                ),
            ),
            LogicalBlock(
                id="gy",
                start_s=0.003,
                gradients=(
                    GradientWaveform(
                        axis="gy", samples_mt_m=(0, 1), raster_s=10e-6
                    ),
                ),
            ),
        ),
    )
    export_ir = build_export_ir(lower_sequence(logical, RESEARCH_3T))
    assert len(export_ir.shapes) == 4
    assert export_ir.blocks[0].rf_shape_id != export_ir.blocks[1].rf_shape_id
    assert {
        shape.axis for shape in export_ir.shapes if shape.kind == "gradient"
    } == {"gx", "gy"}
    assert {
        shape.carrier_offset_hz for shape in export_ir.shapes if shape.kind == "rf"
    } == {0, 100}
