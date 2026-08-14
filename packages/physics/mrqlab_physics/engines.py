import time
import numpy as np
from .base import SimulationEngine
from .models import EngineOptions, Phantom, ScannerModel, SimResult

class BlochEngine(SimulationEngine):
    """Minimal single-isochromat event solver (degrees for RF event values)."""
    name = "bloch"
    def simulate(self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions):
        started = time.perf_counter(); dt = options.dwell_time
        times = np.arange(0, sequence.duration + dt / 2, dt)
        m = np.empty((len(times), 3)); state = np.array([0., 0., phantom.proton_density])
        pulses = sequence.channel("rf_amp"); pulse_i = 0
        for i, t in enumerate(times):
            while pulse_i < len(pulses) and pulses[pulse_i].time <= t + dt / 2:
                a = np.deg2rad(pulses[pulse_i].value); x, y, z = state
                state = np.array([x, y*np.cos(a)-z*np.sin(a), y*np.sin(a)+z*np.cos(a)])
                pulse_i += 1
            if i:
                phase = 2*np.pi*phantom.off_resonance_hz*dt
                xy = (state[0] + 1j*state[1])*np.exp((-dt/phantom.t2) + 1j*phase)
                state = np.array([xy.real, xy.imag, phantom.proton_density-(phantom.proton_density-state[2])*np.exp(-dt/phantom.t1)])
            m[i] = state
        gate = sequence.channel("adc_gate"); windows=[]; on=None
        for e in gate:
            if e.value and on is None: on=e.time
            elif not e.value and on is not None: windows.append((on,e.time)); on=None
        sample_mask = np.array([any(a <= t < b for a,b in windows) for t in times])
        signal = (m[:,0] + 1j*m[:,1])[sample_mask]
        gx = sequence.channel("gx"); kval=0.; k=[]; gi=0; g=0.
        for t in times[sample_mask]:
            while gi < len(gx) and gx[gi].time <= t: g=gx[gi].value; gi += 1
            kval += g*scanner.gradient_scale*dt; k.append(kval)
        return SimResult(signal=signal, magnetization=m if options.return_magnetization else None,
                         k_trajectory=np.asarray(k), meta={"engine": self.name, "samples": len(signal)},
                         timing={"simulation_seconds": time.perf_counter()-started})

class _FutureEngine(SimulationEngine):
    def simulate(self, *args, **kwargs):
        raise NotImplementedError(f"{self.name} engine is registered for future work; use 'bloch' for the MVP")
class EPGEngine(_FutureEngine): name="epg"
class SpectralEngine(_FutureEngine): name="spectral"
