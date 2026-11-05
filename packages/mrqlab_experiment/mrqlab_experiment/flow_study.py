"""Velocity measurements -> conditional pressure fit -> finite-RF causal DIR.

Rigid Newtonian pipe and known geometry/fluid/frequency/clock priors. Independent
known-sigma velocity errors, retained raw CSV, independent acquisition holdout.
No measured-data authenticity or patient/scanner certification is inferred.
"""
import base64
import csv
from hashlib import sha256
import io
from itertools import product
from typing import Literal
import numpy as np
from pydantic import Field,model_validator
from .lab_study import Strict,Number,Identifier,fingerprint,json_safe
from .pulsatile_flow import WomersleyPipe
from .pulsatile_dir import run_pulsatile_dir
from .study_records import _checked_sources,runtime_manifest


class VelocityMeasurement(Strict):
    measurement_id: Identifier
    acquisition_id: Identifier
    split: Literal['calibration','holdout']
    time_s: Number=Field(ge=0,le=30.)
    radius_m: Number=Field(ge=0,le=.1)
    velocity_m_s: Number=Field(ge=-10.,le=10.)
    std_m_s: Number=Field(ge=1e-8,le=1.)


def _csv_rows(raw):
    if not isinstance(raw,bytes) or not 1<=len(raw)<=1000000: raise ValueError('flow CSV must contain 1..1000000 UTF-8 bytes')
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames) or set(reader.fieldnames)!=set(VelocityMeasurement.model_fields):
            raise ValueError('flow CSV headers must exactly name measurement_id,acquisition_id,split,time_s,radius_m,velocity_m_s,std_m_s')
        rows=[]
        for source in reader:
            if len(rows)>=256 or None in source or any(v is None for v in source.values()): raise ValueError('invalid bounded flow CSV row')
            row=dict(source)
            for key in ['time_s','radius_m','velocity_m_s','std_m_s']: row[key]=float(row[key])
            rows.append(VelocityMeasurement.model_validate(row))
    except (UnicodeError,csv.Error,TypeError) as exc: raise ValueError('invalid flow CSV') from exc
    return rows


class VelocityDataset(Strict):
    source_ref: str=Field(min_length=1,max_length=1024)
    origin: Literal['measured','synthetic']
    noise_model: Literal['independent_gaussian_known_sigma']='independent_gaussian_known_sigma'
    time_reference: Literal['shared_with_simulation_and_r_peaks']='shared_with_simulation_and_r_peaks'
    raw_file_sha256: str | None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    raw_csv_base64: str | None=Field(default=None,max_length=1333340)
    measurements: list[VelocityMeasurement]=Field(min_length=12,max_length=256)

    @model_validator(mode='after')
    def independence_and_archive(self):
        ids=[r.measurement_id for r in self.measurements]
        if len(ids)!=len(set(ids)): raise ValueError('flow measurement ids must be unique')
        acquisitions={}
        for r in self.measurements: acquisitions.setdefault(r.acquisition_id,set()).add(r.split)
        if any(len(v)!=1 for v in acquisitions.values()): raise ValueError('flow calibration/holdout acquisition ids must be disjoint')
        for split in ['calibration','holdout']:
            rows=[r for r in self.measurements if r.split==split]
            if len(rows)<6 or len({r.time_s for r in rows})<3: raise ValueError('each flow split needs six samples and three distinct times')
        if (self.raw_file_sha256 is None)!=(self.raw_csv_base64 is None): raise ValueError('raw CSV archive and byte hash must occur together')
        if self.raw_csv_base64 is not None:
            try: raw=base64.b64decode(self.raw_csv_base64,validate=True)
            except (ValueError,TypeError) as exc: raise ValueError('invalid raw CSV base64 archive') from exc
            if sha256(raw).hexdigest()!=self.raw_file_sha256: raise ValueError('raw CSV byte hash mismatch')
            parsed=[r.model_dump(mode='json') for r in _csv_rows(raw)]
            if fingerprint(parsed)!=fingerprint([r.model_dump(mode='json') for r in self.measurements]): raise ValueError('parsed flow rows differ from archived CSV')
        return self


def import_velocity_csv(raw,*,source_ref,origin):
    return VelocityDataset(source_ref=source_ref,origin=origin,measurements=_csv_rows(raw),
        raw_file_sha256=sha256(raw).hexdigest(),raw_csv_base64=base64.b64encode(raw).decode())


class FlowPriors(Strict):
    radius_m: Number=Field(default=.002,ge=.0001,le=.02)
    density_kg_m3: Number=Field(default=1060.,ge=500.,le=2000.)
    viscosity_pa_s: Number=Field(default=.0035,ge=.0001,le=.1)
    frequency_hz: Number=Field(default=1.,ge=.01,le=10.)


class FlowAcquisition(Strict):
    r_peaks_s: list[Number]=Field(default_factory=lambda:[0.,1.,2.],min_length=1,max_length=32)
    observation_end_s: Number=Field(default=3.,gt=0,le=30.)
    trigger_latency_s: Number=Field(default=.003,ge=0,le=.1)
    initial_rr_s: Number=Field(default=1.,ge=.3,le=2.)
    rr_range_s: list[Number]=Field(default_factory=lambda:[.5,1.5],min_length=2,max_length=2)
    thickness_m: Number=Field(default=.005,ge=.001,le=.03)
    off_resonance_hz: Number=Field(default=0.,ge=-1000.,le=1000.)


class FlowDesign(Strict):
    inversion_time_s: Number=Field(default=.9,ge=.02,le=1.4)


class FlowNumerics(Strict):
    radial_rings: int=Field(default=8,ge=2,le=16)
    axial_spins: int=Field(default=401,ge=101,le=1001)
    rf_steps: int=Field(default=128,ge=16,le=256)


class FlowTargets(Strict):
    max_calibration_reduced_chi2: Number=Field(default=3.,gt=0,le=10.)
    max_holdout_standardized_residual: Number=Field(default=4.,gt=0,le=10.)
    max_holdout_reduced_chi2: Number=Field(default=3.,gt=0,le=10.)
    max_relative_pressure_std: Number=Field(default=.25,gt=0,le=1.)
    uncertainty_std_multiplier: Number=Field(default=2.,gt=0,le=3.)
    blood_target_max: Number=Field(default=.1,gt=0,lt=1.)
    wall_target_min: Number=Field(default=.7,gt=0,le=1.)
    max_interrupted_fraction: Number=Field(default=0.,ge=0,le=1.)
    max_observation_refinement_error: Number=Field(default=.01,gt=0,le=.1)


class FlowBudget(Strict):
    max_work_per_simulation: int=Field(default=50000000,ge=1,le=100000000)
    max_total_work: int=Field(default=2000000000,ge=1,le=10000000000)
    max_memory_bytes: int=Field(default=134217728,ge=1,le=134217728)


class FlowStudy(Strict):
    schema_version: Literal['flow-lab-study-1']='flow-lab-study-1'
    research_question: str=Field(min_length=1,max_length=4096)
    target_rationale: str=Field(min_length=1,max_length=4096)
    dataset: VelocityDataset
    priors: FlowPriors=Field(default_factory=FlowPriors)
    acquisition: FlowAcquisition=Field(default_factory=FlowAcquisition)
    candidates: list[FlowDesign]=Field(default_factory=lambda:[FlowDesign(inversion_time_s=.6),FlowDesign(inversion_time_s=.9)],min_length=1,max_length=3)
    numerics: FlowNumerics=Field(default_factory=FlowNumerics)
    targets: FlowTargets=Field(default_factory=FlowTargets)
    budget: FlowBudget=Field(default_factory=FlowBudget)

    @model_validator(mode='after')
    def measured_domain(self):
        if any(r.radius_m>self.priors.radius_m for r in self.dataset.measurements): raise ValueError('measured radius exceeds the declared pipe radius')
        # Validate the conditional fluid/frequency domain without fitting it.
        WomersleyPipe(**self.priors.model_dump(),mean_gradient_pa_m=0.,oscillating_gradient_pa_m=0.)
        from .causal_gating import plan_prospective_readouts
        plan_prospective_readouts(self.acquisition.r_peaks_s,delay_s=self.candidates[0].inversion_time_s,
            observation_end_s=self.acquisition.observation_end_s,initial_rr_s=self.acquisition.initial_rr_s,
            latency_s=self.acquisition.trigger_latency_s,rr_range_s=self.acquisition.rr_range_s)
        return self


def pressure_design(priors,rows):
    pipe=WomersleyPipe(**priors.model_dump(),mean_gradient_pa_m=1.,oscillating_gradient_pa_m=1.)
    radii=np.array([r.radius_m for r in rows]);steady,harmonic=pipe.coefficients(radii)
    phase=np.exp(2j*np.pi*priors.frequency_hz*np.array([r.time_s for r in rows]))
    response=harmonic*phase
    return np.column_stack([steady,response.real,response.imag])


def pressure_parameters(coefficients):
    mean,cosine,sine=coefficients
    return dict(mean_gradient_pa_m=float(mean),oscillating_gradient_pa_m=float(np.hypot(cosine,sine)),phase_rad=float(np.arctan2(-sine,cosine)))


def calibrate_pressure(dataset,priors,targets):
    fit=[r for r in dataset.measurements if r.split=='calibration'];hold=[r for r in dataset.measurements if r.split=='holdout']
    a=pressure_design(priors,fit);h=pressure_design(priors,hold)
    y=np.array([r.velocity_m_s for r in fit]);sigma=np.array([r.std_m_s for r in fit]);weighted=a/sigma[:,None]
    scale=np.linalg.norm(weighted,axis=0);reasons=[];base=dict(parameter_names=['mean','cosine','sine'],unit='Pa/m',calibration_count=len(fit),holdout_count=len(hold),
        estimated_work=int(256*(len(fit)+len(hold))),coefficients_pa_m=None,covariance_pa2_m2=None,std_pa_m=None,stress_intervals_pa_m=None,
        calibration_reduced_chi2=None,holdout_max_standardized_residual=None,holdout_reduced_chi2=None,relative_pressure_std=None,
        calibration_predictions=[],holdout_predictions=[],condition=None,passed=False)
    if np.any(scale==0): return {**base,'rank':int(np.linalg.matrix_rank(weighted)),'reasons':['unidentifiable pressure design: zero sensitivity column']}
    normalized=weighted/scale;rank=int(np.linalg.matrix_rank(normalized));condition=float(np.linalg.cond(normalized))
    if rank<3 or not np.isfinite(condition) or condition>1e6:
        return {**base,'rank':rank,'condition':condition if np.isfinite(condition) else None,'reasons':['unidentifiable or ill-conditioned pressure design']}
    coordinates=np.linalg.lstsq(normalized,y/sigma,rcond=None)[0];beta=coordinates/scale
    _,singular,vh=np.linalg.svd(normalized,full_matrices=False)
    covariance=((vh.T/singular**2)@vh)/np.outer(scale,scale);std=np.sqrt(np.diag(covariance))
    prediction=a@beta;hold_prediction=h@beta;residual=(prediction-y)/sigma
    hz=(hold_prediction-np.array([r.velocity_m_s for r in hold]))/np.array([r.std_m_s for r in hold])
    reduced=float(np.dot(residual,residual)/(len(fit)-3));hold_chi=float(np.dot(hz,hz)/len(hold));maximum=float(np.max(abs(hz)))
    relative=float(np.linalg.norm(std)/np.linalg.norm(beta)) if np.linalg.norm(beta)>1e-12 else None
    if reduced>targets.max_calibration_reduced_chi2: reasons.append('calibration velocity model check failed')
    if maximum>targets.max_holdout_standardized_residual or hold_chi>targets.max_holdout_reduced_chi2: reasons.append('independent acquisition holdout failed')
    if relative is None or relative>targets.max_relative_pressure_std: reasons.append('pressure uncertainty is too large or relative scale is undefined')
    try: WomersleyPipe(**priors.model_dump(),**pressure_parameters(beta))
    except ValueError as exc: reasons.append('fitted pressure outside physical domain: '+str(exc))
    intervals=np.column_stack([beta-targets.uncertainty_std_multiplier*std,beta+targets.uncertainty_std_multiplier*std])
    def measurements(rows,pred,z): return [dict(measurement_id=r.measurement_id,acquisition_id=r.acquisition_id,predicted_velocity_m_s=float(v),observed_velocity_m_s=r.velocity_m_s,
        standardized_residual=float(error)) for r,v,error in zip(rows,pred,z)]
    return dict(**{k:v for k,v in base.items() if k not in ['passed','condition']},rank=rank,condition=condition,passed=not reasons,reasons=reasons) | dict(coefficients_pa_m=beta.tolist(),covariance_pa2_m2=covariance.tolist(),std_pa_m=std.tolist(),stress_intervals_pa_m=intervals.tolist(),
        calibration_reduced_chi2=reduced,holdout_max_standardized_residual=maximum,holdout_reduced_chi2=hold_chi,relative_pressure_std=relative,
        calibration_predictions=measurements(fit,prediction,residual),holdout_predictions=measurements(hold,hold_prediction,hz),
        fit_convention='weighted velocity-space LS on calibration only; complete known-sigma covariance, not residual-scaled; lossless parameter-column conditioning')


def _observations(run):
    out=[]
    for frame in run['readouts']:
        row=[]
        for tissue in ['blood','wall']:
            d=frame['tissues'][tissue];row.extend([d['mean_mz'],*d['signal']])
        out.append(row)
    return np.asarray(out)


def run_flow_study(study):
    spec=FlowStudy.model_validate(study.model_dump(mode='json') if isinstance(study,FlowStudy) else study)
    sources=_checked_sources();request=spec.model_dump(mode='json');fit=calibrate_pressure(spec.dataset,spec.priors,spec.targets)
    targets=spec.targets;budget=spec.budget;n=spec.numerics;work=fit['estimated_work'];scenarios=[]
    if fit['passed']:
        scenarios=[dict(name='nominal',coefficients_pa_m=fit['coefficients_pa_m'])]
        scenarios += [dict(name='corner-'+str(i),coefficients_pa_m=list(b)) for i,b in enumerate(product(*fit['stress_intervals_pa_m']))]
    reserved=fit['estimated_work']+len(spec.candidates)*len(scenarios)*2*budget.max_work_per_simulation
    peak=int(1024*(2*n.radial_rings+1)*(2*n.axial_spins-1)+65536*len(scenarios)*len(spec.candidates))
    resources=reserved<=budget.max_total_work and peak<=budget.max_memory_bytes
    candidates=[];preview=None;preview_index=None
    for index,design in enumerate(spec.candidates):
        point=dict(index=index,design=design.model_dump(mode='json'),executed=False,eligible=False,scenarios=[],reasons=[])
        if not fit['passed']: point['reasons'].append('calibration/independent holdout failed; no flow prior applied')
        if not resources: point['reasons'].append('cannot reserve complete pressure uncertainty/refinement workflow')
        if fit['passed'] and resources:
            for scenario in scenarios:
                case=dict(**scenario,completed=False,passed=False,reasons=[]);runs=[]
                try:
                    parameters=dict(**spec.priors.model_dump(),**pressure_parameters(scenario['coefficients_pa_m']),**spec.acquisition.model_dump(),**design.model_dump(),
                        blood_target_max=targets.blood_target_max,wall_target_min=targets.wall_target_min,max_interrupted_fraction=targets.max_interrupted_fraction,
                        max_work=budget.max_work_per_simulation,max_duration_s=spec.acquisition.observation_end_s)
                    for factor in [1,2]:
                        try: run=run_pulsatile_dir(**parameters,radial_rings=factor*n.radial_rings,axial_spins=factor*(n.axial_spins-1)+1,rf_steps=factor*n.rf_steps)
                        except ValueError:
                            work+=budget.max_work_per_simulation  # conservative charge when partial execution cannot report exact work
                            raise
                        work+=run['provenance']['estimated_work'];runs.append(run)
                    coarse,fine=runs;ca=_observations(coarse);fa=_observations(fine)
                    same=ca.shape==fa.shape and [x['gate'] for x in coarse['readouts']]==[x['gate'] for x in fine['readouts']]
                    error=float(np.max(abs(ca-fa))) if same and ca.size else None
                    refinement=error is not None and error<=targets.max_observation_refinement_error
                    case.update(completed=True,coarse=coarse,refined=fine,max_observation_refinement_error=error,numerical_refinement_passed=refinement,
                        passed=bool(coarse['validation']['passed'] and fine['validation']['passed'] and refinement))
                    if not refinement: case['reasons'].append('RF/radial/axial observable refinement failed or no completed readout')
                    if not coarse['validation']['passed'] or not fine['validation']['passed']: case['reasons'].append('declared suppression/retention/interruption targets failed')
                    if scenario['name']=='nominal' and preview is None: preview=json_safe(fine);preview_index=index
                except ValueError as exc:
                    case['reasons'].append(str(exc));case['partial_runs']=runs
                point['scenarios'].append(json_safe(case))
            point['executed']=any(s['completed'] for s in point['scenarios'])
            point['eligible']=all(s['passed'] for s in point['scenarios']) and len(point['scenarios'])==9
            if not point['eligible']: point['reasons'].append('one or more nominal/pressure-corner/observable targets failed')
        candidates.append(point)
    eligible=[p for p in candidates if p['eligible']]
    selected=min(eligible,key=lambda p:max(s['refined']['objective_loss'] for s in p['scenarios']))['index'] if eligible else None
    if selected is not None:
        preview=candidates[selected]['scenarios'][0]['refined'];preview_index=selected
    if _checked_sources()!=sources: raise ValueError('source changed during measurement-derived flow study')
    result=dict(schema_version='flow-lab-result-1',research_question=spec.research_question,target_rationale=spec.target_rationale,
        calibration=fit,parameter_bindings=[dict(parameter=k,unit='Pa/m',value=v,source='calibration velocity rows only') for k,v in zip(['mean_pressure_gradient','cosine_pressure_gradient','sine_pressure_gradient'],fit['coefficients_pa_m'])] if fit['passed'] else [],
        candidates=candidates,selected_index=selected,preview_simulation=preview,preview_index=preview_index,
        validation=dict(calibration_and_holdout_passed=fit['passed'],complete_budget_reserved=resources,selected_design_passed=selected is not None),
        provenance=dict(sources=sources,runtime=runtime_manifest(),request_sha256=fingerprint(request),input_origin=spec.dataset.origin,source_ref=spec.dataset.source_ref,
            raw_file_sha256=spec.dataset.raw_file_sha256,raw_bytes_retained=spec.dataset.raw_csv_base64 is not None,
            estimated_work=work,reserved_work=reserved,estimated_peak_memory_bytes=peak,
            failed_attempt_work='each failed runner attempt is conservatively charged its full per-simulation cap; completed runs report their own work',
            conditional_priors=spec.priors.model_dump(mode='json'),uncertainty='marginal mean +/- multiplier*known-sigma standard errors; eight rectangular stress corners, not joint confidence or continuous robust guarantees',
            unchanged_priors='radius, fluid density/viscosity/frequency, clock alignment, blood/wall T1/T2 and RF waveform family are not calibrated by these data'),
        scope='teaching/research conditional measured-velocity Womersley pressure calibration and finite-RF causal DIR; input origin is user-declared, not authenticated; synthetic example is not patient data; no compliant/3D CFD, correlated errors, clinical concentration/target calibration, scanner validation or quality certification; B/C parked')
    return json_safe(result)


def build_flow_study_example():
    priors=FlowPriors();pipe=WomersleyPipe(**priors.model_dump(),mean_gradient_pa_m=100.,oscillating_gradient_pa_m=200.,phase_rad=.25)
    stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(list(VelocityMeasurement.model_fields))
    for split,offset in [('calibration',0.),('holdout',.037)]:
        for i,t in enumerate(np.arange(8)/8+offset):
            for j,r in enumerate([0.,.5*priors.radius_m]):
                velocity=float(pipe.velocity(r,float(t)))
                writer.writerow([f'{split}-{i}-{j}',f'{split}-run',split,format(t,'.17g'),format(r,'.17g'),format(velocity,'.17g'),'.001'])
    dataset=import_velocity_csv(stream.getvalue().encode(),source_ref='synthetic:analytic-womersley-velocity-v1',origin='synthetic')
    return FlowStudy(research_question='How do velocity-calibrated pressure and its conditional uncertainty change finite-slice DIR suppression under causal cardiac triggering?',
        target_rationale='Use independent acquisitions for pressure holdout; preserve blood <=0.1, wall >=0.7 and observable refinement <=0.01 across nominal plus eight pressure corners.',dataset=dataset)
