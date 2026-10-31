"""Bounded research-only API; no promotion of the locked clinical catalog."""
from hashlib import sha256
from pathlib import Path
import json
import base64
import platform
from typing import Literal, Any, Annotated
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from mrqlab_experiment.tse_imaging import run_tse_imaging
from mrqlab_experiment.spatial_imaging import run_spatial_imaging
from mrqlab_experiment.flow_imaging import run_flow_imaging
from mrqlab_experiment.pulsatile_dir import run_pulsatile_dir
from mrqlab_experiment.cest_mt_noe import run_cest_mt_noe
from mrqlab_experiment.cest_solomon import run_cest_solomon
from mrqlab_experiment.cest_memory import run_cest_memory
from mrqlab_experiment.mrs_basis import run_mrs_basis
from mrqlab_experiment.mrs_press import run_press_basis
from mrqlab_experiment.mrs_quantum import run_mrs_quantum
from mrqlab_experiment.radial_tse import run_radial_tse
from mrqlab_experiment.flow_epi import run_flow_epi

router=APIRouter(prefix='/research',tags=['research/teaching'])
Kind=Literal['tse','noncartesian','flow','pulsatile_flow','flow_epi','cest','cest_solomon','cest_memory','mrs','mrs_press','mrs_quantum','radial_tse']


class StrictParameters(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)


T2Value=Annotated[float,Field(gt=0,le=10.)]
TimeValue=Annotated[float,Field(ge=0,le=30.)]
RRValue=Annotated[float,Field(gt=0,le=3.)]
Amount=Annotated[float,Field(gt=0,le=10.)]
Phase=Annotated[float,Field(ge=-3.15,le=3.15)]
Shift=Annotated[float,Field(ge=-20.,le=20.)]


class TSEParameters(StrictParameters):
    labels: list | None=None
    echoes: int=Field(default=4,ge=1,le=16)
    order: Literal['linear','centric']='centric'
    echo_spacing_s: float=Field(default=.008,ge=.006,le=.03)
    tr_s: float=Field(default=.4,ge=.05,le=2.)
    partitions: int | None=Field(default=None,ge=2,le=4)
    t2_s: list[T2Value]=Field(default_factory=lambda:[.04,.12],min_length=2,max_length=2)
    refocusing_angle: float=Field(default=180.,ge=1.,le=180.)
    refocusing_end_angle: float=Field(default=180.,ge=1.,le=180.)
    weighting: Literal['echo','mean']='echo'
    max_samples: int=Field(default=4096,ge=1,le=4096)
    max_work: int=Field(default=100000000,ge=1,le=100000000)
    max_duration_s: float=Field(default=100.,gt=0,le=100.)


class NoncartesianParameters(StrictParameters):
    chain: Literal['noncartesian']='noncartesian'
    labels: list | None=None
    encoding: Literal['radial','stack_of_stars']='radial'
    order: Literal['sequential_ky']='sequential_ky'
    spokes: int=Field(default=48,ge=2,le=96)
    points: int=Field(default=32,ge=16,le=64)
    acceleration: Literal[1]=1
    max_samples: int=Field(default=24576,ge=1,le=24576)
    max_work: int=Field(default=10000000000,ge=1,le=10000000000)
    quality_threshold: float=Field(default=1e-6,gt=0,le=1.)
    reconstruction: Literal['gridding','cgls','nufft_cgls']='cgls'
    nufft_eps: float=Field(default=1e-13,ge=1e-14,le=1e-3)
    inverse_max_iterations: int=Field(default=1500,ge=1,le=1500)
    inverse_tolerance: float=Field(default=1e-12,ge=1e-14,le=.1)
    max_memory_bytes: int=Field(default=134217728,ge=1,le=134217728)


class RadialTSEParameters(StrictParameters):
    labels: list | None=None
    echoes: int=Field(default=4,ge=2,le=16)
    spokes: int=Field(default=96,ge=4,le=192)
    points: int=Field(default=32,ge=16,le=64)
    echo_spacing_s: float=Field(default=.008,ge=.006,le=.03)
    tr_s: float=Field(default=.4,ge=.05,le=2.)
    t2_s: list[T2Value]=Field(default_factory=lambda:[.04,.12],min_length=2,max_length=2)
    basis_t2_s: list[T2Value] | None=Field(default=None,min_length=2,max_length=2)
    refocusing_angle: float=Field(default=180.,ge=1.,le=180.)
    refocusing_end_angle: float=Field(default=180.,ge=1.,le=180.)
    echo_order: Literal['forward','reverse']='forward'
    display_echo: int=Field(default=2,ge=1,le=16)
    backend: Literal['exact','finufft']='exact'
    inverse_max_iterations: int=Field(default=6000,ge=1,le=6000)
    inverse_tolerance: float=Field(default=1e-10,ge=1e-13,le=.1)
    nufft_eps: float=Field(default=1e-13,ge=1e-14,le=1e-3)
    control_iterations: int=Field(default=1000,ge=1,le=1000)
    component_phase_rad: list[Phase]=Field(default_factory=lambda:[0.,0.],min_length=2,max_length=2)
    max_samples: int=Field(default=24576,ge=1,le=24576)
    max_work: int=Field(default=20000000000,ge=1,le=50000000000)
    max_memory_bytes: int=Field(default=134217728,ge=1,le=134217728)
    max_duration_s: float=Field(default=100.,gt=0,le=100.)
    target_image_error: float=Field(default=1e-6,gt=0,le=1.)
    target_coefficient_error: float=Field(default=1e-6,gt=0,le=1.)
    target_min_contrast: float=Field(default=.005,ge=0,le=1.)
    target_max_rf_energy: float=Field(default=200.,gt=0,le=1000.)


class FlowParameters(StrictParameters):
    r_peaks_s: list[TimeValue]=Field(default_factory=lambda:[0.,1.2,2.4],min_length=2,max_length=10)
    inversion_time_s: float=Field(default=.9,gt=.008,le=2.)
    blood_velocity_m_s: float=Field(default=.025,ge=-.1,le=.1)
    thickness_m: float=Field(default=.005,ge=.001,le=.02)
    rf_steps: int=Field(default=128,ge=16,le=256)
    spin_count: int=Field(default=801,ge=33,le=1601)
    off_resonance_hz: float=Field(default=0.,ge=-500.,le=500.)
    rr_range_s: list[RRValue]=Field(default_factory=lambda:[.5,1.5],min_length=2,max_length=2)
    max_work: int=Field(default=10000000,ge=1,le=10000000)
    max_duration_s: float=Field(default=10.,gt=0,le=10.)
    blood_target_max: float=Field(default=.1,gt=0,lt=1.)
    wall_target_min: float=Field(default=.7,gt=0,le=1.)


class PulsatileFlowParameters(StrictParameters):
    r_peaks_s: list[TimeValue]=Field(default_factory=lambda:[0.,1.2,2.4],min_length=1,max_length=10)
    observation_end_s: float=Field(default=3.6,gt=0,le=10.)
    inversion_time_s: float=Field(default=.9,gt=.008,le=2.)
    trigger_latency_s: float=Field(default=.003,ge=0,le=.05)
    initial_rr_s: float=Field(default=1.2,ge=.2,le=3.)
    rr_range_s: list[RRValue]=Field(default_factory=lambda:[.5,1.5],min_length=2,max_length=2)
    radius_m: float=Field(default=.002,ge=.0001,le=.01)
    density_kg_m3: float=Field(default=1060.,ge=500.,le=2000.)
    viscosity_pa_s: float=Field(default=.0035,ge=.0001,le=.1)
    mean_gradient_pa_m: float=Field(default=100.,ge=-2000.,le=2000.)
    oscillating_gradient_pa_m: float=Field(default=200.,ge=0,le=2000.)
    frequency_hz: float=Field(default=1.,ge=.05,le=5.)
    phase_rad: float=Field(default=0.,ge=-3.15,le=3.15)
    thickness_m: float=Field(default=.005,ge=.001,le=.02)
    radial_rings: int=Field(default=8,ge=2,le=32)
    axial_spins: int=Field(default=401,ge=33,le=1601)
    rf_steps: int=Field(default=128,ge=16,le=256)
    off_resonance_hz: float=Field(default=0.,ge=-500.,le=500.)
    blood_target_max: float=Field(default=.1,gt=0,lt=1.)
    wall_target_min: float=Field(default=.7,gt=0,le=1.)
    max_interrupted_fraction: float=Field(default=0.,ge=0,le=1.)
    max_work: int=Field(default=10000000,ge=1,le=10000000)
    max_duration_s: float=Field(default=10.,gt=0,le=10.)


class FlowEPIParameters(StrictParameters):
    r_peaks_s: list[TimeValue]=Field(default_factory=lambda:[0.,1.2],min_length=1,max_length=6)
    observation_end_s: float=Field(default=2.4,gt=0,le=10.)
    inversion_time_s: float=Field(default=.9,gt=.008,le=2.)
    trigger_latency_s: float=Field(default=.003,ge=0,le=.05)
    initial_rr_s: float=Field(default=1.2,ge=.2,le=3.)
    rr_range_s: list[RRValue]=Field(default_factory=lambda:[.5,1.5],min_length=2,max_length=2)
    radius_m: float=Field(default=.002,ge=.0005,le=.004)
    density_kg_m3: float=Field(default=1060.,ge=500.,le=2000.)
    viscosity_pa_s: float=Field(default=.0035,ge=.0001,le=.1)
    mean_gradient_pa_m: float=Field(default=100.,ge=-1000.,le=1000.)
    oscillating_gradient_pa_m: float=Field(default=200.,ge=0,le=1000.)
    frequency_hz: float=Field(default=1.,ge=.05,le=5.)
    phase_rad: float=Field(default=0.,ge=-3.15,le=3.15)
    thickness_m: float=Field(default=.005,ge=.001,le=.02)
    matrix_size: Literal[8,16]=16
    fov_m: float=Field(default=.012,ge=.008,le=.04)
    axial_spins: int=Field(default=401,ge=33,le=801)
    rf_steps: int=Field(default=64,ge=16,le=128)
    preparation: Literal['dir','none']='dir'
    off_resonance_hz: float=Field(default=0.,ge=-500.,le=500.)
    dwell_s: float=Field(default=.00006,ge=.00001,le=.0002)
    venc_m_s: float=Field(default=.05,ge=.02,le=.3)
    ramp_steps: int=Field(default=8,ge=2,le=32)
    max_gradient_t_m: float=Field(default=.04,gt=0,le=.04)
    max_nominal_slew_t_m_s: float=Field(default=150.,gt=0,le=150.)
    signal_floor: float=Field(default=1e-5,gt=0,le=.1)
    target_velocity_rmse_m_s: float=Field(default=.002,gt=0,le=.1)
    target_frozen_image_error: float=Field(default=.05,gt=0,le=1.)
    blood_target_max: float=Field(default=.1,gt=0,lt=1.)
    wall_target_min: float=Field(default=.7,gt=0,le=1.)
    max_interrupted_fraction: float=Field(default=0.,ge=0,le=1.)
    max_work: int=Field(default=200000000,ge=1,le=200000000)
    max_memory_bytes: int=Field(default=134217728,ge=1,le=134217728)
    max_duration_s: float=Field(default=10.,gt=0,le=10.)


class CESTParameters(StrictParameters):
    offsets_ppm: list[float]=Field(default_factory=lambda:[-5.,-3.5,-2.,-1.,1.,2.,3.5,5.],min_length=2,max_length=16)
    b0_t: float=Field(default=3.,ge=.5,le=7.)
    b1_uT: float=Field(default=1.,gt=0,le=3.)
    saturation_s: float=Field(default=1.,gt=0,le=2.)
    mode: Literal['cw','pulsed']='cw'
    n_pulses: int=Field(default=1,ge=1,le=20)
    pulse_s: float=Field(default=1.,gt=0,le=2.)
    gap_s: float=Field(default=0.,ge=0,le=1.)
    bound_fraction: float=Field(default=.08,ge=0,le=.3)
    bound_to_water_hz: float=Field(default=20.,ge=0,le=100.)
    bound_t2_s: float=Field(default=12e-6,ge=1e-6,le=1e-3)
    lineshape: Literal['super_lorentzian','gaussian']='super_lorentzian'
    max_work: int=Field(default=100000000,ge=1,le=100000000)
    max_duration_s: float=Field(default=300.,gt=0,le=300.)
    target_min_amide_contrast: float=Field(default=.005,gt=0,le=1.)


class SolomonCESTParameters(CESTParameters):
    pair_fraction: float=Field(default=.02,gt=0,le=.1)
    bridge_exchange_s1: float=Field(default=1000.,ge=0,le=5000.)
    bridge_shift_ppm: float=Field(default=1.,ge=-10.,le=10.)
    donor_shift_ppm: float=Field(default=-3.5,ge=-10.,le=10.)
    distance_m: float=Field(default=2.5e-10,ge=1e-10,le=2e-9)
    tau_c_s: float=Field(default=1e-8,ge=1e-12,le=1e-6)
    target_min_relay_contrast: float=Field(default=.005,gt=0,le=1.)


class MemoryCESTParameters(StrictParameters):
    offsets_ppm: list[float]=Field(default_factory=lambda:[-5.,-3.5,-2.,0.,2.,3.5,5.],min_length=3,max_length=16)
    b0_t: float=Field(default=3.,ge=.5,le=7.)
    b1_uT: float=Field(default=1.,gt=0,le=4.)
    pulse_s: float=Field(default=.02,ge=.00001,le=1.)
    gap_s: float=Field(default=.04,ge=0,le=.5)
    n_pulses: int=Field(default=4,ge=1,le=8)
    shape: Literal['hann','rectangular']='hann'
    phase_cycle_rad: list[Phase]=Field(default_factory=lambda:[0.],min_length=1,max_length=8)
    rf_bins: int=Field(default=16,ge=4,le=32)
    steps_per_bin: int=Field(default=24,ge=1,le=24)
    bound_fraction: float=Field(default=.08,gt=0,le=.3)
    bound_to_water_hz: float=Field(default=20.,ge=0,le=100.)
    bound_t2_s: float=Field(default=12e-6,ge=1e-6,le=.001)
    lineshape: Literal['super_lorentzian','gaussian','lorentzian']='super_lorentzian'
    pair_fraction: float=Field(default=.02,gt=0,le=.1)
    bridge_exchange_s1: float=Field(default=1000.,ge=0,le=5000.)
    bridge_shift_ppm: float=Field(default=1.,ge=-10.,le=10.)
    donor_shift_ppm: float=Field(default=-3.5,ge=-10.,le=10.)
    distance_m: float=Field(default=2.5e-10,ge=1e-10,le=2e-9)
    tau_c_s: float=Field(default=1e-8,ge=1e-12,le=1e-6)
    orientation_order: int=Field(default=32,ge=8,le=32)
    time_order: int=Field(default=32,ge=8,le=32)
    max_work: int=Field(default=32000000000,ge=1,le=32000000000)
    max_memory_bytes: int=Field(default=134217728,ge=1,le=134217728)
    max_duration_s: float=Field(default=300.,gt=0,le=300.)
    target_min_amide_contrast: float=Field(default=.005,gt=0,le=1.)
    target_min_relay_contrast: float=Field(default=.005,gt=0,le=1.)
    target_refinement_error: float=Field(default=.0002,gt=0,le=.1)
    target_kernel_error: float=Field(default=1e-6,gt=0,le=.01)


class MRSParameters(StrictParameters):
    echo_s: float=Field(default=.03,gt=0,le=.2)
    points: int=Field(default=512,ge=16,le=1024)
    dwell_s: float=Field(default=.0005,ge=.0001,le=.002)
    rf_steps: int=Field(default=64,ge=16,le=128)
    rf_duration_s: float=Field(default=.001,ge=.0001,le=.005)
    amounts: list[Amount]=Field(default_factory=lambda:[.02,.015,.01,.008],min_length=4,max_length=4)
    noise_std: float=Field(default=0.,ge=0,le=.01)
    seed: int=Field(default=7,ge=0,le=2147483647)
    phase_rad: float=Field(default=0.,ge=-3.15,le=3.15)
    shift_hz: float=Field(default=0.,ge=-20.,le=20.)
    fit_phase_grid_rad: list[Phase]=Field(default_factory=lambda:[0.],min_length=1,max_length=9)
    fit_shift_grid_hz: list[Shift]=Field(default_factory=lambda:[0.],min_length=1,max_length=9)
    basis_j_hz: float=Field(default=7.,ge=-20.,le=20.)
    sample_j_hz: float=Field(default=7.,ge=-20.,le=20.)
    max_work: int=Field(default=100000000,ge=1,le=100000000)
    target_relative_amount_error: float=Field(default=.05,gt=0,le=1.)


class PressMRSParameters(StrictParameters):
    refine_rf_steps: int=Field(default=128,ge=32,le=256)
    target_rf_error: float=Field(default=.002,gt=0,le=1.)
    echo_s: float=Field(default=.03,ge=.008,le=.2)
    points: int=Field(default=256,ge=16,le=512)
    dwell_s: float=Field(default=.0005,ge=.0001,le=.002)
    rf_duration_s: float=Field(default=.001,ge=.0001,le=.002)
    rf_steps: int=Field(default=64,ge=16,le=128)
    grid_size: int=Field(default=17,ge=3,le=25)
    refine_grid: int=Field(default=25,ge=5,le=33)
    extended_grid: int=Field(default=39,ge=7,le=49)
    extended_fov_scale: float=Field(default=3.,ge=1.6,le=4.)
    thickness_m: list[float]=Field(default_factory=lambda:[.02,.02,.02],min_length=3,max_length=3)
    fov_scale: float=Field(default=2.,ge=1.5,le=3.)
    basis_mode: Literal['volume','center']='volume'
    amounts: list[Amount]=Field(default_factory=lambda:[.02,.008],min_length=2,max_length=2)
    basis_j_hz: float=Field(default=7.,ge=-20.,le=20.)
    sample_j_hz: float=Field(default=7.,ge=-20.,le=20.)
    noise_std: float=Field(default=0.,ge=0,le=.01)
    seed: int=Field(default=7,ge=0,le=2147483647)
    max_work: int=Field(default=100000000,ge=1,le=100000000)
    max_memory_bytes: int=Field(default=134217728,ge=1,le=134217728)
    target_relative_amount_error: float=Field(default=.05,gt=0,le=1.)
    target_refinement_error: float=Field(default=.02,gt=0,le=1.)
    target_fov_error: float=Field(default=.02,gt=0,le=1.)
    target_leakage_fraction: float=Field(default=.1,gt=0,le=1.)


SCHEMAS={'tse':TSEParameters,'noncartesian':NoncartesianParameters,'flow':FlowParameters,'pulsatile_flow':PulsatileFlowParameters,'flow_epi':FlowEPIParameters,'cest':CESTParameters,'cest_solomon':SolomonCESTParameters,'mrs':MRSParameters,'mrs_press':PressMRSParameters,'radial_tse':RadialTSEParameters}
RUNNERS={'tse':run_tse_imaging,'noncartesian':run_spatial_imaging,'flow':run_flow_imaging,'pulsatile_flow':run_pulsatile_dir,'flow_epi':run_flow_epi,'cest':run_cest_mt_noe,'cest_solomon':run_cest_solomon,'mrs':run_mrs_basis,'mrs_press':run_press_basis,'radial_tse':run_radial_tse}
class QuantumMRSParameters(StrictParameters):
    echo_s: float=Field(default=.03,ge=.008,le=.2)
    repetition_s: float=Field(default=.6,ge=.05,le=10.)
    points: int=Field(default=256,ge=16,le=512)
    dwell_s: float=Field(default=.0005,ge=.0001,le=.002)
    rf_duration_s: float=Field(default=.001,ge=.00001,le=.002)
    rf_steps: int=Field(default=32,ge=16,le=64)
    refine_rf_steps: int=Field(default=64,ge=32,le=128)
    excitation_degrees: float=Field(default=90.,gt=0,le=180.)
    polarization: float=Field(default=.01,ge=.000001,le=.1)
    preparation: Literal['periodic','finite_dummies']='periodic'
    dummy_scans: int=Field(default=8,ge=0,le=128)
    basis_mode: Literal['matched','equilibrium']='matched'
    basis_t1_scale: float=Field(default=1.,ge=.2,le=4.)
    sample_t1_scale: float=Field(default=1.,ge=.2,le=4.)
    basis_j_hz: float=Field(default=7.,ge=-20.,le=20.)
    sample_j_hz: float=Field(default=7.,ge=-20.,le=20.)
    amounts: list[Amount]=Field(default_factory=lambda:[.02,.008],min_length=2,max_length=2)
    max_work: int=Field(default=1500000000,ge=1,le=1500000000)
    max_memory_bytes: int=Field(default=134217728,ge=1,le=134217728)
    target_relative_amount_error: float=Field(default=.05,gt=0,le=1.)
    target_rf_error: float=Field(default=.002,gt=0,le=.1)
    target_fit_residual: float=Field(default=.02,gt=0,le=.1)
    target_state_error: float=Field(default=1e-10,gt=0,le=1e-8)
    target_min_signal_fraction: float=Field(default=.2,gt=0,le=1.)


SCHEMAS['cest_memory']=MemoryCESTParameters
RUNNERS['cest_memory']=run_cest_memory
SCHEMAS['mrs_quantum']=QuantumMRSParameters
RUNNERS['mrs_quantum']=run_mrs_quantum


class RunRequest(StrictParameters):
    kind: Kind
    parameters: dict[str,Any]=Field(default_factory=dict)
    expected_source_hash: str | None=Field(default=None,pattern=r'^[a-f0-9]{64}$')


class SearchRequest(RunRequest):
    candidates: list[dict[str,Any]]=Field(min_length=1,max_length=4)


def source_hash():
    root=Path(__file__).resolve().parents[3]
    digest=sha256()
    for folder in ['packages','services/api']:
        for path in sorted((root/folder).rglob('*.py')):
            digest.update(str(path.relative_to(root)).encode()); digest.update(path.read_bytes())
    return digest.hexdigest()


# Pin the source actually imported by this process. A live edit requires restart;
# hashing newly edited files must never mislabel already loaded Python code.
IMPORTED_SOURCE_HASH=source_hash()


def checked_source_hash():
    current=source_hash()
    if current!=IMPORTED_SOURCE_HASH:
        raise HTTPException(409,'Source changed since API startup. Restart the research API before running or replaying.')
    return current


def serializable(value):
    if isinstance(value,np.ndarray): return serializable(value.tolist())
    if isinstance(value,np.generic): return serializable(value.item())
    if isinstance(value,complex): return dict(real=value.real,imag=value.imag)
    if isinstance(value,dict): return {k:serializable(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [serializable(v) for v in value]
    return value


def parameters_for(kind, parameters):
    try:
        parsed=SCHEMAS[kind].model_validate(parameters).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise HTTPException(422,detail=json.loads(exc.json(include_url=False))) from exc
    if kind in {'tse','noncartesian','radial_tse'}:
        if 'labels' not in parsed:
            y,x=np.indices((16,16)); labels=(((x-8)**2+(y-8)**2<20)|((x==3)&(y>3))).astype(int)
            if kind=='noncartesian' and parsed['encoding']=='stack_of_stars': labels=np.stack([labels,1-labels,np.roll(labels,2,0)])
            parsed['labels']=labels.tolist()
        labels=parsed['labels']
        grid_limit=(32 if parsed['backend']=='finufft' else 16) if kind=='radial_tse' else 64 if kind=='noncartesian' and parsed['reconstruction']=='nufft_cgls' else 16
        def valid_row(row):
            return isinstance(row,list) and 2<=len(row)<=grid_limit and all(type(v) is int and v in (0,1) for v in row)
        def valid_plane(plane):
            return isinstance(plane,list) and 2<=len(plane)<=grid_limit and all(valid_row(row) for row in plane) and len({len(row) for row in plane})==1
        is_2d=valid_plane(labels)
        is_3d=isinstance(labels,list) and 2<=len(labels)<=4 and all(valid_plane(plane) for plane in labels) and len({(len(plane),len(plane[0])) for plane in labels})==1
        if not is_2d and not is_3d:
            raise HTTPException(422,'research API labels require an integer two-class grid within the selected model/backend limit and <=4 partitions')
    return parsed


def _curve(label,x,y): return dict(label=label,x=np.asarray(x).tolist(),y=np.asarray(y).real.tolist())


def present(kind,result):
    images=[]; curves=[]
    if kind in {'tse','noncartesian','radial_tse'}:
        for key,title in [('reference','Reference'),('image','Reconstruction')]:
            image=np.asarray(result[key]).real
            if image.ndim==3: image=image[len(image)//2]
            images.append(dict(label=title,width=image.shape[1],height=image.shape[0],values=image.ravel().tolist()))
        if kind in {'tse','radial_tse'}:
            echo_times=result['echo_times_s'] if kind=='tse' else np.arange(1,len(result['tissue_echo_weights'][0])+1)*result['design']['echo_spacing_s']
            for i,weights in enumerate(result['tissue_echo_weights']): curves.append(_curve(f'Tissue {i+1}',np.asarray(echo_times)*1000,weights))
            x_label='Echo time (ms)'; y_label='Absolute EPG signal'
        else:
            for i,solver in enumerate(result['solvers']): curves.append(_curve(f'CGLS frame {i+1}',np.arange(len(solver['residual_history'])),solver['residual_history']))
            x_label='Iteration'; y_label='Relative data residual'
        validation=result['quality'] if kind!='radial_tse' else result['validation']
        if kind=='radial_tse':
            for preview in images: preview['scale_group']='echo'
            image=np.asarray(result['static_control']['image']).real
            if image.ndim==3: image=image[len(image)//2]
            images.append(dict(label='Static-model mismatch control',scale_group='static_control',width=image.shape[1],height=image.shape[0],values=image.ravel().tolist()))
    elif kind=='flow_epi':
        if result['images']:
            frame=result['images'][-1]
            for title,data in [('EPI magnitude',abs(frame['image'])),('Frozen pre-EPI magnitude reference',abs(frame['frozen_reference']))]:
                images.append(dict(label=title,scale_group='signal',width=data.shape[1],height=data.shape[0],values=data.ravel().tolist()))
            data=np.angle(frame['image']);images.append(dict(label='EPI phase (rad)',scale_group='phase',width=data.shape[1],height=data.shape[0],values=data.ravel().tolist()))
            for tissue in ['blood','wall']: curves.append(_curve(tissue,[f['encoding_start_s'] for f in result['images']],[f['pre_'+tissue+'_mz'] for f in result['images']]))
        if result['velocity_pairs']:
            pair=result['velocity_pairs'][-1]
            for title,key,group in [('Wrapped phase velocity (m/s); use validity mask','velocity_m_s','velocity'),
                    ('Gradient-moment flow reference (m/s)','gradient_moment_reference_m_s','velocity'),('Measured signal validity (0/1)','valid_mask','validity')]:
                data=np.asarray(pair[key],float);images.append(dict(label=title,scale_group=group,width=data.shape[1],height=data.shape[0],values=data.ravel().tolist()))
        x_label='Encoding start (s)';y_label='Pre-excitation volume-weighted Mz';validation=result['validation']
    elif kind in {'flow','pulsatile_flow'}:
        for tissue in (['blood','wall'] if result['readouts'] else []):
            curves.append(_curve(tissue,[r['gate']['readout_s'] for r in result['readouts']],
                [r['tissues'][tissue]['mean_mz'] for r in result['readouts']]))
        x_label='Readout time (s)'; y_label='Mean longitudinal magnetization'; validation=result['validation']
    elif kind in {'cest','cest_solomon','cest_memory'}:
        for name,z in result['spectra'].items(): curves.append(_curve(name,result['offsets_ppm'],z))
        x_label='Saturation offset (ppm)'; y_label='Water Z'; validation=result['validation']
    else:
        freq=np.fft.fftshift(np.fft.fftfreq(len(result['signal']),result['design']['dwell_s']))
        for name,fid in [('Sample',result['signal']),('Fitted',result['fit']['prediction'])]:
            curves.append(_curve(name,freq,abs(np.fft.fftshift(np.fft.fft(fid)))))
        x_label='Frequency relative to water (Hz)'; y_label='Spectrum magnitude'; validation=result['validation']
    if kind=='mrs_press':
        for name,localized in zip(result['names'],result['localization']):
            plane=abs(localized['spatial_response'][len(localized['spatial_response'])//2])
            images.append(dict(label=f'{name} localization at z=0',width=plane.shape[1],height=plane.shape[0],values=plane.ravel().tolist()))
    if kind=='tse':
        metrics={'Image NRMSE':result['quality']['nrmse'],'PSF prediction NRMSE':result['psf_prediction_quality']['nrmse']}
    elif kind=='radial_tse':
        metrics={'Image NRMSE':result['quality']['nrmse'],'Component NRMSE':validation['coefficient_error'],
            'Data residual':validation['data_residual'],'ROI contrast':validation['roi_contrast'],
            'RF energy proxy':validation['rf_energy_relative'],'Static-control NRMSE':result['static_control']['quality']['nrmse']}
    elif kind=='noncartesian':
        metrics={'Image NRMSE':result['quality']['nrmse']}
        if result['solvers']: metrics.update({'Data residual':result['solvers'][0]['relative_data_residual'],'Iterations':result['solvers'][0]['iterations']})
    elif kind=='flow_epi':
        metrics={'Completed EPI images':validation['completed_images'],'Complete opposite-sign pairs':validation['completed_encoding_pairs'],
            'Interrupted fraction':validation['interrupted_fraction'],'Peak readout/encoding gradient (T/m)':result['provenance']['waveform']['peak_gradient_t_m'],
            'Nominal readout/encoding slew (T/m/s)':result['provenance']['waveform']['nominal_slew_t_m_s']}
        for field,title in [('max_velocity_rmse_m_s','Velocity RMSE vs moment reference (m/s)'),('max_frozen_image_error','Complex frozen-reference NRMSE'),
                            ('max_abs_blood_mz','Blood max |Mz|'),('min_abs_wall_mz','Wall min |Mz|')]:
            if field in validation: metrics[title]=validation[field]
        if result['velocity_pairs']:
            pair=result['velocity_pairs'][-1];metrics['Observed blood fraction']=pair['observed_blood_fraction']
            if pair['measured_grid_flow_m3_s'] is not None: metrics['Measured grid flow (m3/s)']=pair['measured_grid_flow_m3_s']
            metrics['Moment-reference grid flow (m3/s)']=pair['moment_reference_grid_flow_m3_s']
    elif kind=='pulsatile_flow':
        metrics={'Completed readouts':validation['completed_readouts'],'Interrupted preparations':validation['interrupted_preparations'],'Interrupted fraction':validation['interrupted_fraction']}
        if result['readouts']: metrics.update({'Blood max |Mz|':validation['max_abs_blood_mz'],'Wall min |Mz|':validation['min_abs_wall_mz']})
    elif kind=='flow': metrics={'Blood max |Mz|':validation['max_abs_blood_mz'],'Wall min |Mz|':validation['min_abs_wall_mz']}
    elif kind in {'cest','cest_solomon','cest_memory'}: metrics=result['metrics']
    else: metrics={'Max relative amount error':validation['max_relative_amount_error'],'Fit residual':result['fit']['relative_residual'],'Basis condition':result['fit']['basis_condition']}
    if kind=='mrs_press': metrics.update({'RF refinement error':validation['max_rf_error'],'Grid refinement error':validation['max_refinement_error'],'Expanded FOV error':validation['max_fov_error'],'Outside-voxel power fraction':validation['max_leakage_power_fraction']})
    if kind=='mrs_quantum': metrics.update({'RF refinement error':validation['max_rf_error'],'Physical density error':validation['max_state_error'],
        'Periodic return error':validation['max_periodic_return_error'],'Minimum retained signal fraction':validation['min_signal_fraction']})
    return dict(images=images,curves=curves,x_label=x_label,y_label=y_label,validation=validation,metrics=metrics)


def execute(request, fingerprint):
    if request.expected_source_hash and request.expected_source_hash!=fingerprint:
        raise HTTPException(409,'Replay source changed. Use the original source anchor to replay this record.')
    parameters=parameters_for(request.kind,request.parameters)
    try: result=RUNNERS[request.kind](**parameters)
    except (ValueError,TypeError) as exc: raise HTTPException(422,detail=str(exc)) from exc
    replay=dict(kind=request.kind,parameters=result['provenance']['replay'],expected_source_hash=fingerprint)
    # Pure JSON is shared by the live viewport, export and replay.
    response=serializable(dict(kind=request.kind,result=result,view=present(request.kind,result),
        replay_request=replay,source_hash=fingerprint,runtime=dict(python=platform.python_version(),numpy=np.__version__)))
    response['result_hash']=sha256(json.dumps(response['result'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    return response


@router.post('/run')
def run_research(request: RunRequest): return execute(request,checked_source_hash())


@router.post('/search')
def search_research(request: SearchRequest):
    fingerprint=checked_source_hash()
    if request.expected_source_hash and request.expected_source_hash!=fingerprint: raise HTTPException(409,'Replay source changed')
    if request.kind=='radial_tse' and any(set(patch)-{'echoes','echo_spacing_s','tr_s','refocusing_angle','refocusing_end_angle','echo_order'} for patch in request.candidates):
        raise HTTPException(422,'Radial TSE search varies pulse/echo schedule only; tissue priors, basis assumptions, targets and numerical resolution remain fixed.')
    if request.kind=='mrs_press' and any(set(patch)-{'echo_s','rf_duration_s'} for patch in request.candidates):
        raise HTTPException(422,'PRESS design search varies pulse timing only; basis, molecular priors and numerical resolution remain fixed.')
    if request.kind=='flow_epi' and any(set(patch)-{'inversion_time_s','venc_m_s','dwell_s'} for patch in request.candidates):
        raise HTTPException(422,'Flow-EPI search varies timing, VENC and dwell only; pressure, preparation control, targets, quadrature and gradient limits remain fixed.')
    if request.kind=='cest_memory' and any(set(patch)-{'b1_uT','pulse_s','gap_s','n_pulses','shape','phase_cycle_rad'} for patch in request.candidates):
        raise HTTPException(422,'Finite-memory CEST search varies RF waveform only; molecular/lineshape priors, numerical grids, targets and budgets remain fixed.')
    if request.kind=='mrs_quantum' and any(set(patch)-{'echo_s','repetition_s','rf_duration_s','excitation_degrees'} for patch in request.candidates):
        raise HTTPException(422,'Quantum MRS search varies pulse/echo/TR only; preparation, basis, molecular priors, numerical grids, targets and budgets remain fixed.')
    if request.kind=='cest_solomon':
        pulse_keys={'b1_uT','saturation_s','mode','n_pulses','pulse_s','gap_s'}
        if any(set(patch)-pulse_keys for patch in request.candidates):
            raise HTTPException(422,'Solomon design search varies saturation pulse parameters only. Molecular parameters are priors; use separate runs for sensitivity.')
    # Reject typos, unsafe budgets or unsupported fields before any computation.
    for patch in request.candidates: parameters_for(request.kind,{**request.parameters,**patch})
    points=[]
    for patch in request.candidates:
        try:
            run=execute(RunRequest(kind=request.kind,parameters={**request.parameters,**patch}),fingerprint)
            result=run['result']; loss=result.get('objective_loss',result.get('quality',{}).get('nrmse',result.get('validation',{}).get('max_relative_amount_error')))
            points.append(dict(parameters=patch,feasible=True,loss=loss,run=run))
        except HTTPException as exc:
            if exc.status_code!=422: raise
            points.append(dict(parameters=patch,feasible=False,reason=exc.detail))
    feasible=[p for p in points if p['feasible']]
    eligible=[p for p in feasible if p['run']['view']['validation']['passed']] if request.kind in {'radial_tse','flow_epi','cest_memory','mrs_quantum'} else feasible
    best=min(eligible,key=lambda p:p['loss']) if eligible else None
    return dict(kind=request.kind,candidates=points,best=best,
        objective='minimize RF energy proxy among candidates passing all declared targets; finite grid, no clinical optimum' if request.kind in {'radial_tse','cest_memory'} else 'minimize TR among candidates passing amount, residual, retained signal and numerical targets; finite grid, no clinical optimum' if request.kind=='mrs_quantum' else 'minimize declared velocity+image error and interrupted fraction among candidates passing every target; finite grid, no clinical optimum' if request.kind=='flow_epi' else 'minimize declared model loss against known teaching truth/control; finite grid, no clinical optimum',
        replay_search={**request.model_dump(), 'expected_source_hash':fingerprint},source_hash=fingerprint,
        search_hash=sha256(json.dumps(points,sort_keys=True,allow_nan=False).encode()).hexdigest())


# Measured study records wrap existing ExperimentGraphs; they are not a new
# scanner export or licensed-compute path.
from mrqlab_experiment.lab_study import LabStudy, build_lab_study_example, import_echo_csv
from mrqlab_experiment.study_records import create_study_record, replay_study_record


class EchoCSVRequest(StrictParameters):
    csv_base64: str=Field(min_length=1,max_length=1333340)
    source_ref: str=Field(min_length=1,max_length=1024)
    origin: Literal['synthetic','measured']
    echo_spacing_s: float=Field(default=.008,ge=.000001,le=10.)
    tr_s: float=Field(default=.4,ge=.000001,le=10.)


@router.get('/lab-study/example')
def lab_study_example():
    return build_lab_study_example().model_dump(mode='json')


@router.post('/lab-study/import-echoes')
def lab_study_import(request: EchoCSVRequest):
    try:
        dataset=import_echo_csv(base64.b64decode(request.csv_base64,validate=True),source_ref=request.source_ref,
            origin=request.origin,echo_spacing_s=request.echo_spacing_s,tr_s=request.tr_s)
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc
    return dataset.model_dump(mode='json')


def _lab_response(record):
    simulation=record['result']['selected_simulation']
    def decode(value):
        if isinstance(value,dict):
            if set(value)=={'real','imag'}: return complex(value['real'],value['imag'])
            return {k:decode(v) for k,v in value.items()}
        if isinstance(value,list): return [decode(v) for v in value]
        return value
    return dict(record=record,view=present('tse',decode(simulation)) if simulation is not None else None)


@router.post('/lab-study/run')
def run_measured_study(request: LabStudy):
    checked_source_hash()
    try: return _lab_response(create_study_record(request))
    except ValueError as exc: raise HTTPException(422,str(exc)) from exc


@router.post('/lab-study/replay')
def replay_measured_study(record: dict):
    checked_source_hash()
    try: return _lab_response(replay_study_record(record))
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
