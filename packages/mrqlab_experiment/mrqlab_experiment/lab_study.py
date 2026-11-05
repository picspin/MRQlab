"""Measured CPMG calibration around existing ExperimentGraphs and TSE imaging.

Known independent Gaussian noise, signed real echoes, ideal 180° CPMG and
monoexponential T2 only. Conditional uncertainty and holdout checks are research
model checks, not scanner validation or clinical calibration/certification.
"""
from __future__ import annotations
from hashlib import sha256
from itertools import product
from typing import Annotated, Literal
import csv
import io
import json
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .models import ExperimentGraph, TemplateRef
from .tse_imaging import run_tse_imaging
from .clinical import TissuePrior, TissuePriorSet

Number = Annotated[float, Field(allow_inf_nan=False)]
Positive = Annotated[float, Field(gt=0, le=1000000, allow_inf_nan=False)]
Seconds = Annotated[float, Field(ge=1e-6, le=10, allow_inf_nan=False)]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class EchoMeasurement(Strict):
    measurement_id: Identifier
    acquisition_id: Identifier
    tissue_id: Identifier
    split: Literal['calibration', 'holdout']
    echo_time_s: Seconds
    signal_a_u: Number = Field(ge=-1000000, le=1000000)
    std_a_u: Number = Field(ge=1e-12, le=1000000)


class EchoDataset(Strict):
    source_ref: Annotated[str, Field(min_length=1, max_length=1024)]
    origin: Literal['measured', 'synthetic']
    raw_file_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    signal_kind: Literal['signed_real'] = 'signed_real'
    noise_model: Literal['independent_gaussian_known_sigma'] = 'independent_gaussian_known_sigma'
    refocusing_degrees: Literal[180] = 180
    preparation: Literal['spoiled_periodic'] = 'spoiled_periodic'
    echo_spacing_s: Seconds = .008
    tr_s: Seconds = .4
    measurements: list[EchoMeasurement] = Field(min_length=12, max_length=512)

    @model_validator(mode='after')
    def independence_and_timing(self):
        ids = [row.measurement_id for row in self.measurements]
        if len(ids) != len(set(ids)): raise ValueError('measurement ids must be unique')
        partitions = {}
        for row in self.measurements:
            partitions.setdefault(row.acquisition_id, set()).add(row.split)
            echo = row.echo_time_s/self.echo_spacing_s
            if abs(echo-round(echo)) > 1e-7 or row.echo_time_s+.002 >= self.tr_s:
                raise ValueError('lab echoes must match the declared CPMG spacing and fit TR')
        if any(len(splits) != 1 for splits in partitions.values()):
            raise ValueError('calibration and holdout must use disjoint acquisition ids')
        tissues = {row.tissue_id for row in self.measurements}
        if len(tissues) != 2: raise ValueError('two measured tissue classes required')
        for tissue in tissues:
            for split in ['calibration', 'holdout']:
                times = {r.echo_time_s for r in self.measurements if r.tissue_id == tissue and r.split == split}
                if len(times) < 3: raise ValueError('each tissue needs three distinct calibration and three holdout echo times')
        return self


class TSEDesign(Strict):
    echoes: int = Field(default=4, ge=1, le=16)
    order: Literal['linear', 'centric'] = 'centric'
    echo_spacing_s: Number = Field(default=.008, ge=.006, le=.03)
    tr_s: Number = Field(default=.4, ge=.05, le=2)
    refocusing_angle: Number = Field(default=180., gt=0, le=180)
    refocusing_end_angle: Number = Field(default=180., gt=0, le=180)


class StudyTargets(Strict):
    max_psf_rms_voxels: Positive = 2.
    min_roi_image_contrast: Number = Field(default=.005, ge=0, le=1)
    max_holdout_standardized_residual: Positive = 4.
    max_calibration_reduced_chi2: Positive = 3.
    max_relative_t2_std: Number = Field(default=.25, gt=0, le=.4)
    uncertainty_std_multiplier: Number = Field(default=2., gt=0, le=3)
    max_design_duration_s: Positive = 100.
    max_rf_energy_relative: Positive = 1000.


class StudyBudget(Strict):
    max_work_per_simulation: int = Field(default=10000000, ge=1, le=100000000)
    max_total_work: int = Field(default=1000000000, ge=1, le=5000000000)


class LabStudy(Strict):
    schema_version: Literal['tse-lab-study-1'] = 'tse-lab-study-1'
    experiment: ExperimentGraph
    dataset: EchoDataset
    tissue_order: list[Identifier] = Field(min_length=2, max_length=2)
    labels: list
    candidates: list[TSEDesign] = Field(min_length=1, max_length=8)
    targets: StudyTargets = Field(default_factory=StudyTargets)
    budget: StudyBudget = Field(default_factory=StudyBudget)
    t2_bounds_s: list[Seconds] = Field(default_factory=lambda:[.005, 2.], min_length=2, max_length=2)

    @model_validator(mode='after')
    def supported_experiment(self):
        g = self.experiment
        if not isinstance(g.sequence, TemplateRef) or g.sequence.template != 'TSE3D' or g.engine.preferred != 'epg':
            raise ValueError('lab study currently calibrates TSE3D EPG ExperimentGraphs')
        if not isinstance(g.tissue, tuple) or len(g.tissue) != 2 or {t.id for t in g.tissue} != set(self.tissue_order) or len(set(self.tissue_order)) != 2:
            raise ValueError('tissue_order must bind both distinct ExperimentGraph tissue ids to labels 0/1')
        if {r.tissue_id for r in self.dataset.measurements} != set(self.tissue_order):
            raise ValueError('measurements must name the graph tissues explicitly')
        if not g.clinical_recipe or not g.clinical_recipe.question.research_question:
            raise ValueError('an explicit clinical research question is required')
        if g.objective is not None or g.physiology is not None or g.disturbances.items or g.sample.pools or g.sample.isochromats or g.sample.off_resonance_hz:
            raise ValueError('unsupported objectives, physiology, disturbances or sample overrides in lab TSE study')
        if any(t.flow_velocity_mps or t.exchange_rate_hz or t.bound_pool or t.diffusion_adc_mm2_s for t in g.tissue):
            raise ValueError('lab study requires independent relaxation tissues')
        if any(t.contrast_exposure is not None for t in g.tissue):
            raise ValueError('lab T2 calibration does not infer contrast-free baseline T2 from an exposed measurement; contrast_exposure unsupported here')
        if any(not np.isfinite([t.t1,t.t2,t.proton_density]).all() or not .001<=t.t1<=10 or not 0<t.t2<=10 or not 0<t.proton_density<=10 for t in g.tissue):
            raise ValueError('bounded finite independent T1/T2/PD priors required')
        if set(g.engine.options)-{'dwell_time','epg_kmax','max_work'}:
            raise ValueError('lab study cannot author additional engine/snapshot options')
        if self.t2_bounds_s[0]<.0001 or not self.t2_bounds_s[0] < self.t2_bounds_s[1]: raise ValueError('ordered T2 bounds required')
        def row(values): return isinstance(values,list) and 2<=len(values)<=16 and all(type(v) is int and v in (0,1) for v in values)
        if not 2<=len(self.labels)<=16 or not all(row(v) for v in self.labels) or len({len(v) for v in self.labels})!=1:
            raise ValueError('lab study requires an integer two-class 2D grid no larger than 16x16')
        if {v for r in self.labels for v in r}!={0,1}: raise ValueError('both tissue classes must occur in the label grid')
        return self


def json_safe(value):
    if isinstance(value,np.ndarray): return json_safe(value.tolist())
    if isinstance(value,np.generic): return json_safe(value.item())
    if isinstance(value,complex): return {'real':value.real,'imag':value.imag}
    if isinstance(value,dict): return {k:json_safe(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)): return [json_safe(v) for v in value]
    return value


def fingerprint(value):
    """Hash a typed JSON tree with IEEE-754 binary64 numeric semantics.

    Browser JSON changes 1.0 to 1 and -0 to 0. Numeric values therefore hash
    by their exact binary64 hex representation, with signed zero unified.
    Container/scalar tags prevent user-object/tag collisions. This is a named
    project format, not an implementation or claim of RFC 8785 conformance.
    """
    def canonical(v):
        if v is None: return ['null']
        if isinstance(v,bool): return ['boolean',v]
        if isinstance(v,str): return ['string',v]
        if isinstance(v,(int,float)):
            try: number=float(v)
            except OverflowError as exc: raise ValueError('JSON number is outside finite binary64 range') from exc
            if not np.isfinite(number): raise ValueError('finite binary64 JSON numbers required')
            return ['number',(0. if number==0 else number).hex()]
        if isinstance(v,list): return ['array',[canonical(item) for item in v]]
        if isinstance(v,dict):
            if not all(isinstance(key,str) for key in v): raise ValueError('JSON object keys must be strings')
            return ['object',[[key,canonical(v[key])] for key in sorted(v)]]
        raise ValueError('unsupported non-JSON record value')
    encoded=json.dumps(canonical(json_safe(value)),ensure_ascii=True,separators=(',',':'),allow_nan=False).encode()
    return sha256(encoded).hexdigest()


def import_echo_csv(raw: bytes, *, source_ref: str, origin: Literal['measured','synthetic'], echo_spacing_s=.008, tr_s=.4):
    """Strict UTF-8 CSV with explicit SI field names; no inferred units/splits."""
    if not isinstance(raw,bytes) or len(raw)>1000000: raise ValueError('CSV must be <=1 MB of UTF-8 bytes')
    try:
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
        expected=list(EchoMeasurement.model_fields)
        if not reader.fieldnames or len(reader.fieldnames)!=len(set(reader.fieldnames)) or set(reader.fieldnames)!=set(expected):
            raise ValueError('CSV headers must exactly name measurement_id, acquisition_id, tissue_id, split, echo_time_s, signal_a_u, std_a_u')
        rows=[]
        for source in reader:
            if len(rows)>=512 or None in source or any(v is None for v in source.values()): raise ValueError('invalid CSV row or row count')
            row=dict(source)
            for field in ['echo_time_s','signal_a_u','std_a_u']: row[field]=float(row[field])
            rows.append(EchoMeasurement.model_validate(row))
    except (UnicodeError,csv.Error,TypeError) as exc: raise ValueError('invalid measurement CSV') from exc
    return EchoDataset(source_ref=source_ref,origin=origin,raw_file_sha256=sha256(raw).hexdigest(),
        measurements=rows,echo_spacing_s=echo_spacing_s,tr_s=tr_s)


def calibrate_t2(dataset: EchoDataset, tissue_id: str, bounds_s, targets: StudyTargets):
    """Profile weighted signal-space LS, amplitude nuisance fitted on calibration only.

    A is the lab receiver/polarization amplitude, never applied to reconstructed
    images or used to hide amplitude errors. T1 and PD remain declared priors.
    """
    fit=[r for r in dataset.measurements if r.tissue_id==tissue_id and r.split=='calibration']
    hold=[r for r in dataset.measurements if r.tissue_id==tissue_id and r.split=='holdout']
    times=np.array([r.echo_time_s for r in fit]); values=np.array([r.signal_a_u for r in fit]); sigma=np.array([r.std_a_u for r in fit])
    weights=1/sigma**2; work=0
    def evaluate(log_t2):
        nonlocal work
        work+=len(fit)
        t2=np.exp(log_t2); decay=np.exp(-times/t2)
        denominator=float(np.dot(weights,decay*decay))
        amplitude=max(0.,float(np.dot(weights*decay,values)/denominator)) if denominator>np.finfo(float).tiny else 0.
        loss=float(np.sum(((values-amplitude*decay)/sigma)**2))
        return loss,amplitude,float(t2)
    low,high=np.log(bounds_s); grid=np.linspace(low,high,257)
    trials=[evaluate(x) for x in grid]; index=int(np.argmin([v[0] for v in trials]))
    left=grid[max(0,index-1)]; right=grid[min(len(grid)-1,index+1)]
    golden=(np.sqrt(5)-1)/2; c=right-golden*(right-left); d=left+golden*(right-left)
    fc=evaluate(c); fd=evaluate(d)
    for _ in range(64):
        if fc[0]<fd[0]: right=d; d=c; fd=fc; c=right-golden*(right-left); fc=evaluate(c)
        else: left=c; c=d; fc=fd; d=left+golden*(right-left); fd=evaluate(d)
    chi2,amplitude,t2=min([*trials,fc,fd],key=lambda v:v[0])
    decay=np.exp(-times/t2); prediction=amplitude*decay
    reasons=[]; at_bound=min(abs(t2-bounds_s[0]),abs(t2-bounds_s[1]))<=1e-5*t2
    if amplitude<=0 or at_bound: reasons.append('nonpositive fitted amplitude or T2 at search boundary')
    jac=np.column_stack([decay,prediction*times/t2**2])
    # Relative parameter scaling prevents units alone from inflating conditioning.
    relative_jac=jac*np.array([max(amplitude,1e-30),t2])[None,:]/sigma[:,None]
    condition=float(np.linalg.cond(relative_jac))
    if not np.isfinite(condition) or condition>1e8: reasons.append('T2/amplitude not identifiable under the declared noise')
    try: covariance=np.linalg.inv((jac/sigma[:,None]).T@(jac/sigma[:,None]))
    except np.linalg.LinAlgError:
        covariance=None; reasons.append('singular calibration information matrix')
    if covariance is not None and (not np.isfinite(covariance).all() or np.any(np.linalg.eigvalsh(covariance)<=0)):
        covariance=None; reasons.append('invalid calibration covariance')
    t2_std=float(np.sqrt(covariance[1,1])) if covariance is not None else None
    interval=[t2-targets.uncertainty_std_multiplier*t2_std,t2+targets.uncertainty_std_multiplier*t2_std] if t2_std is not None else None
    if interval is None or interval[0]<bounds_s[0] or interval[1]>bounds_s[1]: reasons.append('T2 uncertainty interval leaves declared calibration support')
    if t2_std is None or t2_std/t2>targets.max_relative_t2_std: reasons.append('relative T2 standard uncertainty exceeds target')
    reduced=chi2/(len(fit)-2)
    if reduced>targets.max_calibration_reduced_chi2: reasons.append('calibration residual/model mismatch')
    rows=[]
    for row in [*fit,*hold]:
        e=np.exp(-row.echo_time_s/t2); pred=float(amplitude*e)
        derivative=np.array([e,pred*row.echo_time_s/t2**2])
        parameter_variance=float(derivative@covariance@derivative) if covariance is not None else 0.
        predictive_std=float(np.sqrt(row.std_a_u**2+max(0.,parameter_variance)))
        rows.append(dict(measurement_id=row.measurement_id,acquisition_id=row.acquisition_id,split=row.split,
            echo_time_s=row.echo_time_s,observed_a_u=row.signal_a_u,std_a_u=row.std_a_u,predicted_a_u=pred,
            residual_a_u=row.signal_a_u-pred,predictive_std_a_u=predictive_std,
            standardized_residual=(row.signal_a_u-pred)/predictive_std))
    holdout_max=max(abs(r['standardized_residual']) for r in rows if r['split']=='holdout')
    if holdout_max>targets.max_holdout_standardized_residual: reasons.append('independent holdout model check failed')
    return dict(tissue_id=tissue_id,t2_s=t2,t2_std_s=t2_std,t2_interval_s=interval,lab_amplitude_a_u=amplitude,
        covariance= None if covariance is None else covariance.tolist(),relative_information_condition=condition if np.isfinite(condition) else None,
        calibration_chi2=chi2,calibration_reduced_chi2=reduced,holdout_max_standardized_residual=holdout_max,
        passed=not reasons,reasons=reasons,rows=rows,estimated_work=work,
        uncertainty_scope='local linearized covariance, known independent Gaussian sigma; rectangular T2 stress corners are not a joint confidence region')


def run_lab_study(study: LabStudy | dict):
    spec=LabStudy.model_validate(study); raw=spec.model_dump(mode='json')
    dataset_hash=fingerprint(raw['dataset']); fits=[]; work=0
    # An explicit upper bound on fitting evaluations prevents budget-free fitting.
    fit_reserve=2*325*len(spec.dataset.measurements)
    if fit_reserve>spec.budget.max_total_work: raise ValueError('calibration preflight exceeds total work budget')
    for tissue in spec.tissue_order:
        fit=calibrate_t2(spec.dataset,tissue,spec.t2_bounds_s,spec.targets); fits.append(fit); work+=fit['estimated_work']
    original=spec.experiment.model_dump(mode='json'); graph=spec.experiment.model_copy(deep=True)
    by_id={t.id:t for t in graph.tissue}
    graph.tissue=tuple(by_id[f['tissue_id']].model_copy(update={'t2':f['t2_s']}) for f in fits)
    graph.provenance.tags=(*graph.provenance.tags,'lab-dataset-sha256:'+dataset_hash)
    recipe=graph.clinical_recipe
    priors=TissuePriorSet(id=recipe.tissue_priors.id+'-measured-t2',version='1.0.0',
        tissues=tuple(TissuePrior.model_validate(t.model_dump()) for t in graph.tissue))
    graph.clinical_recipe=recipe.model_copy(update={'tissue_priors':priors,
        'measurement_objective':'minimize worst tissue PSF RMS subject to measured-T2 corner contrast, duration and RF-proxy targets'})
    graph_dict=graph.model_dump(mode='json'); calibrated=all(f['passed'] for f in fits)
    candidates=[]; simulations=[]; budget_incomplete=False; reserved=fit_reserve
    corners=list(product(*(f['t2_interval_s'] for f in fits))) if calibrated else []
    for index,design in enumerate(spec.candidates):
        entry=dict(index=index,design=design.model_dump(),executed=False,eligible=False,scenarios=[],reasons=[])
        if not calibrated:
            entry['reasons']=['calibration/holdout gate failed; no measured-prior design selection']; candidates.append(entry); continue
        scenarios=[('nominal',[f['t2_s'] for f in fits]),*[(f'corner-{i}',list(t2)) for i,t2 in enumerate(corners)]]
        nominal=None
        for name,t2 in scenarios:
            cap=spec.budget.max_work_per_simulation
            if reserved+cap>spec.budget.max_total_work:
                budget_incomplete=True; entry['reasons'].append('total work budget cannot cover complete scenario grid'); break
            reserved+=cap
            try:
                run=run_tse_imaging(spec.labels,**design.model_dump(),t2_s=t2,max_samples=4096,
                    max_work=cap,max_duration_s=10000.,experiment=graph_dict)
                actual_work=run['provenance']['estimated_work']; work+=actual_work
                ntrains=len(run['timeline']); preparation_trains=round(run['provenance']['preparation_duration_s']/design.tr_s)
                rf_energy=(ntrains+preparation_trains)*(.25+sum((angle/180)**2 for angle in run['timeline'][0]['refocusing_degrees']))
                image=np.asarray(run['image']).real; labels=np.asarray(spec.labels)
                contrast=float(abs(image[labels==0].mean()-image[labels==1].mean()))
                train_contrast=float(abs(np.diff(run['tissue_echo_weights'].mean(axis=1))[0]))
                psf=max(p['rms_radius_voxels'] for p in run['psfs']); duration=run['provenance']['total_duration_s']
                checks=dict(psf=psf<=spec.targets.max_psf_rms_voxels,contrast=contrast>=spec.targets.min_roi_image_contrast,
                    duration=duration<=spec.targets.max_design_duration_s,rf_proxy=rf_energy<=spec.targets.max_rf_energy_relative,
                    forward_consistency=run['psf_prediction_quality']['passed'])
                evidence=dict(name=name,t2_s=t2,max_psf_rms_voxels=psf,roi_image_contrast=contrast,train_mean_signal_contrast=train_contrast,
                    duration_s=duration,rf_energy_relative=rf_energy,checks=checks,passed=all(checks.values()),
                    run_hash=fingerprint(run),provenance=run['provenance'])
                entry['scenarios'].append(evidence)
                if name=='nominal': nominal=run
            except ValueError as exc:
                work+=cap  # Failed calls may consume the cap; never account them as free.
                entry['reasons'].append(str(exc)); break
        entry['executed']=len(entry['scenarios'])==len(scenarios)
        if entry['executed']:
            entry['worst_psf_rms_voxels']=max(s['max_psf_rms_voxels'] for s in entry['scenarios'])
            entry['eligible']=all(s['passed'] for s in entry['scenarios'])
            if not entry['eligible']: entry['reasons'].append('one or more declared targets fail at nominal or uncertainty corner')
        candidates.append(entry); simulations.append(nominal)
    eligible=[p for p in candidates if p['eligible']]
    selected=min(eligible,key=lambda p:p['worst_psf_rms_voxels']) if eligible and not budget_incomplete else None
    selected_index=selected['index'] if selected else None
    selected_run=simulations[selected_index] if selected_index is not None else None
    fit_evidence=[{**{k:v for k,v in f.items() if k not in {'rows','passed','reasons','holdout_max_standardized_residual'}},
        'rows':[row for row in f['rows'] if row['split']=='calibration']} for f in fits]
    calibration_rows=[row for row in raw['dataset']['measurements'] if row['split']=='calibration']
    holdout_rows=[row for row in raw['dataset']['measurements'] if row['split']=='holdout']
    protocol={k:v for k,v in raw['dataset'].items() if k not in {'measurements','raw_file_sha256','source_ref'}}
    holdout_evidence=[dict(tissue_id=f['tissue_id'],holdout_max_standardized_residual=f['holdout_max_standardized_residual'],
        passed=f['passed'],reasons=f['reasons'],rows=[row for row in f['rows'] if row['split']=='holdout']) for f in fits]
    stages=[]
    for name,inputs,output,dependencies in [
        ('measurements',raw['dataset'],dataset_hash,[]),
        ('calibration',dict(rows=calibration_rows,protocol=protocol,bounds_s=raw['t2_bounds_s']),fingerprint(fit_evidence),['measurements']),
        ('independent_holdout_validation',dict(rows=holdout_rows,calibration_sha256=fingerprint(fit_evidence),policy=raw['targets']),fingerprint(holdout_evidence),['calibration','measurements']),
        ('calibrated_experiment',dict(experiment_sha256=fingerprint(original),calibration_sha256=fingerprint(fit_evidence),holdout_sha256=fingerprint(holdout_evidence)),fingerprint(graph_dict),['calibration','independent_holdout_validation']),
        ('design_search',dict(experiment_sha256=fingerprint(graph_dict),candidates=raw['candidates'],targets=raw['targets']),fingerprint(candidates),['calibrated_experiment']),
        ('target_validation',dict(search_sha256=fingerprint(candidates)),fingerprint(dict(selected_index=selected_index,budget_incomplete=budget_incomplete)),['design_search'])]:
        stages.append(dict(id=name,input_sha256=fingerprint(inputs),output_sha256=output,derived_from=dependencies))
    result=dict(clinical_question=recipe.question.model_dump(mode='json'),original_experiment=original,
        calibrated_experiment=graph_dict,calibration=fits,candidates=candidates,selected_index=selected_index,
        selected_simulation=selected_run,validation=dict(calibration_and_holdout_passed=calibrated,
            complete_budgeted_search=calibrated and not budget_incomplete,selected_design_passed=selected is not None),
        targets=raw['targets'],provenance=dict(dataset_sha256=dataset_hash,study_input_sha256=fingerprint(raw),
            stages=stages,estimated_work=work,reserved_work=reserved,
            selection='minimum worst tissue PSF RMS among candidates passing every nominal/rectangular T2 corner target; incomplete work budget disables selection',
            assumptions=['lab amplitude is a calibration nuisance; no reconstructed image gain fit',
                'only T2 is calibrated; T1/PD remain explicitly authored priors',
                'contrast is the absolute difference of real reconstructed image means in the two supplied label ROIs; no gain fit',
                'signed-real independent known Gaussian noise and ideal 180-degree spoiled periodic CPMG for lab data',
                'rectangular local T2 uncertainty corners are stress tests, not joint clinical confidence bounds']),
        scope='teaching/research measured-input model checks; no scanner validation or clinical quality certification; B/C parked')
    return json_safe(result)


def build_lab_study_example():
    """Explicit synthetic analytic CPMG data, never presented as measured data."""
    from .family_recipes import build_family_recipe
    graph=build_family_recipe('brain_t1_3d_tse')
    question=graph.clinical_recipe.question.model_copy(update=dict(anatomy='research phantom',
        research_question='Which TSE train preserves declared phantom tissue contrast with bounded PSF after independent CPMG T2 calibration?',
        target_finding='research phantom contrast and PSF',
        contrast_mechanism='measured-input T2 calibration plus authored T1/PD; EPG echo weighting and ideal Cartesian encoding'))
    graph.clinical_recipe=graph.clinical_recipe.model_copy(update={'question':question})
    graph.name='Measured-input phantom TSE design study'
    rows=[]
    for tissue,t2 in zip(graph.tissue,[.04,.12]):
        for split,indices in [('calibration',[1,3,5,7]),('holdout',[2,4,6,8])]:
            for i in indices:
                rows.append(EchoMeasurement(measurement_id=f'{tissue.id}-{i}',acquisition_id=split,
                    tissue_id=tissue.id,split=split,echo_time_s=i*.008,
                    signal_a_u=float(.4*np.exp(-i*.008/t2)),std_a_u=.0005))
    y,x=np.indices((16,16)); labels=(((x-8)**2+(y-8)**2)<20).astype(int)
    return LabStudy(experiment=graph,dataset=EchoDataset(source_ref='synthetic:analytic-cpmg-example-v1',origin='synthetic',measurements=rows),
        tissue_order=[t.id for t in graph.tissue],labels=labels.tolist(),
        candidates=[TSEDesign(echoes=n) for n in [2,4,8]])
