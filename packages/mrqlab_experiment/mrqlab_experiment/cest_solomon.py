"""CEST/MT with a distance/tau-derived Solomon -> chemical-exchange relay.

Donor and bridge are one-to-one paired protons at equal authored densities.
Donor never chemically exchanges with water. This minimal pair is not a full
molecular spin-diffusion network or a clinical concentration calibration.
"""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import numpy as np
import platform
from mrqlab_physics.models import LiquidPoolSystem
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.ops.dipolar_solomon import dipolar_pair_rates,add_solomon_pair
from mrqlab_physics.ops.cest_saturation import _matrix_exp,validate_cest_timing
from .cest_mt_noe import joint_generator
from .spatial_imaging import _hash

SCOPE=('research/teaching homogeneous CEST/MT plus high-field isotropic Solomon proton-pair relay; '
       'distance/tau-derived signed longitudinal cross-relaxation, background T2 plus spin-flip rho/2; '
       'not full Redfield coherence/spin diffusion, patient calibration, scanner validation or clinical certification; B/C parked')


_SOURCE_PATHS=[Path(__file__),Path(joint_generator.__code__.co_filename),Path(dipolar_pair_rates.__code__.co_filename),
    Path(_matrix_exp.__code__.co_filename),Path(dipolar_pair_rates.__code__.co_filename).parent/'super_lorentzian.py',
    Path(dipolar_pair_rates.__code__.co_filename).parent.parent/'kernel/units.py',
    Path(dipolar_pair_rates.__code__.co_filename).parent.parent/'models.py']


def _source_files():
    root=Path(__file__).resolve().parents[3]
    return {p.resolve().relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in _SOURCE_PATHS}


IMPORTED_SOURCE_HASH=_hash(_source_files())


def relay_pool_system(*,b0_t=3.,pair_fraction=.02,bridge_exchange_s1=1000.,
                        bridge_shift_ppm=1.,donor_shift_ppm=-3.5,amide_exchange=True):
    if not np.isfinite([b0_t,pair_fraction,bridge_exchange_s1,bridge_shift_ppm,donor_shift_ppm]).all() or b0_t<=0 or not 0<pair_fraction<=.2 or bridge_exchange_s1<0:
        raise ValueError('finite positive field/pair density and nonnegative bridge exchange required')
    density=np.array([1.,.003,.005,pair_fraction,pair_fraction]); rates=np.zeros((5,5))
    for i,k in enumerate([30. if amide_exchange else 0.,200.,bridge_exchange_s1],1):
        rates[0,i]=density[i]*k; rates[i,0]=k
    shifts=np.array([0.,3.5,2.,bridge_shift_ppm,donor_shift_ppm])
    return LiquidPoolSystem((1.5,1.,1.,1.,1.),(.08,.02,.01,.01,.0005),
        tuple(density),tuple(shifts*GAMMA_BAR_HZ_T*b0_t*1e-6),tuple(map(tuple,rates)))


def relay_generator(system,offset_hz,b1_uT,rates,*,cross_relaxation=True,**bound):
    return add_solomon_pair(joint_generator(system,offset_hz,b1_uT,**bound),system,3,4,rates,cross_relaxation=cross_relaxation)


def run_cest_solomon(*,offsets_ppm=(-5.,-3.5,-2.,-1.,1.,2.,3.5,5.),
                     b0_t=3.,b1_uT=1.,saturation_s=1.,mode='cw',n_pulses=1,pulse_s=1.,gap_s=0.,
                     pair_fraction=.02,bridge_exchange_s1=1000.,bridge_shift_ppm=1.,donor_shift_ppm=-3.5,
                     distance_m=2.5e-10,tau_c_s=1e-8,bound_fraction=.08,bound_to_water_hz=20.,
                     bound_t2_s=12e-6,lineshape='super_lorentzian',max_work=100000000,max_duration_s=300.,
                     target_min_amide_contrast=.005,target_min_relay_contrast=.005):
    sources=_source_files()
    if _hash(sources)!=IMPORTED_SOURCE_HASH: raise ValueError('Solomon model source changed since import; restart before recording or replaying')
    offsets=np.asarray(offsets_ppm,float)
    if offsets.ndim!=1 or not 2<=len(offsets)<=128 or not np.isfinite(offsets).all() or len(np.unique(offsets))!=len(offsets):
        raise ValueError('2..128 distinct finite offsets required')
    if any(np.count_nonzero(np.isclose(offsets,x))!=1 for x in [3.5,donor_shift_ppm]):
        raise ValueError('one amide +3.5 ppm and one donor-resonant sample required')
    if np.isclose(donor_shift_ppm,3.5): raise ValueError('donor and amide metric samples must differ')
    if not np.isfinite([b1_uT,max_duration_s,target_min_amide_contrast,target_min_relay_contrast]).all() or min(b1_uT,max_duration_s,target_min_amide_contrast,target_min_relay_contrast)<=0:
        raise ValueError('positive finite RF, duration budget and targets required')
    if type(max_work) is not int or max_work<=0: raise ValueError('positive integer work budget required')
    rates=dipolar_pair_rates(b0_t=b0_t,distance_m=distance_m,tau_c_s=tau_c_s,shifts_ppm=(bridge_shift_ppm,donor_shift_ppm))
    timing=validate_cest_timing(dict(mode=mode,saturation_duration_s=saturation_s,n_pulses=n_pulses,pulse_duration_s=pulse_s,gap_duration_s=gap_s))
    _,count,pulse,gap,elapsed,duty=timing
    if count>1000: raise ValueError('at most 1000 pulses required')
    # All pool amounts and self relaxation retained in these conditional controls.
    controls=dict(full=(True,True,True,True),no_cross=(False,True,True,True),
        no_bridge_exchange=(True,False,True,True),no_amide=(True,True,False,True),no_mt=(True,True,True,False))
    duration=(len(controls)*len(offsets)+1)*elapsed
    if duration>max_duration_s: raise ValueError('all-offset/control duration budget exceeded')
    spectra={}; states={}; work=0; reference=None
    for name,(cross,bridge,amide,mt) in controls.items():
        system=relay_pool_system(b0_t=b0_t,pair_fraction=pair_fraction,bridge_exchange_s1=bridge_exchange_s1 if bridge else 0.,
            bridge_shift_ppm=bridge_shift_ppm,donor_shift_ppm=donor_shift_ppm,amide_exchange=amide)
        initial=np.zeros(3*system.count+2); initial[2:3*system.count:3]=system.density; initial[-2]=bound_fraction; initial[-1]=1.
        bound=dict(bound_fraction=bound_fraction,bound_to_water_hz=bound_to_water_hz if mt else 0.,bound_t2_s=bound_t2_s,lineshape=lineshape)
        z=[]; retained=[]
        for ppm in offsets:
            hz=float(ppm*GAMMA_BAR_HZ_T*b0_t*1e-6)
            g=relay_generator(system,hz,b1_uT,rates,cross_relaxation=cross,**bound)
            free=relay_generator(system,hz,0.,rates,cross_relaxation=cross,**bound)
            scaling=lambda a,t:max(0,int(np.ceil(np.log2(max(float(np.linalg.norm(a,np.inf)*t),1.)))))
            cost=len(initial)**3*((80+scaling(g,pulse))*count+(80+scaling(free,gap))*(count-1 if gap>0 else 0))
            if work+cost>max_work: raise ValueError('Solomon CEST exponential work budget exceeded')
            work+=cost; prop=_matrix_exp(g,pulse); wait=_matrix_exp(free,gap) if gap>0 and count>1 else None
            state=initial.copy()
            for i in range(count):
                state=prop@state
                if wait is not None and i+1<count: state=wait@state
            if not np.isfinite(state).all(): raise ValueError('nonfinite Solomon CEST state')
            z.append(float(state[2])); retained.append(state.tolist())
        spectra[name]=z; states[name]=retained
        if name=='full':
            g0=relay_generator(system,0.,0.,rates,**bound)
            cost=len(initial)**3*(80+scaling(g0,elapsed))
            if work+cost>max_work: raise ValueError('unsaturated reference work budget exceeded')
            work+=cost; reference=float((_matrix_exp(g0,elapsed)@initial)[2])
    plus=int(np.flatnonzero(np.isclose(offsets,3.5))[0]); donor=int(np.flatnonzero(np.isclose(offsets,donor_shift_ppm))[0])
    metrics=dict(amide_exchange_contrast=float(spectra['no_amide'][plus]-spectra['full'][plus]),
        relayed_noe_contrast=float(spectra['no_cross'][donor]-spectra['full'][donor]),
        bridge_exchange_control_contrast=float(spectra['no_bridge_exchange'][donor]-spectra['full'][donor]),
        mt_contrast_at_amide=float(spectra['no_mt'][plus]-spectra['full'][plus]),
        donor_minus_amide=float(spectra['full'][donor]-spectra['full'][plus]),unsaturated_water=reference)
    inputs=dict(offsets_ppm=offsets.tolist(),b0_t=b0_t,b1_uT=b1_uT,saturation_s=saturation_s,mode=mode,
        n_pulses=n_pulses,pulse_s=pulse_s,gap_s=gap_s,pair_fraction=pair_fraction,bridge_exchange_s1=bridge_exchange_s1,
        bridge_shift_ppm=bridge_shift_ppm,donor_shift_ppm=donor_shift_ppm,distance_m=distance_m,tau_c_s=tau_c_s,
        bound_fraction=bound_fraction,bound_to_water_hz=bound_to_water_hz,bound_t2_s=bound_t2_s,lineshape=lineshape,
        max_work=max_work,max_duration_s=max_duration_s,target_min_amide_contrast=target_min_amide_contrast,
        target_min_relay_contrast=target_min_relay_contrast)
    return dict(clinical_question='How do distance and molecular correlation time alter signed dipolar NOE relayed through labile exchange into water CEST/MT?',
        design=inputs,offsets_ppm=offsets.tolist(),spectra=spectra,metrics=metrics,scope=SCOPE,
        objective_loss=-metrics['relayed_noe_contrast'],validation=dict(target_min_amide_contrast=target_min_amide_contrast,
            target_min_relay_contrast=target_min_relay_contrast,passed=metrics['amide_exchange_contrast']>=target_min_amide_contrast and metrics['relayed_noe_contrast']>=target_min_relay_contrast),
        provenance=dict(version='solomon-relay-cest-v1',replay=inputs,input_hash=_hash(inputs),
            source_hash=IMPORTED_SOURCE_HASH,source_files=sources,states_hash=_hash(states),
            runtime=dict(python=platform.python_version(),numpy=np.__version__),
            dipolar_rates=rates,liquid_system=asdict(relay_pool_system(b0_t=b0_t,pair_fraction=pair_fraction,
                bridge_exchange_s1=bridge_exchange_s1,bridge_shift_ppm=bridge_shift_ppm,donor_shift_ppm=donor_shift_ppm)),
            controls={name:list(value) for name,value in controls.items()},estimated_work=work,duration_s=duration,duty_cycle=duty,
            rf_energy_uT2_s=len(controls)*len(offsets)*b1_uT*b1_uT*count*pulse,
            state_convention='3 Cartesian components per liquid; bound Z; affine 1; each offset starts at equilibrium',
            transverse_model='authored background T2 plus rho/2 spin-flip relaxation; dipolar pure dephasing not derived',
            bound_lineshape=lineshape,normalization='declared water equilibrium density 1; no gain fit or sign clipping'))
