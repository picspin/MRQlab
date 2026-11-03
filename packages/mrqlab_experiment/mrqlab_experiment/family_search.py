"""Simulation-backed family searches with replayable, per-run provenance.

Family losses are explicit research criteria. No optimizer uses a closed-form
signal surrogate. Every candidate executes the authored pulses in the kernel.
"""
import math
from time import perf_counter
import numpy as np
from pydantic import BaseModel, ConfigDict
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from .models import TemplateRef
from .kernel import run_experiment
from .observations import build_result_graph
from .family_execution import adc_map


class FamilySearchPoint(BaseModel):
    model_config=ConfigDict(frozen=True)
    parameters: dict[str,float]
    objective_loss: float
    measurements: dict
    provenance: tuple[dict,...]
    duration_s: float
    rf_energy_relative: float
    rf_energy_unit: str
    elapsed_s: float
    feasible: bool


class FamilySearchResult(BaseModel):
    model_config=ConfigDict(frozen=True)
    elapsed_s: float
    baseline_experiment: dict
    parameter_units: dict[str,str]
    baseline: FamilySearchPoint
    candidates: tuple[FamilySearchPoint,...]
    best: FamilySearchPoint | None
    clinical_question: str
    objective: str
    scope: str='research teaching models; RF energy proxy, not SAR; no hardware certification'


from .family_recipes import OBJECTIVES

PARAMETER_UNITS={"te":"s","tr":"s","refocusing_flip_angle":"deg","refocusing_end_angle":"deg",
                 "flip_angle":"deg","inversion_time_s":"s","inflow_fraction":"dimensionless",
                 "diffusion_gradient_mt_m":"mT/m","saturation_power_uT":"uT","saturation_duration_s":"s","readout_s":"s"}

ALLOWED={
 'TSE3D':{'te','tr','refocusing_flip_angle','refocusing_end_angle'},
 'SSFP':{'flip_angle','inversion_time_s','inflow_fraction'},
 'EPSE':{'diffusion_gradient_mt_m'},
 'CEST':{'saturation_power_uT','saturation_duration_s'},
 'PRESS':{'te','readout_s'},
}


def peak_integrals(signal, dwell_s, centers_hz, half_width_hz=8.):
    """Phased absorption-spectrum integration, no full-spectrum fit.

    PRESS echo convention is -i. Finite windows, leakage and overlap bias areas.
    Caller must supply known peak windows. Ratios are relative signal amounts,
    without water-content, proton-number or relaxation corrections.
    """
    signal=np.asarray(signal,complex)
    if signal.ndim!=1 or signal.size<4 or not np.isfinite(signal).all() or dwell_s<=0 or half_width_hz<=0:
        raise ValueError('invalid spectral readout')
    freq=np.fft.fftfreq(signal.size,dwell_s)
    absorption=np.real(np.fft.fft(1j*signal)*dwell_s)
    df=1/(signal.size*dwell_s)
    out={}
    for name,center in centers_hz.items():
        if abs(center)+half_width_hz >= .5/dwell_s:
            raise ValueError('peak window exceeds Nyquist bandwidth')
        mask=abs(freq-center)<=half_width_hz
        if mask.sum()<3:
            raise ValueError('peak window undersampled; lengthen readout')
        out[name]=float(absorption[mask].sum()*df)
    return out


def evaluate_family(graph):
    """Execute the complete family measurement, including its controls."""
    family=graph.sequence.template if isinstance(graph.sequence,TemplateRef) else 'CEST'
    runs=[]; provenances=[]
    def run(g):
        r=run_experiment(g); obs=build_result_graph(r)
        runs.append(r); provenances.append(obs.observations[0].provenance.model_dump(mode='json'))
        return r
    if family in {'TSE3D','SSFP','EPSE'}:
        measures=[]; adcs=[]; b=None
        if not isinstance(graph.tissue,tuple) or len(graph.tissue)!=2:
            raise ValueError('family contrast requires target and reference tissues')
        for tissue in graph.tissue:
            g=graph.model_copy(deep=True); g.tissue=tissue
            if family=='SSFP':
                g.sequence.params['blood_compartment']=int(tissue.id=='blood')
            r=run(g); measures.append(float(np.mean(np.abs(r.sim_result.signal))))
            if family=='EPSE':
                b=r.sim_result.meta['b_value_s_mm2']
                g.sequence.params['diffusion_gradient_mt_m']=0.
                reference=run(g)
                if b>0:
                    adcs.append(float(adc_map([0,b], [np.mean(abs(reference.sim_result.signal)),measures[-1]])))
        loss= -abs(measures[0]-measures[1]) if family=='TSE3D' else -(measures[0]-measures[1])
        metrics=dict(target_signal=measures[0],reference_signal=measures[1])
        if family=='EPSE': metrics.update(b_value_s_mm2=b,adc_mm2_s=adcs)
    elif family=='CEST':
        r=run(graph); g=graph.model_copy(deep=True)
        matrix=np.asarray(g.sequence.metadata['cest']['exchange_matrix_hz'])
        g.sequence.metadata['cest']['exchange_matrix_hz']=np.zeros_like(matrix).tolist()
        control=run(g)
        offsets=r.sim_result.z_spectrum['offset_ppm']
        match=np.flatnonzero(np.isclose(offsets,3.5))
        if match.size!=1: raise ValueError('CEST search requires a 3.5 ppm target sample')
        i=match[0]
        z=float(r.sim_result.z_spectrum['Z'][i]); ref=float(control.sim_result.z_spectrum['Z'][i])
        loss=-abs(z-ref); metrics=dict(water_z=z,no_exchange_z=ref)
    elif family=='PRESS':
        r=run(graph); g=graph.model_copy(deep=True)
        g.sample.pools=(dict(name='water',fraction=1.,chemical_shift_ppm=0.,t1=1.,t2=.2),)
        reference=run(g)
        dwell=graph.engine.options.get('dwell_time',.001)
        centers={p['name']:p['chemical_shift_ppm']*GAMMA_BAR_HZ_T*graph.effective_scanner.b0_t*1e-6 for p in graph.sample.pools}
        peaks=peak_integrals(r.sim_result.signal,dwell,centers)
        water=peak_integrals(reference.sim_result.signal,dwell,{'water':0.})['water']
        if water<=0: raise ValueError('nonpositive water integral')
        ratios={k:v/water for k,v in peaks.items()}
        truth={p['name']:p['fraction'] for p in graph.sample.pools}
        loss=sum(abs(ratios[k]/truth[k]-1) for k in ratios)
        metrics=dict(peak_areas=peaks,water_area=water,relative_amounts=ratios,teaching_truth=truth)
    else:
        raise ValueError('unsupported family')
    if not math.isfinite(loss): raise ValueError('nonfinite family objective')
    # Include TSE conditioning trains, inversion delay, and every control.
    duration=sum(r.sequence.duration+r.sim_result.meta.get("preparation_duration_s",0.) for r in runs)
    energy=sum((e.value/180)**2 for r in runs for e in r.sequence.channel('rf_amp'))
    energy+=sum(r.sim_result.meta.get('preparation_rf_energy_relative',0.) for r in runs)
    if family=='CEST':
        duration=sum(r.sequence.metadata['cest']['saturation_duration_s']*(len(r.sequence.metadata['cest']['offsets_ppm'])+1) for r in runs)
        energy=sum(r.sequence.metadata['cest']['saturation_power_uT']**2*r.sequence.metadata['cest']['saturation_duration_s']*len(r.sequence.metadata['cest']['offsets_ppm']) for r in runs)
    return family,loss,metrics,tuple(provenances),duration,energy


def search_family_parameters(graph,candidates,*,max_duration_s,max_rf_energy_relative):
    if graph.clinical_recipe is None:
        raise ValueError('family search requires a clinical question')
    for limit in (max_duration_s,max_rf_energy_relative):
        if isinstance(limit,bool) or not math.isfinite(limit) or limit<=0:
            raise ValueError('finite positive search budgets required')
    family=graph.sequence.template if isinstance(graph.sequence,TemplateRef) else 'CEST'
    if family not in ALLOWED: raise ValueError('unsupported family')
    if graph.clinical_recipe.measurement_objective != OBJECTIVES[family]:
        raise ValueError('family search requires its declared measurement objective')
    def evaluate(patch):
        if set(patch)-ALLOWED[family]: raise ValueError('unsupported family search parameter')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in patch.values()):
            raise ValueError('finite numeric parameters required')
        tick=perf_counter(); g=graph.model_copy(deep=True)
        if family=='CEST': g.sequence.metadata['cest'].update(patch)
        else: g.sequence.params.update(patch)
        _,loss,metrics,provenance,duration,energy=evaluate_family(g)
        return FamilySearchPoint(parameters=patch,objective_loss=loss,measurements=metrics,provenance=provenance,
            duration_s=duration,rf_energy_relative=energy,rf_energy_unit="uT^2 s" if family=="CEST" else "sum(flip_deg/180)^2",elapsed_s=perf_counter()-tick,
            feasible=duration<=max_duration_s and energy<=max_rf_energy_relative)
    started=perf_counter()
    baseline=evaluate({}); points=tuple(evaluate(dict(p)) for p in candidates)
    if not points: raise ValueError('at least one search candidate required')
    feasible=[p for p in (baseline,*points) if p.feasible]
    return FamilySearchResult(elapsed_s=perf_counter()-started,baseline_experiment=graph.model_dump(mode="json"),parameter_units={k:PARAMETER_UNITS[k] for p in points for k in p.parameters},baseline=baseline,candidates=points,best=min(feasible,key=lambda p:p.objective_loss) if feasible else None,
        clinical_question=graph.clinical_recipe.question.research_question,objective=OBJECTIVES[family])
