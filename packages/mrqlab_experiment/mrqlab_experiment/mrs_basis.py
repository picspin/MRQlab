"""Small-spin density-matrix spectroscopy and full-complex-readout fitting.

Declared teaching spin systems, not a validated metabolite library. Finite RF
and isotropic J evolve concurrently. Relaxation is a scalar envelope, not a
quantum relaxation superoperator. No clinical concentration calibration.
"""
from hashlib import sha256
from pathlib import Path
from itertools import combinations
import numpy as np
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from .flow_imaging import selective_sinc
from .spatial_imaging import _hash

SCOPE = ('research/teaching small-spin density matrix, finite sinc RF and J coupling; '
         'scalar T2 envelope and equilibrium preparation; no validated metabolite library, '
         'clinical concentration calibration, scanner validation or quality certification; B/C parked')


def spin_operators(count):
    if type(count) is not int or not 1 <= count <= 3: raise ValueError('one to three spin-1/2 nuclei required')
    pauli = [np.array([[0,1],[1,0]], complex)/2,
             np.array([[0,-1j],[1j,0]], complex)/2,
             np.diag([1.,-1.])/2]
    out = []
    for spin in range(count):
        axes = []
        for matrix in pauli:
            op = np.ones((1,1), complex)
            for index in range(count): op = np.kron(op, matrix if spin == index else np.eye(2))
            axes.append(op)
        out.append(axes)
    return out


def spin_hamiltonian(offsets_hz, couplings_hz, *, coupling_model='isotropic'):
    frequencies = np.asarray(offsets_hz, float); j = np.asarray(couplings_hz, float)
    if frequencies.ndim != 1 or not np.isfinite(frequencies).all(): raise ValueError('finite offsets required')
    ops = spin_operators(len(frequencies))
    if j.shape != (len(ops),len(ops)) or not np.isfinite(j).all() or not np.allclose(j,j.T) or np.any(np.diag(j) != 0):
        raise ValueError('finite symmetric J matrix with zero diagonal required')
    if coupling_model not in {'isotropic','secular'}: raise ValueError('unsupported coupling model')
    h = sum(2*np.pi*f*axes[2] for f,axes in zip(frequencies,ops))
    for a,b in combinations(range(len(ops)),2):
        for axis in (range(3) if coupling_model == 'isotropic' else [2]):
            h += 2*np.pi*j[a,b]*(ops[a][axis] @ ops[b][axis])
    return h, ops


def _unitary(h, duration):
    values, vectors = np.linalg.eigh(h)
    return (vectors*np.exp(-1j*values*duration)) @ vectors.conj().T


def simulate_density_fid(offsets_hz, couplings_hz, *, echo_s=.03, dwell_s=.0005,
                         points=512, rf_duration_s=.001, rf_steps=64,
                         thickness_m=.02, position_m=(0.,0.,0.), t2_s=.15,
                         coupling_model='isotropic', max_work=10000000):
    """Two-refocuser teaching sequence; no crusher/coherence-pathway selection.

    Pulse centers relative to excitation center: 0, TE/4, 3TE/4; echo at TE.
    Three slice gradients act on x/y/z respectively. Positions are explicit
    single isochromats; this is not a converged 3D PRESS localization integral.
    """
    if type(points) is not int or not 16 <= points <= 4096 or type(rf_steps) is not int or not 16 <= rf_steps <= 1024:
        raise ValueError('bounded integer FID and RF sample counts required')
    if not np.isfinite([echo_s,dwell_s,rf_duration_s,thickness_m,t2_s,*position_m]).all() or min(dwell_s,rf_duration_s,thickness_m,t2_s) <= 0 or echo_s <= 6*rf_duration_s or len(position_m) != 3:
        raise ValueError('finite positive design and nonoverlapping finite RF pulses required')
    if type(max_work) is not int or max_work <= 0: raise ValueError('positive integer work budget required')
    h, ops = spin_hamiltonian(offsets_hz,couplings_hz,coupling_model=coupling_model)
    frequencies = np.asarray(offsets_hz)
    # Conservative bound on highest possible transition frequency.
    bandwidth = 2*(np.sum(abs(frequencies))+np.sum(abs(np.asarray(couplings_hz)))/2)
    if bandwidth >= 1/dwell_s: raise ValueError('spectral transitions exceed Nyquist; shorten dwell')
    dimension = len(h); work = dimension**3*(3*rf_steps*4+12)+points*dimension**2
    if work > max_work: raise ValueError('density-matrix work budget exceeded')
    x = sum(a[0] for a in ops); y = sum(a[1] for a in ops); z = sum(a[2] for a in ops)
    rho = z/np.trace(z@z).real
    detection = x+1j*y
    rf = selective_sinc(90.,duration_s=rf_duration_s,thickness_m=thickness_m,steps=rf_steps)
    elapsed = 0.; timeline = []
    centers = [rf_duration_s/2, echo_s/4+rf_duration_s/2, 3*echo_s/4+rf_duration_s/2]
    for index,(flip,phase) in enumerate([(90.,0.),(180.,np.pi/2),(180.,np.pi/2)]):
        start = centers[index]-rf_duration_s/2
        if start > elapsed:
            u = _unitary(h,start-elapsed); rho = u@rho@u.conj().T
        for b1 in rf['b1_uT']*flip/90:
            h_rf = h+2*np.pi*GAMMA_BAR_HZ_T*b1*1e-6*(np.cos(phase)*x+np.sin(phase)*y)
            h_rf += 2*np.pi*GAMMA_BAR_HZ_T*rf['gz_t_m']*position_m[index]*z
            u = _unitary(h_rf,rf['dt_s']); rho = u@rho@u.conj().T
        elapsed = start+rf_duration_s
        timeline.append(dict(start_s=start,end_s=elapsed,flip_degrees=flip,phase_rad=phase,gradient_axis='xyz'[index]))
    echo_time = echo_s+rf_duration_s/2
    u = _unitary(h,echo_time-elapsed); rho = u@rho@u.conj().T
    # Exact free evolution in the Hamiltonian eigenbasis; no FID time stepping.
    eigen, vectors = np.linalg.eigh(h)
    rotated = vectors.conj().T@rho@vectors
    detect = vectors.conj().T@detection@vectors
    times = np.arange(points)*dwell_s
    transitions = eigen[:,None]-eigen[None,:]
    coefficients = rotated*detect.T
    fid = np.sum(coefficients[:,:,None]*np.exp(-1j*transitions[:,:,None]*times),axis=(0,1))
    fid *= np.exp(-(echo_time+times)/t2_s)
    return fid, dict(timeline=timeline,echo_time_s=echo_time,estimated_work=work,
        hermiticity_error=float(np.max(abs(rho-rho.conj().T))),trace_real=float(np.trace(rho).real),
        rf_hash=_hash(rf['b1_uT'].tolist()),coupling_model=coupling_model,
        normalization='unit initial total longitudinal polarization; signal amount, not molarity')


def fit_full_basis(signal, basis, *, phase_grid_rad=(0.,), shift_grid_hz=(0.,),
                   dwell_s=.0005, max_relative_residual=.02):
    """Nonnegative real amounts, exhaustive active subsets, complex FID LS.

    Full-FID LS is equivalent to full-spectrum LS by Parseval. No peak windows
    or per-metabolite rescaling. Phase/frequency are an explicit finite grid.
    Condition/rank describe this fixed basis; no concentration uncertainty claim.
    """
    signal=np.asarray(signal,complex); basis=np.asarray(basis,complex)
    if signal.ndim != 1 or basis.ndim != 2 or basis.shape[0] != len(signal) or not 1 <= basis.shape[1] <= 6 or not np.isfinite(signal).all() or not np.isfinite(basis).all():
        raise ValueError('finite FID and one to six full basis columns required')
    phases=np.asarray(phase_grid_rad,float); shifts=np.asarray(shift_grid_hz,float)
    if phases.ndim != 1 or shifts.ndim != 1 or not 1 <= len(phases)*len(shifts) <= 81 or not np.isfinite(phases).all() or not np.isfinite(shifts).all() or not np.isfinite([dwell_s,max_relative_residual]).all() or min(dwell_s,max_relative_residual)<=0:
        raise ValueError('bounded finite phase/shift grid, positive dwell/target required')
    norm=np.linalg.norm(signal)
    if norm == 0: raise ValueError('nonzero signal required')
    real_design=np.vstack([basis.real,basis.imag])
    rank=int(np.linalg.matrix_rank(real_design)); condition=float(np.linalg.cond(real_design))
    if rank < basis.shape[1] or condition > 1e10: raise ValueError('basis is rank deficient or ill conditioned')
    best=None; times=np.arange(len(signal))*dwell_s
    for phase in phases:
        for shift in shifts:
            design=basis*np.exp(1j*(phase+2*np.pi*shift*times))[:,None]
            a=np.vstack([design.real,design.imag]); b=np.r_[signal.real,signal.imag]
            for mask in range(1<<basis.shape[1]):
                active=[i for i in range(basis.shape[1]) if mask&(1<<i)]
                amounts=np.zeros(basis.shape[1])
                if active:
                    values=np.linalg.lstsq(a[:,active],b,rcond=None)[0]
                    if np.any(values < 0): continue
                    amounts[active]=values
                prediction=design@amounts; loss=float(np.linalg.norm(prediction-signal)/norm)
                if best is None or loss < best['relative_residual']:
                    best=dict(amounts=amounts.tolist(),relative_residual=loss,
                        phase_rad=float(phase),shift_hz=float(shift),prediction=prediction,
                        passed=loss<=max_relative_residual,threshold=max_relative_residual,
                        basis_rank=rank,basis_condition=condition)
    return best


def run_mrs_basis(*, echo_s=.03, points=512, dwell_s=.0005, rf_steps=64,
                  rf_duration_s=.001, amounts=(.02,.015,.01,.008),
                  noise_std=0., seed=7, phase_rad=0., shift_hz=0.,
                  fit_phase_grid_rad=(0.,), fit_shift_grid_hz=(0.,),
                  basis_j_hz=7., sample_j_hz=7., max_work=100000000,
                  target_relative_amount_error=.05):
    """Declared spin systems -> sample/basis simulation -> full fit -> replay.

    NAA/Cr/Cho are teaching singlets; coupled pair is explicitly synthetic,
    not lactate or another real molecule. Amounts are relative signal amounts.
    Water uses the same finite pulse sequence with declared water T2=.2 s.
    """
    amounts=np.asarray(amounts,float)
    if amounts.shape!=(4,) or not np.isfinite(amounts).all() or np.any(amounts<=0): raise ValueError('four positive teaching amounts required')
    if not np.isfinite([noise_std,phase_rad,shift_hz,basis_j_hz,sample_j_hz,target_relative_amount_error]).all() or noise_std<0 or target_relative_amount_error<=0 or type(seed) is not int:
        raise ValueError('finite sample/fit controls, nonnegative noise and integer seed required')
    if type(max_work) is not int or max_work<=0: raise ValueError('positive integer work budget required')
    names=['NAA_singlet','Cr_singlet','Cho_singlet','synthetic_AB']
    frequencies=[[-343.6],[-213.3],[-190.3],[-300.,-270.]]
    fit_work = len(fit_phase_grid_rad)*len(fit_shift_grid_hz)*16*points*64+8*points
    if fit_work >= max_work: raise ValueError('full-fit work budget exceeded')
    basis=[]; sample=[]; records=[]; work=fit_work
    def simulate(freq,j,t2):
        nonlocal work
        fid,record=simulate_density_fid(freq,j,echo_s=echo_s,points=points,dwell_s=dwell_s,
            rf_steps=rf_steps,rf_duration_s=rf_duration_s,t2_s=t2,max_work=max_work-work)
        work+=record['estimated_work']; records.append(record)
        return fid
    for i,freq in enumerate(frequencies):
        j=np.zeros((len(freq),len(freq)))
        if len(freq)==2: j[0,1]=j[1,0]=basis_j_hz
        basis.append(simulate(freq,j,.15))
        if len(freq)==2 and sample_j_hz!=basis_j_hz:
            j[0,1]=j[1,0]=sample_j_hz; sample.append(simulate(freq,j,.15))
        else: sample.append(basis[-1])
    basis=np.array(basis).T; clean=np.array(sample).T@amounts
    times=np.arange(points)*dwell_s
    clean*=np.exp(1j*(phase_rad+2*np.pi*shift_hz*times))
    rng=np.random.default_rng(seed); signal=clean+noise_std*(rng.normal(size=points)+1j*rng.normal(size=points))
    fit=fit_full_basis(signal,basis,phase_grid_rad=fit_phase_grid_rad,shift_grid_hz=fit_shift_grid_hz,dwell_s=dwell_s)
    water=simulate([0.],[[0.]],.2)
    water_fit=fit_full_basis(water,water[:,None],dwell_s=dwell_s)
    recovered=np.asarray(fit['amounts']); error=float(np.max(abs(recovered/amounts-1)))
    inputs=dict(echo_s=echo_s,points=points,dwell_s=dwell_s,rf_steps=rf_steps,
        rf_duration_s=rf_duration_s,amounts=amounts.tolist(),noise_std=noise_std,seed=seed,
        phase_rad=phase_rad,shift_hz=shift_hz,fit_phase_grid_rad=list(fit_phase_grid_rad),
        fit_shift_grid_hz=list(fit_shift_grid_hz),basis_j_hz=basis_j_hz,sample_j_hz=sample_j_hz,
        max_work=max_work,target_relative_amount_error=target_relative_amount_error)
    return dict(clinical_question='How do finite RF bandwidth, J coupling and basis mismatch affect water-referenced teaching spectral amounts?',
        design=inputs,names=names,signal=signal,basis=basis,water=water,fit=fit,
        teaching_truth=amounts,water_referenced_signal_amounts=(recovered/water_fit['amounts'][0]).tolist(),
        validation=dict(max_relative_amount_error=error,target=target_relative_amount_error,
            passed=error<=target_relative_amount_error and fit['passed']),scope=SCOPE,
        provenance=dict(version='density-basis-v1',replay=inputs,input_hash=_hash(inputs),
            source_hash=sha256(Path(__file__).read_bytes()).hexdigest(),
            basis_hash=_hash([basis.real.tolist(),basis.imag.tolist()]),
            signal_hash=_hash([signal.real.tolist(),signal.imag.tolist()]),
            estimated_work=work,estimated_fit_work=fit_work,simulations=records,water_reference_t2_s=.2,
            fit_convention='full complex FID LS, nonnegative amounts; fixed-basis synthetic recovery is not clinical calibration'))


def search_mrs_echo(candidates_s, **kwargs):
    candidates=list(candidates_s)
    if not candidates or len(candidates)>32 or 'echo_s' in kwargs: raise ValueError('bounded echo grid required')
    points=[]
    for te in candidates:
        try:
            r=run_mrs_basis(echo_s=te,**kwargs)
            points.append(dict(echo_s=te,feasible=True,result=r))
        except ValueError as exc:
            points.append(dict(echo_s=te,feasible=False,reason=str(exc)))
    feasible=[p for p in points if p['feasible']]
    return dict(candidates=points,best=min(feasible,key=lambda p:p['result']['validation']['max_relative_amount_error']) if feasible else None,
        objective='minimize known synthetic maximum relative amount error; finite grid only')
