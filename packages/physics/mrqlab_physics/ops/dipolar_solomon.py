"""High-field isotropic two-proton Solomon dipolar relaxation, SI units.

J(w)=tau/(1+w²tau²), dipolar b=(mu0/4pi)*gamma²*hbar/r³ (rad/s).
This is a Markov/secular longitudinal pair model, not full molecular Redfield
coherence relaxation or a fitted unidirectional saturation-transfer rate.
"""
import numpy as np
from ..kernel.units import GAMMA_BAR_HZ_T

HBAR_J_S=1.054571817e-34
MU0_OVER_4PI=1e-7 # conventional SI dipolar prefactor, recorded approximation


def dipolar_pair_rates(*,b0_t=3.,distance_m=2.5e-10,tau_c_s=1e-8,
                       shifts_ppm=(1.,-3.5)):
    if len(shifts_ppm)!=2 or not np.isfinite([b0_t,distance_m,tau_c_s,*shifts_ppm]).all():
        raise ValueError('finite field, distance, correlation time and two shifts required')
    if not .05<=b0_t<=20. or not 1e-10<=distance_m<=2e-9 or not 1e-12<=tau_c_s<=1e-6 or max(abs(x) for x in shifts_ppm)>100:
        raise ValueError('B0 0.05..20 T, distance 0.1..2 nm, tau 1 ps..1 us and bounded chemical shifts required')
    gamma=2*np.pi*GAMMA_BAR_HZ_T
    omega=gamma*b0_t*(1+np.array(shifts_ppm)*1e-6)
    b=MU0_OVER_4PI*gamma*gamma*HBAR_J_S/distance_m**3
    if b*tau_c_s>.05: raise ValueError('dipolar b*tau exceeds declared weak-fluctuation bound 0.05')
    j=lambda w: tau_c_s/(1+(w*tau_c_s)**2)
    factor=b*b/10
    w0=factor*j(omega[0]-omega[1]); w2=6*factor*j(omega[0]+omega[1])
    w1_i=1.5*factor*j(omega[0]); w1_s=1.5*factor*j(omega[1])
    rho_i=w0+w2+2*w1_i; rho_s=w0+w2+2*w1_s; sigma=w2-w0
    return dict(rho_i_s1=float(rho_i),rho_s_s1=float(rho_s),sigma_s1=float(sigma),
        w0_s1=float(w0),w2_s1=float(w2),w1_i_s1=float(w1_i),w1_s_s1=float(w1_s),
        dipolar_b_rad_s=float(b),weak_fluctuation_b_tau=float(b*tau_c_s),
        omega_i_rad_s=float(omega[0]),omega_s_rad_s=float(omega[1]),
        spectral_density='tau/(1+(omega*tau)^2), seconds',
        mu0_over_4pi_si=MU0_OVER_4PI,hbar_j_s=HBAR_J_S)


def add_solomon_pair(generator,system,i,j,rates,*,cross_relaxation=True):
    """Add -rho*deltaZi-sigma*deltaZj for equal-density one-to-one pairs.

    Pair spin-flip R2=rho/2 is added to the authored background transverse
    relaxation; additional dipolar pure dephasing is not derived here. Retaining
    rho when disabling sigma is a named conditional control, not a new molecule.
    """
    if type(i) is not int or type(j) is not int or i==j or min(i,j)<0 or max(i,j)>=system.count:
        raise ValueError('two distinct valid liquid indices required')
    if type(cross_relaxation) is not bool: raise ValueError('boolean cross-relaxation control required')
    if not np.isclose(system.density[i],system.density[j],rtol=0,atol=1e-15):
        raise ValueError('this one-to-one Solomon pair requires equal equilibrium densities')
    g=np.array(generator,float,copy=True); n=3*system.count
    if g.ndim!=2 or g.shape[0]!=g.shape[1] or len(g)<n+1 or not np.isfinite(g).all():
        raise ValueError('finite liquid Cartesian affine generator required')
    rho_i,rho_s,sigma=[rates[k] for k in ['rho_i_s1','rho_s_s1','sigma_s1']]
    if not np.isfinite([rho_i,rho_s,sigma]).all() or min(rho_i,rho_s)<0 or abs(sigma)>np.sqrt(rho_i)*np.sqrt(rho_s)*(1+1e-12):
        raise ValueError('positive semidefinite pair relaxation required')
    sigma=sigma if cross_relaxation else 0.
    for this,other,rho in [(i,j,rho_i),(j,i,rho_s)]:
        base=3*this; other_z=3*other+2
        g[base,base]-=rho/2; g[base+1,base+1]-=rho/2
        g[base+2,base+2]-=rho; g[base+2,other_z]-=sigma
        g[base+2,-1]+=rho*system.density[this]+sigma*system.density[other]
    return g
