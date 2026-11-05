"""Small completely-positive local spin baths, with explicit authored rates.

Column-major vectorization: d vec(rho)/dt = L vec(rho). This is a local
phenomenological Lindblad model, not molecular Redfield or correlated relaxation.
"""
import numpy as np
from .cest_saturation import _matrix_exp


def lindblad_generator(hamiltonian, collapses):
    h=np.asarray(hamiltonian,complex)
    if h.ndim!=2 or h.shape[0]!=h.shape[1] or not 2<=len(h)<=8 or not np.isfinite(h).all() or not np.allclose(h,h.conj().T,rtol=0,atol=1e-12):
        raise ValueError('finite Hermitian two-to-eight-state Hamiltonian required')
    identity=np.eye(len(h));generator=-1j*(np.kron(identity,h)-np.kron(h.T,identity))
    for value in collapses:
        c=np.asarray(value,complex)
        if c.shape!=h.shape or not np.isfinite(c).all(): raise ValueError('finite compatible collapse operators required')
        product=c.conj().T@c
        generator+=np.kron(c.conj(),c)-.5*(np.kron(identity,product)+np.kron(product.T,identity))
    return generator


def local_spin_bath(operators,t1_s,t2_s,*,polarization=.01):
    """Independent amplitude damping and pure dephasing of each spin-1/2.

    All spins have the same authored equilibrium polarization. Its product state
    commutes with chemical shifts and isotropic J, which conserve total Iz.
    T2 <= 2*T1 is necessary for nonnegative pure-dephasing rates.
    """
    count=len(operators);t1=np.asarray(t1_s,float);t2=np.asarray(t2_s,float)
    if not 1<=count<=3 or t1.shape!=(count,) or t2.shape!=(count,) or not np.isfinite([*t1,*t2,polarization]).all() or np.any(t1<=0) or np.any(t2<=0) or np.any(t2>2*t1) or not 0<polarization<1:
        raise ValueError('one-to-three positive T1/T2 values with T2<=2*T1 and polarization in (0,1) required')
    collapses=[];rates=[];equilibrium=np.ones((1,1),complex)
    for axes,a,b in zip(operators,t1,t2):
        up=(1+polarization)/(2*a);down=(1-polarization)/(2*a);dephase=1/b-1/(2*a)
        collapses.extend([np.sqrt(up)*(axes[0]+1j*axes[1]),np.sqrt(down)*(axes[0]-1j*axes[1]),np.sqrt(2*dephase)*axes[2]])
        equilibrium=np.kron(equilibrium,np.diag([(1+polarization)/2,(1-polarization)/2]))
        rates.append(dict(up_s1=float(up),down_s1=float(down),pure_dephasing_s1=float(dephase)))
    return collapses,equilibrium,rates


def quantum_channel(generator,duration_s):
    g=np.asarray(generator,complex)
    if g.ndim!=2 or g.shape[0]!=g.shape[1] or len(g) not in {4,16,64} or not np.isfinite(g).all() or not np.isfinite(duration_s) or duration_s<0:
        raise ValueError('bounded finite Liouvillian and nonnegative duration required')
    return _matrix_exp(g,duration_s)


def periodic_density(cycle,dimension):
    """Trace-constrained fixed point; never renormalize or clip the solution."""
    c=np.asarray(cycle,complex);d=dimension
    if type(d) is not int or d not in {2,4,8} or c.shape!=(d*d,d*d) or not np.isfinite(c).all():
        raise ValueError('bounded compatible cycle channel required')
    lhs=np.eye(d*d)-c;rhs=np.zeros(d*d,complex)
    trace=np.eye(d).reshape(-1,order='F');lhs[0]=trace;rhs[0]=1.
    condition=float(np.linalg.cond(lhs))
    if not np.isfinite(condition) or condition>1e10: raise ValueError('periodic density fixed point is ill conditioned or nonunique')
    state=np.linalg.solve(lhs,rhs)
    return state.reshape((d,d),order='F'),dict(fixed_point_residual=float(np.max(abs(c@state-state))),trace_constraint_condition=condition)
