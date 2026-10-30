"""Finite-history generalized Bloch semisolid RF, not an absorption-rate clamp.

G(t) is the real FID Green function. Complex RF and off-resonance enter a
Volterra convolution; all previous pulse/gap intervals remain in that history.
Product integration is linear in longitudinal state within each RF hold, and
Crank--Nicolson advances the coupled real affine system. Refinement is required.
"""
import numpy as np


def solver_budget(steps,dimension,unique_rf_holds):
    return dict(planned_work=int(8*steps*steps+2*steps*dimension**2+4*unique_rf_holds*dimension**3+steps*dimension*8),
        estimated_peak_memory_bytes=int(8*(steps+1)*dimension+64*steps+32*unique_rf_holds*dimension**2))


def semisolid_green(lag_s,t2_s,*,lineshape='super_lorentzian',orientation_order=32):
    lag=np.asarray(lag_s,float)
    if not np.isfinite(lag).all() or np.any(lag<0) or not np.isfinite(t2_s) or t2_s<=0:
        raise ValueError('finite nonnegative lags and positive semisolid T2 required')
    if type(orientation_order) is not int or not 8<=orientation_order<=256:
        raise ValueError('orientation quadrature order 8..256 required')
    scaled=lag/t2_s
    if lineshape=='lorentzian': return np.exp(-scaled)
    if lineshape=='gaussian': return np.exp(-scaled**2/2)
    if lineshape!='super_lorentzian': raise ValueError('unsupported semisolid Green function')
    # Split about the magic angle. At long lags, change integration bounds to
    # resolve its narrow Gaussian neighborhood. Excluded integrand <=exp(-64),
    # not a finite replacement for the divergent zero-frequency lineshape.
    nodes,weights=np.polynomial.legendre.leggauss(orientation_order)
    width=np.divide(8*np.sqrt(8),scaled,out=np.full_like(scaled,np.inf),where=scaled>0)
    low=np.sqrt(np.maximum(0.,(1-width)/3));high=np.sqrt(np.minimum(1.,(1+width)/3))
    magic=1/np.sqrt(3);result=np.zeros_like(lag)
    for a,b in [(low,np.full_like(lag,magic)),(np.full_like(lag,magic),high)]:
        u=(a[...,None]+b[...,None])/2+(b-a)[...,None]*nodes/2
        result+=(b-a)/2*np.sum(weights*np.exp(-scaled[...,None]**2*(3*u*u-1)**2/8),axis=-1)
    return result


def memory_weights(steps,dt_s,*,t2_s,offset_hz=0.,lineshape='super_lorentzian',
                   orientation_order=32,time_order=32,max_work=100000000,max_memory_bytes=134217728):
    """Integrals of G(u) exp(-i*offset*u) times linear source interpolation.

    Return left/right endpoint weights for every lag cell. Zero offset is regular
    here, including for the super-Lorentzian Green function. No history truncation.
    """
    if type(steps) is not int or not 1<=steps<=32768 or not np.isfinite([dt_s,offset_hz]).all() or dt_s<=0:
        raise ValueError('bounded positive step count/duration and finite carrier offset required')
    if type(time_order) is not int or not 8<=time_order<=128: raise ValueError('time quadrature order 8..128 required')
    for value in [max_work,max_memory_bytes]:
        if type(value) is not int or value<=0: raise ValueError('positive integer kernel budgets required')
    work=int(steps*time_order*(2*orientation_order+16));chunk=min(128,steps)
    memory=int(32*steps+128*chunk*time_order*orientation_order)
    if work>max_work or memory>max_memory_bytes: raise ValueError('Green-function quadrature work/memory budget exceeded before allocation')
    nodes,weights=np.polynomial.legendre.leggauss(time_order)
    fraction=(nodes+1)/2;quadrature=weights*dt_s/2
    left=np.empty(steps,complex);right=np.empty(steps,complex)
    for start in range(0,steps,chunk):
        stop=min(steps,start+chunk);lag=(np.arange(start,stop)[:,None]+fraction)*dt_s
        kernel=semisolid_green(lag,t2_s,lineshape=lineshape,orientation_order=orientation_order)*np.exp(-2j*np.pi*offset_hz*lag)
        left[start:stop]=kernel@(quadrature*fraction)
        right[start:stop]=kernel@(quadrature*(1-fraction))
    return left,right,dict(estimated_work=work,estimated_peak_memory_bytes=memory,
        method='Gauss-Legendre lag-cell integrals and magic-angle-resolved orientation quadrature; no lag cutoff')


def integrate_generalized_mt(free_generator,rf_x_generator,rf_y_generator,initial,
                             rf_rad_s,dt_s,left,right,*,bound_index,
                             max_work=100000000,max_memory_bytes=134217728):
    """Advance coupled liquids / one common semisolid Z / affine source.

    RF is piecewise constant per interval. Left/right RF values may jump at a
    pulse boundary; longitudinal state interpolates within that interval only.
    Complex RF phase is kept, and memory survives gaps and phase changes.
    """
    free=np.asarray(free_generator,float);rx=np.asarray(rf_x_generator,float);ry=np.asarray(rf_y_generator,float)
    state=np.asarray(initial,float);rf=np.asarray(rf_rad_s,complex);left=np.asarray(left,complex);right=np.asarray(right,complex)
    if rf.ndim!=1 or state.ndim!=1: raise ValueError('RF and affine state must be vectors')
    n=len(rf);d=len(state)
    if (state.ndim!=1 or not 2<=d<=32 or any(a.shape!=(d,d) for a in [free,rx,ry]) or
            rf.ndim!=1 or not 1<=n<=32768 or left.shape!=(n,) or right.shape!=(n,) or
            not all(np.isfinite(a).all() for a in [free,rx,ry,state,rf,left,right]) or
            not np.isfinite(dt_s) or dt_s<=0 or type(bound_index) is not int or not 0<=bound_index<d-1):
        raise ValueError('finite compatible affine matrices, RF holds, kernel cells and bound-state index required')
    if state[-1]!=1. or any(np.any(a[-1]) for a in [free,rx,ry]): raise ValueError('source-last affine state must remain exactly one')
    if any(np.any(a[bound_index]) or np.any(a[:,bound_index]) for a in [rx,ry]):
        raise ValueError('semisolid RF acts through memory only, not direct matrix rotation')
    for value in [max_work,max_memory_bytes]:
        if type(value) is not int or value<=0: raise ValueError('positive integer solver budgets required')
    unique=len(set(rf.tolist()))
    budget=solver_budget(n,d,unique);planned=budget['planned_work'];memory=budget['estimated_peak_memory_bytes']
    if planned>max_work or memory>max_memory_bytes: raise ValueError('complete Volterra/affine work or memory budget exceeded before history allocation')
    history=np.empty((n+1,d));history[0]=state
    qleft=np.zeros(n,complex);qright=np.zeros(n,complex);cache={};eye=np.eye(d)
    for i,omega in enumerate(rf):
        if omega not in cache:
            a=free+omega.real*rx+omega.imag*ry
            lhs=eye-dt_s*a/2;lhs[bound_index,bound_index]+=dt_s*abs(omega)**2*right[0].real/2
            cache[omega]=(np.linalg.inv(lhs),eye+dt_s*a/2)
        inv,advance=cache[omega];rhs=advance@history[i]
        if omega!=0:
            before=left[:i][::-1]@qleft[:i]+right[:i][::-1]@qright[:i]
            end=left[1:i+1][::-1]@qleft[:i]+right[1:i+1][::-1]@qright[:i]
            end+=omega*left[0]*history[i,bound_index]
            rhs[bound_index]-=dt_s/2*np.real(np.conj(omega)*(before+end))
        history[i+1]=inv@rhs
        if not np.isfinite(history[i+1]).all(): raise ValueError('nonfinite generalized Bloch state; refine or reject this design')
        qleft[i]=omega*history[i,bound_index];qright[i]=omega*history[i+1,bound_index]
    actual=int(16*sum(i for i,omega in enumerate(rf) if omega!=0)+2*n*d*d+4*unique*d**3+n*d*8)
    return history,dict(estimated_work=actual,planned_work=planned,estimated_peak_memory_bytes=memory,
        steps=n,dt_s=dt_s,unique_rf_holds=unique,history_reset=False,history_cutoff_s=None,
        method='linear-state product integration with implicit endpoint self-memory and affine Crank-Nicolson',
        scope='finite uniform-grid approximation; verify time/kernel refinement; no fitted absorption rate or sign clipping')
