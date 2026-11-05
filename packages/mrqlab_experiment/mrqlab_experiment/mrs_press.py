"""Finite-RF PRESS pathway and complex 3D volume quadrature.

Ideal coherence selection (-1,+1,-1), not scanner crusher firmware. Small
teaching spin systems; scalar T2 envelope, no clinical concentration calibration.
"""
import numpy as np
from pathlib import Path
from hashlib import sha256
import platform
from .mrs_basis import spin_hamiltonian,_unitary,fit_full_basis
from .flow_imaging import selective_sinc
from .spatial_imaging import _hash
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T


_SOURCE_PATHS=[Path(__file__),Path(spin_hamiltonian.__code__.co_filename),Path(selective_sinc.__code__.co_filename),
    Path(_hash.__code__.co_filename),Path(__file__).resolve().parents[2]/'physics/mrqlab_physics/kernel/units.py']


def _sources():
    root=Path(__file__).resolve().parents[3]
    return {p.resolve().relative_to(root).as_posix():sha256(p.read_bytes()).hexdigest() for p in _SOURCE_PATHS}


IMPORTED_SOURCE_HASH=_hash(_sources())


def coherence_mask(total_z,order):
    if type(order) is not int: raise ValueError('integer coherence order required')
    m=np.diag(total_z).real
    return np.isclose(m[:,None]-m[None,:],order,atol=1e-12)


def selected_pulse(rho,unitary,total_z,incoming,outgoing,method='projection'):
    if method=='projection':
        return (unitary@rho@np.swapaxes(unitary.conj(),-1,-2))*coherence_mask(total_z,outgoing)
    if method!='phase_cycle': raise ValueError('projection or phase_cycle required')
    # Exact Fourier extraction for all orders supported by this spin space.
    phases=np.arange(2*int(round(np.ptp(np.diag(total_z).real)))+1)*2*np.pi/(2*int(round(np.ptp(np.diag(total_z).real)))+1)
    result=0j
    for phase in phases:
        r=np.exp(-1j*phase*np.diag(total_z).real)
        u=r[:,None]*unitary*r.conj()[None,:]
        result=result+np.exp(1j*phase*(outgoing-incoming))*(u@rho@np.swapaxes(u.conj(),-1,-2))/len(phases)
    return result


def finite_pulse_unitary(h,ops,rf,position_m,*,flip=90.,phase=0.):
    x=sum(a[0] for a in ops);y=sum(a[1] for a in ops);z=sum(a[2] for a in ops)
    u=np.eye(len(h),dtype=complex)
    for b1 in rf['b1_uT']*flip/90:
        effective=h+2*np.pi*GAMMA_BAR_HZ_T*(b1*1e-6*(np.cos(phase)*x+np.sin(phase)*y)+rf['gz_t_m']*position_m*z)
        u=_unitary(effective,rf['dt_s'])@u
    return u


def simulate_press_volume(offsets_hz,couplings_hz,*,echo_s=.03,dwell_s=.0005,points=256,
                          rf_duration_s=.001,rf_steps=64,thickness_m=(.02,.02,.02),
                          grid_size=17,fov_scale=2.,t2_s=.15,selection='projection',
                          max_work=100000000,max_memory_bytes=134217728):
    if _hash(_sources())!=IMPORTED_SOURCE_HASH: raise ValueError('PRESS source changed since import; restart before recording or replaying')
    if type(grid_size) is not int or not 3<=grid_size<=65 or grid_size%2!=1 or type(points) is not int or not 16<=points<=4096 or type(rf_steps) is not int or not 16<=rf_steps<=512:
        raise ValueError('bounded odd spatial grid and integer RF/FID resolution required')
    if len(thickness_m)!=3 or not np.isfinite([echo_s,dwell_s,rf_duration_s,*thickness_m,fov_scale,t2_s]).all() or min(dwell_s,rf_duration_s,*thickness_m,t2_s)<=0 or echo_s<=6*rf_duration_s or not 1<=fov_scale<=4:
        raise ValueError('positive finite nonoverlapping pulse/volume design required')
    if selection not in {'projection','phase_cycle'}: raise ValueError('invalid coherence selection')
    if any(type(v) is not int or v<=0 for v in [max_work,max_memory_bytes]): raise ValueError('positive integer resource budgets required')
    h,ops=spin_hamiltonian(offsets_hz,couplings_hz); d=len(h); n=grid_size
    bandwidth=2*(np.sum(abs(np.asarray(offsets_hz)))+np.sum(abs(np.asarray(couplings_hz)))/2)
    if bandwidth>=1/dwell_s: raise ValueError('spectral transitions exceed Nyquist')
    phases=1 if selection=='projection' else 2*len(ops)+1
    work=int((3*n*(4*rf_steps+12)+phases*(6*n*n+6*n**3)+32)*d**3+4*points*d*d)
    memory=int(128*n*n*d*d+64*n**3+128*n*d*d+64*points*d*d)
    if work>max_work or memory>max_memory_bytes: raise ValueError('PRESS preflight work/memory budget exceeded')
    x=sum(a[0] for a in ops);y=sum(a[1] for a in ops);z=sum(a[2] for a in ops)
    rho=z/np.trace(z@z).real;det=x+1j*y
    axes=[(np.arange(n)+.5-n/2)*side*fov_scale/n for side in thickness_m]
    cells=np.array(thickness_m)*fov_scale/n;dv=float(np.prod(cells));voxel=float(np.prod(thickness_m))
    pulses=[selective_sinc(90.,duration_s=rf_duration_s,thickness_m=side,steps=rf_steps) for side in thickness_m]
    caches=[np.array([finite_pulse_unitary(h,ops,rf,p,flip=flip,phase=phase) for p in axis])
            for rf,axis,flip,phase in zip(pulses,axes,[90.,180.,180.],[0.,np.pi/2,np.pi/2])]
    rephase_duration=rf_duration_s/2
    rephase=np.array([_unitary(h-2*np.pi*GAMMA_BAR_HZ_T*pulses[0]['gz_t_m']*p*z,rephase_duration) for p in axes[0]])
    waits=[echo_s/4-1.5*rf_duration_s,echo_s/2-rf_duration_s,echo_s/4-rf_duration_s/2]
    free=[_unitary(h,t) for t in waits]
    rx=selected_pulse(rho,caches[0],z,0,-1,selection)
    rx=rephase@rx@np.swapaxes(rephase.conj(),-1,-2)
    rx=free[0]@rx@free[0].conj().T
    integrated=np.zeros_like(rho);center_state=None;spatial=np.zeros((n,n,n),complex)
    for iy in range(n):
        rxy=selected_pulse(rx,caches[1][iy],z,-1,1,selection)
        rxy=free[1]@rxy@free[1].conj().T
        for iz in range(n):
            out=selected_pulse(rxy,caches[2][iz],z,1,-1,selection)
            out=free[2]@out@free[2].conj().T
            spatial[iz,iy]=np.trace(out@det,axis1=-2,axis2=-1)
            integrated+=out.sum(axis=0)*dv
            if iy==n//2 and iz==n//2: center_state=out[n//2].copy()
    echo_time=echo_s+rf_duration_s/2;spatial*=np.exp(-echo_time/t2_s)
    eigen,vectors=np.linalg.eigh(h);rotated=vectors.conj().T@integrated@vectors;detect=vectors.conj().T@det@vectors
    times=np.arange(points)*dwell_s
    center_rotated=vectors.conj().T@center_state@vectors
    center_fid=np.sum((center_rotated*detect.T)[:,:,None]*np.exp(-1j*(eigen[:,None]-eigen[None,:])[:,:,None]*times),axis=(0,1))*np.exp(-(echo_time+times)/t2_s)
    fid=np.sum((rotated*detect.T)[:,:,None]*np.exp(-1j*(eigen[:,None]-eigen[None,:])[:,:,None]*times),axis=(0,1))*np.exp(-(echo_time+times)/t2_s)
    power=abs(spatial)**2;total=float(power.sum());zz,yy,xx=np.meshgrid(axes[2],axes[1],axes[0],indexing='ij')
    outside=(abs(xx)>thickness_m[0]/2)|(abs(yy)>thickness_m[1]/2)|(abs(zz)>thickness_m[2]/2)
    centroid=[float(np.sum(power*p)/(total or 1)) for p in [xx,yy,zz]]
    return dict(fid=fid/voxel,fid_volume_m3=fid,center_fid=center_fid,spatial_response=spatial,axes_m=[a.tolist() for a in axes],
        leakage_power_fraction=float(power[outside].sum()/(total or 1)),centroid_m=centroid,
        provenance=dict(estimated_work=work,estimated_memory_bytes=memory,grid_size=n,cell_volume_m3=dv,nominal_volume_m3=voxel,
            echo_time_s=echo_time,selection=selection,coherence_path=[-1,1,-1],rephaser_duration_s=rephase_duration,
            rephaser_gx_t_m=-pulses[0]['gz_t_m'],free_delays_s=waits,
            waveform_hash=_hash([rf['b1_uT'].tolist() for rf in pulses]),gradient_t_m=[rf['gz_t_m'] for rf in pulses],
            state_hash=_hash([integrated.real.tolist(),integrated.imag.tolist()]),
            normalization='complex volume integral / declared nominal voxel volume; no fitted gain',
            relaxation='scalar T2 envelope from preparation start; not quantum relaxation/T1 preparation'))


def run_press_basis(*,echo_s=.03,points=256,dwell_s=.0005,rf_duration_s=.001,rf_steps=64,
                    refine_rf_steps=128,
                    grid_size=17,refine_grid=25,extended_grid=39,extended_fov_scale=3.,thickness_m=(.02,.02,.02),fov_scale=2.,
                    basis_mode='volume',amounts=(.02,.008),basis_j_hz=7.,sample_j_hz=7.,
                    noise_std=0.,seed=7,max_work=100000000,max_memory_bytes=134217728,
                    target_relative_amount_error=.05,target_refinement_error=.02,target_rf_error=.002,target_fov_error=.02,target_leakage_fraction=.1):
    """Finer-grid synthetic sample, coarse volume/center basis and full-FID fit.

    Molecular systems remain a teaching singlet and synthetic AB. Spatial
    quadrature error, localization leakage and known-amount error are independent
    target gates. The center-point fit is an explicit mismatch control.
    """
    truth=np.asarray(amounts,float)
    if truth.shape!=(2,) or not np.isfinite(truth).all() or np.any(truth<=0) or basis_mode not in {'volume','center'}:
        raise ValueError('two positive teaching amounts and volume/center basis required')
    if not np.isfinite([basis_j_hz,sample_j_hz,noise_std,target_relative_amount_error,target_refinement_error,target_rf_error,target_fov_error,target_leakage_fraction]).all() or noise_std<0 or min(target_relative_amount_error,target_refinement_error,target_rf_error,target_fov_error,target_leakage_fraction)<=0 or type(seed) is not int or not 0<=seed<=2147483647:
        raise ValueError('finite spin/sample parameters and positive targets required')
    if type(grid_size) is not int or type(refine_grid) is not int or refine_grid<=grid_size:
        raise ValueError('an explicitly finer independent sample quadrature is required')
    if type(extended_grid) is not int or extended_grid<=refine_grid or not np.isfinite(extended_fov_scale) or not extended_fov_scale>fov_scale>=1.5:
        raise ValueError('outside-voxel FOV and explicitly larger/finer FOV check required')
    if type(rf_steps) is not int or type(refine_rf_steps) is not int or not 16<=rf_steps<refine_rf_steps<=512:
        raise ValueError('explicitly finer RF time discretization required')
    if any(type(v) is not int or v<=0 for v in [max_work,max_memory_bytes]):
        raise ValueError('positive integer resource budgets required')
    # Reserve the complete workflow before the first finite-RF propagator. The
    # retained output volumes also count against the shared memory budget.
    plan=[(grid_size,rf_steps,d) for d in [2,4,2]]+[(refine_grid,rf_steps,d) for d in [2,4,2]]
    if basis_j_hz!=sample_j_hz: plan.append((refine_grid,rf_steps,4))
    plan += [(extended_grid,rf_steps,d) for d in [2,4,2]]+[(refine_grid,refine_rf_steps,d) for d in [2,4,2]]
    for n,steps,d in plan:
        if not 3<=n<=65 or n%2!=1: raise ValueError('bounded odd spatial grid required')
    if type(points) is not int or not 16<=points<=4096: raise ValueError('bounded integer FID count required')
    planned_work=points*128+sum((3*n*(4*steps+12)+6*n*n+6*n**3+32)*d**3+4*points*d*d for n,steps,d in plan)
    retained=sum(16*n**3+48*points+24*n for n,steps,d in plan)
    peak_memory=retained+max(128*n*n*d*d+64*n**3+128*n*d*d+64*points*d*d for n,steps,d in plan)
    if planned_work>max_work or peak_memory>max_memory_bytes:
        raise ValueError('PRESS workflow preflight work/memory budget exceeded')
    work=points*128;coarse=[];fine=[];records=[]
    def simulate(freq,j,n,t2=.15,scale=None,steps=None):
        nonlocal work
        r=simulate_press_volume(freq,j,echo_s=echo_s,points=points,dwell_s=dwell_s,
            rf_duration_s=rf_duration_s,rf_steps=rf_steps if steps is None else steps,thickness_m=thickness_m,grid_size=n,fov_scale=fov_scale if scale is None else scale,
            t2_s=t2,max_work=max_work-work,max_memory_bytes=max_memory_bytes)
        work+=r['provenance']['estimated_work']; records.append(r['provenance']); return r
    for frequencies,j in [([-213.3],[[0.]]),([-300.,-270.],[[0.,basis_j_hz],[basis_j_hz,0.]])]:
        coarse.append(simulate(frequencies,j,grid_size))
        sample_j=[[0.,sample_j_hz],[sample_j_hz,0.]] if len(frequencies)==2 else j
        fine.append(simulate(frequencies,sample_j,refine_grid))
    water=simulate([0.],[[0.]],grid_size,t2=.2);water_fine=simulate([0.],[[0.]],refine_grid,t2=.2)
    # Compare quadratures at fixed molecular truth; a changed J is not grid error.
    reference_fine=fine if basis_j_hz==sample_j_hz else [fine[0],simulate([-300.,-270.],[[0.,basis_j_hz],[basis_j_hz,0.]],refine_grid)]
    refinement=[float(np.linalg.norm(a['fid']-b['fid'])/np.linalg.norm(b['fid'])) for a,b in zip(coarse+[water],reference_fine+[water_fine])]
    extended=[simulate([-213.3],[[0.]],extended_grid,scale=extended_fov_scale),
        simulate([-300.,-270.],[[0.,sample_j_hz],[sample_j_hz,0.]],extended_grid,scale=extended_fov_scale),
        simulate([0.],[[0.]],extended_grid,t2=.2,scale=extended_fov_scale)]
    fov_errors=[float(np.linalg.norm(a['fid']-b['fid'])/np.linalg.norm(b['fid'])) for a,b in zip(fine+[water_fine],extended)]
    refined_rf=[simulate([-213.3],[[0.]],refine_grid,steps=refine_rf_steps),
        simulate([-300.,-270.],[[0.,sample_j_hz],[sample_j_hz,0.]],refine_grid,steps=refine_rf_steps),
        simulate([0.],[[0.]],refine_grid,t2=.2,steps=refine_rf_steps)]
    rf_errors=[float(np.linalg.norm(a['fid']-b['fid'])/np.linalg.norm(b['fid'])) for a,b in zip(fine+[water_fine],refined_rf)]
    basis=np.array([r['fid' if basis_mode=='volume' else 'center_fid'] for r in coarse]).T
    clean=np.array([r['fid'] for r in fine]).T@truth
    rng=np.random.default_rng(seed); signal=clean+noise_std*(rng.normal(size=points)+1j*rng.normal(size=points))
    fit=fit_full_basis(signal,basis,dwell_s=dwell_s)
    error=float(np.max(abs(np.asarray(fit['amounts'])/truth-1)))
    leakage=max(r['leakage_power_fraction'] for r in fine+[water_fine])
    passed=bool(error<=target_relative_amount_error and fit['passed'] and max(refinement)<=target_refinement_error and max(rf_errors)<=target_rf_error and leakage<=target_leakage_fraction and max(fov_errors)<=target_fov_error)
    inputs=dict(echo_s=echo_s,points=points,dwell_s=dwell_s,rf_duration_s=rf_duration_s,rf_steps=rf_steps,
        grid_size=grid_size,refine_grid=refine_grid,refine_rf_steps=refine_rf_steps,extended_grid=extended_grid,extended_fov_scale=extended_fov_scale,thickness_m=list(thickness_m),fov_scale=fov_scale,
        basis_mode=basis_mode,amounts=truth.tolist(),basis_j_hz=basis_j_hz,sample_j_hz=sample_j_hz,
        noise_std=noise_std,seed=seed,max_work=max_work,max_memory_bytes=max_memory_bytes,
        target_relative_amount_error=target_relative_amount_error,target_refinement_error=target_refinement_error,target_rf_error=target_rf_error,target_fov_error=target_fov_error,target_leakage_fraction=target_leakage_fraction)
    return dict(clinical_question='How do finite RF bandwidth and coherence-selected 3D PRESS localization bias full-readout teaching spectral amounts?',
        design=inputs,names=['teaching_singlet','synthetic_AB'],signal=signal,basis=basis,fit=fit,
        water=water_fine['fid'],teaching_truth=truth,localization=coarse,water_localization=water,
        refinement_errors=refinement,rf_refinement_errors=rf_errors,extended_fov_errors=fov_errors,validation=dict(max_relative_amount_error=error,target=target_relative_amount_error,target_fit_residual=.02,
            max_rf_error=max(rf_errors),target_rf_error=target_rf_error,
            max_refinement_error=max(refinement),target_refinement_error=target_refinement_error,max_fov_error=max(fov_errors),target_fov_error=target_fov_error,
            max_leakage_power_fraction=leakage,target_leakage_fraction=target_leakage_fraction,passed=passed),
        scope='teaching/research PRESS coherence path and finite-RF complex volume integral; synthetic spin priors, scalar T2; no full molecular library, quantum relaxation, scanner validation or clinical certification; B/C parked',
        provenance=dict(version='press-volume-v1',source_hash=IMPORTED_SOURCE_HASH,source_files=_sources(),runtime=dict(python=platform.python_version(),numpy=np.__version__),replay=inputs,input_hash=_hash(inputs),estimated_work=work,estimated_peak_memory_bytes=peak_memory,
            simulations=records,basis_hash=_hash([basis.real.tolist(),basis.imag.tolist()]),
            signal_hash=_hash([signal.real.tolist(),signal.imag.tolist()]),
            normalization='known nominal voxel volume only; no fitted localization gain; finer-grid sample independent of fitting basis'))
