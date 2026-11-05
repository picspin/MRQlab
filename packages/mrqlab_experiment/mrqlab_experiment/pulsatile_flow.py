"""Pressure-driven periodic Womersley flow in a straight rigid circular pipe.

Newtonian incompressible fully developed laminar solution, not patient-specific
CFD. Pressure waveform is prescribed; fluid starts in its periodic steady state.
Axial trajectories may reverse; radial positions stay fixed, with no wrapping.
"""
import numpy as np


def bessel_j(order, z):
    """Bounded complex J0/J1 power series; no approximation outside |z|<=12."""
    z = np.asarray(z, complex)
    if order not in (0, 1) or not np.isfinite(z).all() or np.any(abs(z)>12):
        raise ValueError('J0/J1 finite argument |z|<=12 required')
    term = np.ones_like(z) if order==0 else z/2
    result = term.copy()
    for k in range(1, 100):
        term = term*(-z*z/4)/(k*(k+order)); result += term
        if np.all(abs(term)<2e-16*np.maximum(1.,abs(result))): return result
    raise ValueError('Bessel series did not converge')


class WomersleyPipe:
    """v(r,t) solves dv/dt=a(t)+nu/r*d(r*dv/dr)/dr, v(R,t)=0.

    a(t)=[mean_gradient+osc_gradient*cos(omega*t+phase)]/density,
    with positive gradient meaning -dp/dz. All public quantities use SI.
    """
    def __init__(self, *, radius_m=.002, density_kg_m3=1060., viscosity_pa_s=.0035,
                 mean_gradient_pa_m=100., oscillating_gradient_pa_m=200.,
                 frequency_hz=1., phase_rad=0.):
        values=[radius_m,density_kg_m3,viscosity_pa_s,mean_gradient_pa_m,
                oscillating_gradient_pa_m,frequency_hz,phase_rad]
        if not np.isfinite(values).all() or min(radius_m,density_kg_m3,viscosity_pa_s,frequency_hz)<=0 or oscillating_gradient_pa_m<0:
            raise ValueError('positive finite pipe/fluid/frequency and nonnegative oscillation required')
        self.radius=radius_m; self.density=density_kg_m3; self.nu=viscosity_pa_s/density_kg_m3
        self.omega=2*np.pi*frequency_hz; self.alpha=radius_m*np.sqrt(self.omega/self.nu)
        if not .02<=self.alpha<=12: raise ValueError('validated Womersley alpha range is 0.02 to 12')
        self.mean_acceleration=mean_gradient_pa_m/density_kg_m3
        self.harmonic_acceleration=oscillating_gradient_pa_m/density_kg_m3*np.exp(1j*phase_rad)
        self.lam=(1-1j)*self.alpha/np.sqrt(2)
        self.denominator=bessel_j(0,self.lam)
        speed_bound=abs(self.mean_acceleration)*radius_m**2/(4*self.nu)+abs(self.harmonic_acceleration)/self.omega*(1+np.cosh(abs(self.lam.imag))/abs(self.denominator))
        self.reynolds_bound=float(2*radius_m*speed_bound/self.nu)
        if self.reynolds_bound>1000:
            raise ValueError('outside declared laminar teaching domain: conservative Reynolds bound exceeds 1000; transition/turbulence not modeled')
        self.parameters=dict(radius_m=radius_m,density_kg_m3=density_kg_m3,viscosity_pa_s=viscosity_pa_s,
            mean_gradient_pa_m=mean_gradient_pa_m,oscillating_gradient_pa_m=oscillating_gradient_pa_m,
            frequency_hz=frequency_hz,phase_rad=phase_rad)

    def coefficients(self, radius_m):
        r=np.asarray(radius_m,float)
        if not np.isfinite(r).all() or np.any(r<0) or np.any(r>self.radius):
            raise ValueError('radial coordinates must be within the pipe')
        steady=self.mean_acceleration*(self.radius**2-r*r)/(4*self.nu)
        harmonic=self.harmonic_acceleration/(1j*self.omega)*(1-bessel_j(0,self.lam*r/self.radius)/self.denominator)
        return steady,harmonic

    def velocity(self, radius_m, time_s):
        if not np.isfinite(time_s) or time_s<0: raise ValueError('finite nonnegative time required')
        steady,harmonic=self.coefficients(radius_m)
        return steady+np.real(harmonic*np.exp(1j*self.omega*time_s))

    def volume_flow_m3_s(self,time_s):
        if not np.isfinite(time_s) or time_s<0: raise ValueError('finite nonnegative time required')
        mean=self.mean_acceleration*self.radius**2/(8*self.nu)
        harmonic=self.harmonic_acceleration/(1j*self.omega)*(1-2*bessel_j(1,self.lam)/(self.lam*self.denominator))
        return float(np.pi*self.radius**2*(mean+np.real(harmonic*np.exp(1j*self.omega*time_s))))

    def motion(self,radius_m): return WomersleyMotion(*self.coefficients(radius_m),self.omega)


class WomersleyMotion:
    """Analytic displacement and exact non-RF gradient phase integral."""
    def __init__(self,steady,harmonic,omega):
        self.steady=np.array(steady,float,copy=True); self.harmonic=np.array(harmonic,complex,copy=True)
        if self.steady.shape!=self.harmonic.shape or not np.isfinite(self.steady).all() or not np.isfinite(self.harmonic).all() or not np.isfinite(omega) or omega<=0:
            raise ValueError('finite matched motion coefficients and positive angular frequency required')
        self.omega=omega
        self.steady.flags.writeable=False; self.harmonic.flags.writeable=False

    def displacement(self,time_s):
        if not np.isfinite(time_s) or time_s<0: raise ValueError('finite nonnegative time required')
        return self.steady*time_s+np.real(self.harmonic*np.expm1(1j*self.omega*time_s)/(1j*self.omega))

    def positions(self,z0,time_s): return z0+self.displacement(time_s)

    def position_integral(self,z0,start_s,end_s):
        if not np.isfinite([start_s,end_s]).all() or start_s<0 or end_s<=start_s: raise ValueError('ordered finite integration interval required')
        dt=end_s-start_s; z=1j*self.omega*dt
        # exprel(z)-1 with a stable series for short RF/gradient intervals.
        relative_minus_one=(z/2+z*z/6+z**3/24+z**4/120+z**5/720) if abs(z)<1e-3 else np.expm1(z)/z-1
        integral=dt*(np.expm1(1j*self.omega*start_s)+np.exp(1j*self.omega*start_s)*relative_minus_one)/(1j*self.omega)
        return z0*dt+self.steady*(end_s**2-start_s**2)/2+np.real(self.harmonic*integral)

    def displacement_bounds(self,end_s):
        if not np.isfinite(end_s) or end_s<=0: raise ValueError('positive finite horizon required')
        amplitude=2*abs(self.harmonic)/self.omega
        return np.minimum(0.,self.steady*end_s)-amplitude,np.maximum(0.,self.steady*end_s)+amplitude


def pipe_reservoir(pipe, *, end_s, thickness_m, radial_rings, axial_spins):
    """Equal-area midpoint rings and axial volume quadrature; finite reservoir."""
    if type(radial_rings) is not int or not 2<=radial_rings<=64 or type(axial_spins) is not int or axial_spins<33:
        raise ValueError('bounded integer radial/axial quadrature required')
    if not np.isfinite([end_s,thickness_m]).all() or min(end_s,thickness_m)<=0: raise ValueError('positive finite horizon and thickness required')
    r=pipe.radius*np.sqrt((np.arange(radial_rings)+.5)/radial_rings)
    ring_motion=pipe.motion(r); low,high=ring_motion.displacement_bounds(end_s)
    left=-high-2*thickness_m; right=-low+2*thickness_m
    dz=(right-left)/axial_spins
    z=(left[:,None]+(np.arange(axial_spins)[None,:]+.5)*dz[:,None]).ravel()
    radii=np.repeat(r,axial_spins); weights=np.repeat(dz/radial_rings,axial_spins)
    return z,pipe.motion(radii),weights,radii
