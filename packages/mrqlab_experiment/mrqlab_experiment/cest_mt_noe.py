"""Joint liquid CEST, longitudinal semisolid MT and effective upfield rNOE.

The rNOE pool is phenomenological BM exchange, not microscopic Solomon cross
relaxation. No clinical concentration/biomarker or scanner validation claim.
"""
from dataclasses import asdict
from pathlib import Path
from hashlib import sha256
import numpy as np
from mrqlab_physics.models import LiquidPoolSystem
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from mrqlab_physics.ops.cest_saturation import liquid_bm_generator, _matrix_exp, validate_cest_timing
from mrqlab_physics.ops.super_lorentzian import super_lorentzian_absorption_rate
from .spatial_imaging import _hash

SCOPE = ('research/teaching homogeneous joint CEST/semisolid MT/effective rNOE; '
         'rNOE is an effective exchanging upfield pool, not microscopic cross relaxation; '
         'no scanner validation, clinical quality certification or concentration calibration; B/C parked')


def joint_pool_system(b0_t=3., *, amide_scale=1., noe_scale=1.):
    if not np.isfinite([b0_t, amide_scale, noe_scale]).all() or b0_t <= 0 or min(amide_scale, noe_scale) < 0:
        raise ValueError('positive B0 and nonnegative exchange scales required')
    density = np.array([1., .003, .005, .02])
    rates = np.zeros((4, 4))
    for i, k in enumerate([30.*amide_scale, 200., 15.*noe_scale], 1):
        rates[0, i] = density[i]*k; rates[i, 0] = k
    offsets = np.array([0., 3.5, 2., -3.5])*GAMMA_BAR_HZ_T*b0_t*1e-6
    return LiquidPoolSystem((1.5, 1., 1., 1.), (.08, .02, .01, .0005),
        tuple(density), tuple(offsets), tuple(map(tuple, rates)))


def joint_generator(system, offset_hz, b1_uT, *, bound_fraction=.08,
                    bound_t1_s=1., bound_t2_s=12e-6, bound_to_water_hz=20.,
                    lineshape='super_lorentzian'):
    """3N liquid components + bound Z + affine source; all exchange concurrent.

    Water is pool 0, semisolid exchanges only longitudinally with water.
    Transverse water loses coherence on entry into the semisolid reservoir.
    Detailed balance: k_water_bound = fraction_bound/fraction_water*k_bound_water.
    """
    values = [bound_fraction, bound_t1_s, bound_t2_s, bound_to_water_hz, offset_hz, b1_uT]
    if not np.isfinite(values).all() or min(bound_fraction, bound_to_water_hz, b1_uT) < 0 or min(bound_t1_s, bound_t2_s) <= 0:
        raise ValueError('invalid semisolid parameters')
    if lineshape not in {'super_lorentzian', 'gaussian'}: raise ValueError('unsupported bound lineshape')
    if system.density[0] <= 0: raise ValueError('water density must be positive')
    liquid = liquid_bm_generator(system, offset_hz, b1_uT)
    d = 3*system.count; g = np.zeros((d+2, d+2))
    g[:d, :d] = liquid[:d, :d]; g[:d, -1] = liquid[:d, -1]
    kwb = bound_fraction/system.density[0]*bound_to_water_hz
    # No fictitious transverse semisolid pool or hard-RF bound rotation.
    g[0, 0] -= kwb; g[1, 1] -= kwb
    g[2, 2] -= kwb; g[2, d] = bound_to_water_hz
    g[d, 2] = kwb; g[d, d] = -1/bound_t1_s-bound_to_water_hz
    g[d, -1] = bound_fraction/bound_t1_s
    rate = 0.
    if b1_uT > 0 and bound_fraction > 0:
        if lineshape == 'super_lorentzian':
            # The existing canonical SL implementation is singular at zero.
            # Preserve fail-closed behavior; never clamp or substitute a line.
            rate = super_lorentzian_absorption_rate(b1_uT, offset_hz, bound_t2_s)
        else:
            line = bound_t2_s/np.sqrt(2*np.pi)*np.exp(-.5*(2*np.pi*offset_hz*bound_t2_s)**2)
            rate = np.pi*(2*np.pi*GAMMA_BAR_HZ_T*b1_uT*1e-6)**2*line
    g[d, d] -= rate
    return g


def run_cest_mt_noe(*, offsets_ppm=(-5., -3.5, -2., -1., 1., 2., 3.5, 5.),
                    b0_t=3., b1_uT=1., saturation_s=1., mode='cw', n_pulses=1,
                    pulse_s=1., gap_s=0., bound_fraction=.08,
                    bound_to_water_hz=20., bound_t2_s=12e-6,
                    lineshape='super_lorentzian', max_work=100000000,
                    max_duration_s=300., target_min_amide_contrast=.005):
    """Full/control Z spectra -> explicit contrast objective -> validation/replay.

    Every offset/control starts at thermal equilibrium; offset-wise recovery and
    scanner readout are absent. Controls turn off balanced exchange links only,
    retaining the same pool densities and direct saturation.
    """
    offsets = np.asarray(offsets_ppm, float)
    if offsets.ndim != 1 or not 2 <= len(offsets) <= 128 or not np.isfinite(offsets).all() or len(np.unique(offsets)) != len(offsets):
        raise ValueError('2..128 distinct finite offsets required')
    if any(np.count_nonzero(np.isclose(offsets, x)) != 1 for x in (-3.5, 3.5)):
        raise ValueError('exactly one +/-3.5 ppm sample required for metrics')
    if not np.isfinite([b1_uT, max_duration_s, target_min_amide_contrast]).all() or min(b1_uT, max_duration_s, target_min_amide_contrast) <= 0:
        raise ValueError('positive finite power, duration budget and target required')
    if type(max_work) is not int or max_work <= 0: raise ValueError('positive integer work budget required')
    timing = validate_cest_timing(dict(mode=mode, saturation_duration_s=saturation_s,
        n_pulses=n_pulses, pulse_duration_s=pulse_s, gap_duration_s=gap_s))
    _, count, pulse, gap, elapsed, duty = timing
    if count > 1000: raise ValueError('at most 1000 saturation pulses')
    controls = dict(full=(1., 1., 1.), no_amide=(0., 1., 1.), no_noe=(1., 0., 1.), no_mt=(1., 1., 0.))
    duration = (len(controls)*len(offsets)+1)*elapsed
    if duration > max_duration_s: raise ValueError('all-offset/control duration budget exceeded')
    spectra = {}; states = {}; work = 0; water_reference = None
    for name, (amide, noe, mt) in controls.items():
        system = joint_pool_system(b0_t, amide_scale=amide, noe_scale=noe)
        initial = np.zeros(3*system.count+2); initial[2:3*system.count:3] = system.density
        initial[-2] = bound_fraction; initial[-1] = 1.
        z = []; retained = []
        for ppm in offsets:
            hz = float(ppm*GAMMA_BAR_HZ_T*b0_t*1e-6)
            args = dict(bound_fraction=bound_fraction, bound_t2_s=bound_t2_s,
                bound_to_water_hz=bound_to_water_hz*mt, lineshape=lineshape)
            g = joint_generator(system, hz, b1_uT, **args)
            relax = joint_generator(system, hz, 0., **args)
            # Upper proxy: Taylor <=79 multiplies plus scaling/squaring count.
            scale = max(0, int(np.ceil(np.log2(max(float(np.linalg.norm(g, np.inf)*pulse), 1.)))))
            scale_gap = max(0, int(np.ceil(np.log2(max(float(np.linalg.norm(relax, np.inf)*gap), 1.)))))
            cost = len(initial)**3*((80+scale)*count+(80+scale_gap)*(count-1 if gap > 0 else 0))
            if work+cost > max_work: raise ValueError('joint CEST matrix-exponential work budget exceeded')
            work += cost
            prop = _matrix_exp(g, pulse)
            free = _matrix_exp(relax, gap) if gap > 0 and count > 1 else None
            state = initial.copy()
            for i in range(count):
                state = prop @ state
                if i+1 < count and free is not None: state = free @ state
            z.append(float(state[2]/system.density[0])); retained.append(state.tolist())
        spectra[name] = z; states[name] = retained
        if name == 'full':
            control_cost = len(initial)**3*100
            if work+control_cost > max_work: raise ValueError('unsaturated control exceeds work budget')
            work += control_cost
            water_reference = float((_matrix_exp(joint_generator(system, 0., 0., **args), elapsed) @ initial)[2])
    plus = np.flatnonzero(np.isclose(offsets, 3.5))[0]; minus = np.flatnonzero(np.isclose(offsets, -3.5))[0]
    metrics = dict(amide_exchange_contrast=float(spectra['no_amide'][plus]-spectra['full'][plus]),
        effective_noe_contrast=float(spectra['no_noe'][minus]-spectra['full'][minus]),
        mt_contrast_at_amide=float(spectra['no_mt'][plus]-spectra['full'][plus]),
        mtr_asym_3p5=float(spectra['full'][minus]-spectra['full'][plus]),
        unsaturated_water=water_reference)
    inputs = dict(offsets_ppm=offsets.tolist(), b0_t=b0_t, b1_uT=b1_uT, saturation_s=saturation_s,
        mode=mode, n_pulses=n_pulses, pulse_s=pulse_s, gap_s=gap_s,
        bound_fraction=bound_fraction, bound_to_water_hz=bound_to_water_hz, bound_t2_s=bound_t2_s,
        lineshape=lineshape, max_work=max_work, max_duration_s=max_duration_s,
        target_min_amide_contrast=target_min_amide_contrast)
    return dict(clinical_question='How do semisolid MT and an effective upfield rNOE pool confound amide CEST and saturation-power choice?',
        design=inputs, offsets_ppm=offsets.tolist(), spectra=spectra, metrics=metrics,
        objective_loss=-metrics['amide_exchange_contrast'],
        validation=dict(target_min_amide_contrast=target_min_amide_contrast,
            passed=metrics['amide_exchange_contrast'] >= target_min_amide_contrast), scope=SCOPE,
        provenance=dict(version='joint-cest-mt-noe-v1', replay=inputs, input_hash=_hash(inputs),
            source_hash=sha256(Path(__file__).read_bytes()).hexdigest(), states_hash=_hash(states),
            liquid_system=asdict(joint_pool_system(b0_t)),
            estimated_work=work, duration_s=duration, rf_energy_uT2_s=len(controls)*len(offsets)*b1_uT*b1_uT*count*pulse,
            duty_cycle=duty, controls={k:list(v) for k,v in controls.items()},
            state_convention='Mx/My/Mz per liquid, bound Z, affine 1; equilibrium independent offsets',
            bound_lineshape=lineshape))


def search_cest_power(powers_uT, *, max_rf_energy_uT2_s=100., **kwargs):
    powers = list(powers_uT)
    if not powers or len(powers) > 32 or not np.isfinite(max_rf_energy_uT2_s) or max_rf_energy_uT2_s <= 0:
        raise ValueError('bounded candidate grid and positive RF budget required')
    if 'b1_uT' in kwargs: raise ValueError('power belongs in candidate grid')
    points = []
    for power in powers:
        try:
            result = run_cest_mt_noe(b1_uT=power, **kwargs)
            feasible = result['provenance']['rf_energy_uT2_s'] <= max_rf_energy_uT2_s
            points.append(dict(power_uT=power, feasible=feasible, result=result,
                reason=None if feasible else 'RF energy proxy exceeds budget'))
        except ValueError as exc:
            points.append(dict(power_uT=power, feasible=False, reason=str(exc)))
    feasible = [p for p in points if p['feasible']]
    return dict(candidates=points, best=min(feasible, key=lambda p:p['result']['objective_loss']) if feasible else None,
        max_rf_energy_uT2_s=max_rf_energy_uT2_s, objective='maximize no-amide minus full Z at +3.5 ppm; finite teaching grid')
