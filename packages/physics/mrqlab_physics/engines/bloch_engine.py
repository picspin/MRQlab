import time

import numpy as np

from ..base import SimulationEngine
from ..models import EngineOptions, Phantom, ScannerModel, SimResult


class BlochEngine(SimulationEngine):
    name = "bloch"
    description = "MVP single-isochromat Bloch simulation"

    def simulate(self, sequence, phantom: Phantom, scanner: ScannerModel, options: EngineOptions):
        started = time.perf_counter()
        dt = options.dwell_time
        times = np.arange(0, sequence.duration + dt / 2, dt)
        magnetization = np.empty((len(times), 3))
        state = np.array([0.0, 0.0, phantom.proton_density])
        pulses = sequence.channel("rf_amp")
        pulse_index = 0
        for index, t in enumerate(times):
            while pulse_index < len(pulses) and pulses[pulse_index].time <= t + dt / 2:
                alpha = np.deg2rad(pulses[pulse_index].value)
                x, y, z = state
                state = np.array([
                    x,
                    y * np.cos(alpha) - z * np.sin(alpha),
                    y * np.sin(alpha) + z * np.cos(alpha),
                ])
                pulse_index += 1
            if index:
                phase = 2 * np.pi * phantom.off_resonance_hz * dt
                transverse = (state[0] + 1j * state[1]) * np.exp(-dt / phantom.t2 + 1j * phase)
                state = np.array([
                    transverse.real,
                    transverse.imag,
                    phantom.proton_density - (
                        phantom.proton_density - state[2]
                    ) * np.exp(-dt / phantom.t1),
                ])
            magnetization[index] = state
        windows: list[tuple[float, float]] = []
        active = None
        for event in sequence.channel("adc_gate"):
            if event.value and active is None:
                active = event.time
            elif not event.value and active is not None:
                windows.append((active, event.time))
                active = None
        sample_mask = np.array([any(start <= t < stop for start, stop in windows) for t in times])
        signal = (magnetization[:, 0] + 1j * magnetization[:, 1])[sample_mask]
        return SimResult(
            signal=signal,
            magnetization=magnetization if options.return_magnetization else None,
            k_trajectory=np.zeros((len(signal), 3)),
            meta={"engine": self.name, "samples": len(signal)},
            timing={"simulation_seconds": time.perf_counter() - started},
        )
