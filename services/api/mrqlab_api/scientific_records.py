"""Immutable local scientific records for every declared research runner.

A record checksum is integrity, not authenticity or scientific revalidation.
Lossless JSON strings preserve original numeric tokens across browser transport.
No scanner execution or arbitrary code/path endpoint.
"""
from __future__ import annotations
import argparse
from contextlib import closing
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time
from typing import Annotated, Literal
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from mrqlab_experiment.lab_study import LabStudy, fingerprint
from mrqlab_experiment.study_records import (
    _checked_sources, runtime_manifest, create_study_record, verify_study_record,
)
from mrqlab_experiment.calibrated_radial import CalibratedRadialStudy, run_calibrated_radial_study
from mrqlab_experiment.flow_study import FlowStudy,VelocityDataset,run_flow_study
from mrqlab_experiment.tse_control import apply_tse_edits
from mrqlab_experiment.sequence_operations import OperationSequence, apply_operation_edits, run_operation_sequence
from mrqlab_experiment.waveform_bloch import WaveformBlochPlan, run_waveform_bloch
from mrqlab_experiment.linked_readout import LinkedEdit, verify_linked_readout
from mrqlab_experiment.agentic_inference import infer_tissue_modalities, verify_agentic_inference
from .research import (
    RunRequest, SearchRequest, checked_source_hash, execute, search_research, _lab_response, serializable, present,
)

SCHEMA='mrqlab-scientific-record-1'
MAX_BYTES=128*1024*1024
HASH=re.compile(r'^[a-f0-9]{64}$')
SCOPE='teaching/research only; model targets and local replay, not scanner validation or clinical quality certification'
router=APIRouter(prefix='/research/records',tags=['local scientific records'])


class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False,str_strip_whitespace=True)


class BackgroundReference(Strict):
    source_ref: str=Field(min_length=1,max_length=1024)
    origin: Literal['authored','synthetic','measured']
    sha256: str | None=Field(default=None,pattern=r'^[a-f0-9]{64}$')
    note: str=Field(min_length=1,max_length=2048)
    usage: Literal['context_only']='context_only'


class StudyContext(Strict):
    study_id: str=Field(min_length=1,max_length=128,pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_.-]*$')
    research_question: str=Field(min_length=1,max_length=4096)
    target_rationale: str=Field(min_length=1,max_length=4096)
    assumptions: str=Field(default='',max_length=8192)
    background_references: list[BackgroundReference]=Field(default_factory=list,max_length=32)
    intended_use: Literal['teaching','research']='research'


class RunPlan(RunRequest):
    type: Literal['run']='run'


class SearchPlan(SearchRequest):
    type: Literal['search']='search'


class MeasuredPlan(Strict):
    type: Literal['measured_tse']='measured_tse'
    study: LabStudy


class MeasuredFlowPlan(Strict):
    type: Literal['measured_flow']='measured_flow'
    study: FlowStudy


class LinkedParentEdits(Strict):
    """Common bounded parent/edit carrier; physics is chosen by the adapter."""
    parent_record_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    parent_record: dict | None=None
    updates: list[LinkedEdit]=Field(min_length=1,max_length=8)


class AgenticInferencePlan(Strict):
    type: Literal['agentic_inference']='agentic_inference'
    parent_record_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    parent_record: dict | None=None
    reference_tissue_id: str | None=Field(default=None,min_length=1,max_length=128)
class EditedTSEPlan(LinkedParentEdits):
    type: Literal['edited_tse']='edited_tse'


class OperationSequencePlan(Strict):
    type: Literal['operation_sequence']='operation_sequence'
    parameters: OperationSequence


class WaveformPlan(Strict):
    type: Literal['waveform_bloch']='waveform_bloch'
    parameters: WaveformBlochPlan


class EditedOperationsPlan(LinkedParentEdits):
    type: Literal['edited_operations']='edited_operations'


class CalibratedRadialPlan(Strict):
    type: Literal['calibrated_radial_tse']='calibrated_radial_tse'
    parent_record_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    parent_record: dict | None=None
    study: CalibratedRadialStudy=Field(default_factory=CalibratedRadialStudy)


class ScientificPlan(Strict):
    context: StudyContext
    execution: Annotated[RunPlan | SearchPlan | MeasuredPlan | MeasuredFlowPlan | EditedTSEPlan | CalibratedRadialPlan | AgenticInferencePlan | OperationSequencePlan | EditedOperationsPlan | WaveformPlan,Field(discriminator='type')]
    expected_execution_hash: str | None=Field(default=None,pattern=r'^[a-f0-9]{64}$')


def _dump(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def _sha(value: str):
    return sha256(value.encode('utf-8')).hexdigest()


def _unique(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise ValueError('duplicate JSON key: '+key)
        result[key]=value
    return result


def _loads(value):
    def invalid(token): raise ValueError('nonfinite JSON number: '+token)
    return json.loads(value,object_pairs_hook=_unique,parse_constant=invalid)



def _validate_view(view):
    if not isinstance(view,dict): raise ValueError('malformed scientific preview')
    def numeric(values):
        return isinstance(values,list) and all(type(v) in (int,float) and math.isfinite(v) for v in values)
    images=view.get('images');curves=view.get('curves')
    if not isinstance(images,list) or len(images)>8 or not isinstance(curves,list) or len(curves)>32:
        raise ValueError('bounded scientific preview arrays required')
    for image in images:
        w=image.get('width');h=image.get('height');values=image.get('values')
        if (type(w) is not int or type(h) is not int or not 1<=w<=128 or not 1<=h<=128 or
                not numeric(values) or len(values)!=w*h or not isinstance(image.get('label'),str)):
            raise ValueError('invalid scientific image preview')
    for curve in curves:
        x=curve.get('x');y=curve.get('y')
        if not numeric(x) or not numeric(y) or len(x)!=len(y) or len(x)>10000 or not isinstance(curve.get('label'),str):
            raise ValueError('invalid scientific curve preview')
    if type(view.get('validation',{}).get('passed')) is not bool:
        raise ValueError('explicit model-reported target status required')
    if not all(isinstance(view.get(k),str) for k in ['x_label','y_label']) or not isinstance(view.get('metrics'),dict):
        raise ValueError('scientific preview axes/metrics required')
    if not numeric(list(view['metrics'].values())):
        raise ValueError('finite scientific preview metrics required')

def _validate_run(run, source):
    _validate_view(run.get('view') if isinstance(run,dict) else None)
    if not isinstance(run,dict) or run.get('source_hash')!=source:
        raise ValueError('research payload source differs')
    if run.get('replay_request',{}).get('expected_source_hash')!=source:
        raise ValueError('research replay source differs')
    # This is the original API hash convention, applied to the lossless payload.
    actual=sha256(json.dumps(run['result'],sort_keys=True,allow_nan=False).encode()).hexdigest()
    if run.get('result_hash')!=actual: raise ValueError('nested research result hash mismatch')
    if run.get('kind') in {'tse','sequence_operations'} and 'linked_readout' in run['result']:
        pair=run['result']['linked_readout'];verify_linked_readout(pair)
        if pair['provenance']['inputs_sha256']!=fingerprint(run['replay_request']['parameters']):
            raise ValueError('linked input pin differs from retained computation')


def _agentic_view(inference):
    """Bounded human preview of the identified proportions; 3D uses the center plane."""
    shape=inference['source']['shape'];images=[];curves=[]
    for modality in inference['modalities']:
        values=modality['values']
        if len(shape)==2:
            width,height=shape[1],shape[0];flat=values
        else:
            plane=shape[1]*shape[2];start=(shape[0]//2)*plane
            width,height=shape[2],shape[1];flat=values[start:start+plane]
        if width<=128 and height<=128 and len(flat)==width*height:
            images.append(dict(label=modality['label'],width=width,height=height,
                values=[float(value) for value in flat],scale_group=modality['id']))
    acquisition=inference['proportions']['acquisition']
    if acquisition['available']:
        times=[float(value) for value in inference['ingestion']['echo_times_s']]
        for tissue,values in acquisition['coefficients'].items():
            curves.append(dict(label=tissue,x=times,y=[float(value) for value in values]))
        x_label='Echo time (s)';y_label='Identifiable relative coefficient'
    else:
        x_label='Echo time (s)';y_label='Unavailable'
    metrics={'Complete complex samples read':float(inference['ingestion']['sample_count']),
        'Parseval relative error':float(inference['ingestion']['parseval_relative_error'])}
    for tissue,item in inference['proportions']['image_signal'].items():
        metrics['Image signal share · '+tissue]=float(item['energy_fraction'])
    for tissue,item in inference['proportions']['structure'].items():
        metrics['Structure voxel fraction · '+tissue]=float(item['voxel_fraction'])
    validation=dict(inference['validation']['checks'],passed=inference['validation']['passed'])
    return dict(images=images,curves=curves,x_label=x_label,y_label=y_label,validation=validation,metrics=metrics)


def _edit_parent(execution):
    parent=execution['parent_record']
    if not isinstance(parent,dict) or parent.get('record_sha256')!=execution['parent_record_sha256']: raise ValueError('edit parent record identity mismatch')
    operation_mode=execution['type']=='edited_operations'
    edit_mode='edited_operations' if operation_mode else 'edited_tse'
    cursor=parent;depth=1
    while _loads(cursor['request_json'])['execution']['type'] in {'edited_tse','edited_operations'}:
        if _loads(cursor['request_json'])['execution']['type']!=edit_mode:
            raise ValueError('edit parent adapter lineage differs; mixed edit chains are unsupported')
        depth+=1
        if depth>3: raise ValueError('at most three '+('operation' if operation_mode else 'TSE')+' edit generations are supported; no unbounded parent replay')
        cursor=_loads(cursor['request_json'])['execution']['parent_record']
    verify_scientific_record(parent)
    payload=_loads(parent['payload_json'])
    if parent['summary']['mode']==edit_mode: run=payload['run']
    elif operation_mode and parent['summary']['mode']=='operation_sequence': run=payload
    elif not operation_mode and parent['summary']['mode']=='run' and parent['summary']['kind']=='tse': run=payload
    else: raise ValueError('semantic edits require a matching operation sequence parent' if operation_mode else 'semantic edits require a TSE run or edited TSE parent')
    if run['kind']!=('sequence_operations' if operation_mode else 'tse'):
        raise ValueError('edit parent adapter kind differs')
    if 'linked_readout' not in run['result']: raise ValueError('parent lacks complete linked image/signal data')
    return parent,run


def _run_origins(run):
    origins={'authored_model_inputs'}
    if run.get('kind') in {'sequence_operations','waveform_bloch'}: origins.add('synthetic')
    if run.get('kind')=='tse':
        for physical in run['result']['provenance']['physical']:
            for binding in physical.get('contrast_relaxation_bindings',[]): origins.add(binding['exposure']['origin'])
    return sorted(origins)


def _operation_run(parameters, source):
    result=run_operation_sequence(parameters)
    pair=result['linked_readout'];image=pair['image'];values=image['values']
    magnitude=[abs(complex(re,im)) for re,im in zip(values['real'],values['imag'])]
    view=dict(images=[dict(label='Static transverse snapshot magnitude',width=image['shape'][1],height=image['shape'][0],values=magnitude)],
              curves=[],x_label='voxel',y_label='a.u.',metrics=dict(preparation_duration_s=result['duration_s']),validation=result['validation'])
    run=dict(kind='sequence_operations',result=result,view=view,source_hash=source,
             replay_request=dict(kind='sequence_operations',parameters=result['provenance']['replay'],expected_source_hash=source))
    run['result_hash']=sha256(json.dumps(result,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return run


def _waveform_run(parameters, source):
    result=run_waveform_bloch(parameters)
    samples=result['samples'];times=[s['time_s'] for s in samples]
    view=dict(images=[],curves=[dict(label='ADC real',x=times,y=[s['real'] for s in samples]),
                               dict(label='ADC imaginary',x=times,y=[s['imag'] for s in samples])],
              x_label='Time (s)',y_label='Signal (a.u.)',
              metrics={'ADC samples':float(len(samples)), 'Voxel steps':float(result['work']['voxel_steps'])},
              validation=result['validation'])
    run=dict(kind='waveform_bloch',result=result,view=view,source_hash=source,
             replay_request=dict(kind='waveform_bloch',parameters=result['provenance']['replay'],expected_source_hash=source))
    run['result_hash']=sha256(json.dumps(result,sort_keys=True,allow_nan=False).encode()).hexdigest()
    return run



def _parent_measurement(execution):
    parent=execution.get('parent_record')
    if not isinstance(parent,dict) or parent.get('record_sha256')!=execution['parent_record_sha256']:
        raise ValueError('embedded parent identity differs from the declared record')
    # Only a direct measured-TSE parent is accepted: no recursive derived graphs
    # or arbitrary record types masquerading as calibrated measurement sources.
    request=_loads(parent.get('request_json','{}'))
    if request.get('execution',{}).get('type')!='measured_tse':
        raise ValueError('derived radial study requires a measured_tse parent record')
    verify_scientific_record(parent)
    return parent,_loads(parent['payload_json'])['record']

def _summary(request,payload,source):
    execution=request['execution']; mode=execution['type']
    if mode in {'run','operation_sequence','waveform_bloch'}:
        expected_kind=execution.get('kind') if mode=='run' else 'sequence_operations' if mode=='operation_sequence' else 'waveform_bloch'
        if expected_kind!=payload.get('kind'): raise ValueError('execution kind differs from payload')
        _validate_run(payload,source)
        if mode=='waveform_bloch':
            inputs=fingerprint(execution['parameters'])
            if (fingerprint(payload['replay_request']['parameters'])!=inputs or
                    fingerprint(payload['result']['provenance']['replay'])!=inputs):
                raise ValueError('waveform request and retained replay inputs differ')
        points=[dict(index=0,input_parameters_sha256=fingerprint(payload['replay_request']['parameters']),executable=True,
            model_reported_passed=payload['view']['validation']['passed'],validation=payload['view']['validation'])]
        kind=payload['kind'];selected=0;reported=points[0]['model_reported_passed']
        execution_hash=payload['result_hash'];origins=_run_origins(payload)
    elif mode in {'edited_tse','edited_operations'}:
        parent,original=_edit_parent(execution);run=payload['run'];_validate_run(run,source)
        if payload['parent_record_sha256']!=parent['record_sha256'] or parent['api_source_hash']!=source: raise ValueError('edited linked parent/source differs')
        if run['kind']!=original['kind']: raise ValueError('edited run adapter kind differs from parent')
        if fingerprint(payload['updates'])!=fingerprint(execution['updates']): raise ValueError('applied semantic edits differ from retained request')
        if payload['parameters_before_sha256']!=fingerprint(original['replay_request']['parameters']) or payload['parameters_after_sha256']!=fingerprint(run['replay_request']['parameters']):
            raise ValueError('edit parameter dependency hashes differ')
        reported=run['view']['validation']['passed'];kind=original['kind'];selected=0;execution_hash=run['result_hash'];origins=_run_origins(run)
        points=[dict(index=0,executable=True,model_reported_passed=reported,validation=run['view']['validation'])]
    elif mode=='search':
        if execution.get('kind')!=payload.get('kind'): raise ValueError('execution kind differs from payload')
        if payload.get('source_hash')!=source or payload.get('replay_search',{}).get('expected_source_hash')!=source:
            raise ValueError('search source differs')
        if payload.get('search_hash')!=sha256(json.dumps(payload['candidates'],sort_keys=True,allow_nan=False).encode()).hexdigest():
            raise ValueError('nested candidate hash mismatch')
        points=[];selected=None
        for i,p in enumerate(payload['candidates']):
            if p['feasible']:
                _validate_run(p['run'],source)
                points.append(dict(index=i,parameters=p['parameters'],executable=True,
                    model_reported_passed=p['run']['view']['validation']['passed'],validation=p['run']['view']['validation']))
            else: points.append(dict(index=i,parameters=p['parameters'],executable=False,model_reported_passed=False,reason=p['reason']))
            if payload['best'] is not None and _dump(p)==_dump(payload['best']): selected=i
        if payload['best'] is not None and selected is None: raise ValueError('selected result is not a candidate')
        reported=selected is not None and points[selected]['model_reported_passed']
        kind=payload['kind'];execution_hash=payload['search_hash']
        origins=sorted({'authored_model_inputs'}|{origin for p in payload['candidates'] if p['feasible'] for origin in _run_origins(p['run'])})
    elif mode=='measured_tse':
        legacy=payload['record'];verify_study_record(legacy)
        if payload['view'] is not None: _validate_view(payload['view'])
        r=legacy['result'];selected=r['selected_index'];reported=r['validation']['selected_design_passed']
        points=[dict(index=p['index'],parameters=p['design'],executable=p['executed'],
            model_reported_passed=p['eligible'],reasons=p['reasons']) for p in r['candidates']]
        kind='measured_tse';execution_hash=legacy['record_sha256'];origins=[legacy['request']['dataset']['origin']]
    elif mode=='measured_flow':
        r=payload['flow_study']
        dataset=VelocityDataset.model_validate(execution['study']['dataset'])
        if any(r['provenance'][key]!=value for key,value in [('input_origin',dataset.origin),('source_ref',dataset.source_ref),('raw_file_sha256',dataset.raw_file_sha256)]):
            raise ValueError('flow result measurement origin/archive differs from retained input')
        if fingerprint(execution['study'])!=r['provenance']['request_sha256']: raise ValueError('flow result input hash differs from retained measurement request')
        if payload['view'] is not None: _validate_view(payload['view'])
        selected=r['selected_index'];reported=r['validation']['selected_design_passed'];kind=mode
        points=[dict(index=p['index'],parameters=p['design'],executable=p['executed'],model_reported_passed=p['eligible'],reasons=p['reasons']) for p in r['candidates']]
        origins=[execution['study']['dataset']['origin']];execution_hash=fingerprint(r)
    elif mode=='calibrated_radial_tse':
        parent,legacy=_parent_measurement(execution)
        r=payload['derivation']
        if r['parent_legacy_record_sha256']!=legacy['record_sha256']:
            raise ValueError('derived numerical source differs from embedded parent')
        if payload['view'] is not None: _validate_view(payload['view'])
        kind=mode;selected=r['selected_index'];reported=r['validation']['selected_design_passed']
        points=[dict(index=p['index'],parameters=p['design'],executable=p['executed'],
            model_reported_passed=p['eligible'],reasons=p['reasons'],
            validation={k:p[k] for k in ['worst_image_nrmse','worst_component_nrmse','worst_total_rf_energy'] if k in p}) for p in r['candidates']]
        origins=[r['input_origin']];execution_hash=fingerprint(r)
    elif mode=='agentic_inference':
        parent,original=_edit_parent(execution);_validate_run(original,source)
        pair=original['result']['linked_readout'];inference=payload['inference']
        verify_agentic_inference(inference)
        if payload['parent_record_sha256']!=parent['record_sha256'] or parent['api_source_hash']!=source:
            raise ValueError('agentic inference parent/source differs')
        if payload['parent_pair_sha256']!=pair['pair_sha256'] or inference['source']['pair_sha256']!=pair['pair_sha256']:
            raise ValueError('agentic inference pair differs from the retained parent')
        if (inference['source']['source_sha256']!=pair['provenance']['source_sha256']
                or inference['source']['runtime']!=pair['provenance']['runtime']):
            raise ValueError('agentic inference source/runtime pin differs from the linked parent')
        if payload['view'] is not None: _validate_view(payload['view'])
        kind=mode;selected=0;reported=inference['validation']['passed'];execution_hash=fingerprint(inference)
        points=[dict(index=0,executable=True,model_reported_passed=reported,validation=inference['validation'])]
        origins=_run_origins(original)
    else: raise ValueError('unknown scientific execution type')
    summary=dict(study_id=request['context']['study_id'],research_question=request['context']['research_question'],
        mode=mode,kind=kind,selected_index=selected,model_reported_passed=bool(reported),
        candidate_count=len(points),candidates=points,execution_hash=execution_hash,input_origins=origins,
        background_references_applied=False,scope=SCOPE)
    if mode in {'calibrated_radial_tse','edited_tse','edited_operations','agentic_inference'}: summary['parent_record_sha256']=execution['parent_record_sha256']
    if mode in {'edited_tse','edited_operations'}: summary['applied_edits_sha256']=fingerprint(execution['updates'])
    if mode=='agentic_inference':
        summary['inference_sha256']=fingerprint(payload['inference'])
        summary['parent_pair_sha256']=payload['parent_pair_sha256']
    if mode=='measured_flow': summary['calibration_sha256']=fingerprint(payload['flow_study']['calibration'])
    return summary


def _stages(request,request_hash,payload_hash,summary,environment):
    values=[('question',fingerprint(request['context'])),('design_and_inputs',request_hash),
            ('source_and_runtime',fingerprint(environment)),('computed_execution',payload_hash),('reported_validation',fingerprint(summary))]
    if request['execution']['type']=='calibrated_radial_tse':
        values.insert(1,('parent_measurement_record',request['execution']['parent_record_sha256']))
    if request['execution']['type'] in {'edited_tse','edited_operations'}:
        values[1:1]=[('parent_image_signal_record',request['execution']['parent_record_sha256']),('typed_parameter_edits',summary['applied_edits_sha256'])]
    if request['execution']['type']=='agentic_inference':
        values[1:1]=[('parent_image_signal_record',request['execution']['parent_record_sha256']),
                     ('agentic_signal_inference',summary['inference_sha256'])]
    if request['execution']['type']=='measured_flow':
        values=[values[0],('raw_velocity_measurements',fingerprint(request['execution']['study']['dataset'])),values[2],
            ('conditional_pressure_calibration',summary['calibration_sha256']),values[1],*values[3:]]
    nodes=[]
    for name,value in values:
        parents=[nodes[-1]['sha256']] if nodes else []
        body=dict(stage=name,parents=parents,value_sha256=value)
        nodes.append({**body,'sha256':fingerprint(body)})
    return nodes


def create_scientific_record(plan: ScientificPlan | dict, *, store=None):
    plan=ScientificPlan.model_validate(plan).model_copy(deep=True)
    if isinstance(plan.execution,(CalibratedRadialPlan,LinkedParentEdits,AgenticInferencePlan)) and plan.execution.parent_record is None:
        plan.execution.parent_record=(store or ScientificStore()).get(plan.execution.parent_record_sha256)
    sources=_checked_sources();api_source=checked_source_hash();runtime=runtime_manifest()
    request=plan.model_dump(mode='json');request_json=_dump(request)
    execution=plan.execution
    if isinstance(execution,LinkedParentEdits):
        parent,original=_edit_parent(request['execution'])
        replay_scientific_record(parent)  # never derive from an uncomputed imported result
        operation_mode=isinstance(execution,EditedOperationsPlan)
        apply_edits=apply_operation_edits if operation_mode else apply_tse_edits
        parameters=apply_edits(original['replay_request']['parameters'],execution.updates,pair=original['result']['linked_readout'])
        run=_operation_run(parameters,api_source) if operation_mode else execute(RunRequest(kind='tse',parameters=parameters,expected_source_hash=api_source),api_source)
        payload=dict(parent_record_sha256=parent['record_sha256'],updates=[u.model_dump(mode='json') for u in execution.updates],parent_computationally_replayed=True,
            parameters_before_sha256=fingerprint(original['replay_request']['parameters']),parameters_after_sha256=fingerprint(run['replay_request']['parameters']),run=run)
    elif isinstance(execution,AgenticInferencePlan):
        parent,original=_edit_parent(request['execution'])
        replay_scientific_record(parent)  # never infer from an uncomputed imported result
        pair=original['result']['linked_readout']
        inference=infer_tissue_modalities(pair,reference_tissue_id=execution.reference_tissue_id)
        payload=dict(parent_record_sha256=parent['record_sha256'],parent_computationally_replayed=True,
            parent_pair_sha256=pair['pair_sha256'],inference=inference,view=_agentic_view(inference))
    elif isinstance(execution,OperationSequencePlan):
        payload=_operation_run(execution.parameters,api_source)
    elif isinstance(execution,WaveformPlan):
        payload=_waveform_run(execution.parameters,api_source)
    elif isinstance(execution,CalibratedRadialPlan):
        parent,legacy=_parent_measurement(request['execution'])
        derived=run_calibrated_radial_study(legacy,execution.study)
        preview=derived['preview_simulation']
        # Reuse the established presenter with an explicit complex-array decoder.
        def decode(value):
            import numpy as np
            if isinstance(value,dict):
                if set(value)=={'real','imag'}: return complex(value['real'],value['imag'])
                return {k:decode(v) for k,v in value.items()}
            if isinstance(value,list):
                out=[decode(v) for v in value]
                if out and all(isinstance(v,(int,float,complex,list,np.ndarray)) for v in out):
                    try: return np.asarray(out)
                    except ValueError: pass
                return out
            return value
        view=present('radial_tse',decode(preview)) if preview is not None else None
        if view is not None and derived.get('reconstruction')=='navigator_t2':
            view['images'][-1]['label']='Fixed nominal-prior mismatch control (same samples)'
            view['metrics']['Fixed-prior control NRMSE']=view['metrics'].pop('Static-control NRMSE')
        payload=serializable(dict(derivation=derived,view=view))
    elif isinstance(execution,MeasuredFlowPlan):
        result=run_flow_study(execution.study);preview=result['preview_simulation']
        payload=dict(flow_study=result,view=present('pulsatile_flow',preview) if preview is not None else None)
    elif isinstance(execution,MeasuredPlan): payload=_lab_response(create_study_record(execution.study))
    elif isinstance(execution,SearchPlan): payload=search_research(SearchRequest.model_validate(execution.model_dump(exclude={'type'})))
    else: payload=execute(RunRequest.model_validate(execution.model_dump(exclude={'type'})),api_source)
    if _checked_sources()!=sources or checked_source_hash()!=api_source or runtime_manifest()!=runtime:
        raise ValueError('source/runtime changed during scientific execution')
    payload_json=_dump(payload);summary=_summary(request,payload,api_source)
    if plan.expected_execution_hash and plan.expected_execution_hash!=summary['execution_hash']:
        raise ValueError('computed execution differs from the expected run/search/study hash; nothing saved')
    body=dict(schema_version=SCHEMA,request_json=request_json,request_sha256=_sha(request_json),
        payload_json=payload_json,payload_sha256=_sha(payload_json),sources=sources,
        api_source_hash=api_source,runtime=runtime,summary=summary,
        stages=_stages(request,_sha(request_json),_sha(payload_json),summary,dict(sources=sources,api_source_hash=api_source,runtime=runtime)))
    record={**body,'record_sha256':fingerprint(body)}
    if len(_dump(record).encode())>MAX_BYTES: raise ValueError('scientific record exceeds 128 MiB storage limit')
    return record


def verify_scientific_record(record):
    expected={'schema_version','request_json','request_sha256','payload_json','payload_sha256',
        'sources','api_source_hash','runtime','summary','stages','record_sha256'}
    try:
        if not isinstance(record,dict) or set(record)!=expected or record['schema_version']!=SCHEMA:
            raise ValueError('unsupported scientific record envelope')
        body={k:v for k,v in record.items() if k!='record_sha256'}
        if fingerprint(body)!=record['record_sha256']: raise ValueError('scientific record integrity hash mismatch')
        for key in ['request','payload']:
            if not isinstance(record[key+'_json'],str) or _sha(record[key+'_json'])!=record[key+'_sha256']:
                raise ValueError('lossless '+key+' hash mismatch')
        sources=record['sources']
        if set(sources)!={'files','sha256'} or fingerprint(sources['files'])!=sources['sha256']:
            raise ValueError('source manifest integrity mismatch')
        if not HASH.fullmatch(record['api_source_hash']): raise ValueError('invalid API source fingerprint')
        request=_loads(record['request_json']);payload=_loads(record['payload_json'])
        StudyContext.model_validate(request['context'])
        mode=request['execution']['type']
        runs=([payload] if mode in {'run','operation_sequence','waveform_bloch'} else [payload['run']] if mode in {'edited_tse','edited_operations'} else
              [p['run'] for p in payload['candidates'] if p['feasible']] if mode=='search' else [])
        for run in runs:
            pair=run.get('result',{}).get('linked_readout')
            if pair and (pair['provenance']['source_sha256']!=record['sources']['sha256'] or pair['provenance']['runtime']!=record['runtime']):
                raise ValueError('linked source/runtime pin differs from scientific record')
        summary=_summary(request,payload,record['api_source_hash'])
        if fingerprint(summary)!=fingerprint(record['summary']): raise ValueError('record summary differs from computed payload')
        if request.get('expected_execution_hash') and request['expected_execution_hash']!=summary['execution_hash']:
            raise ValueError('expected execution hash differs')
        if _stages(request,record['request_sha256'],record['payload_sha256'],summary,{k:record[k] for k in ['sources','api_source_hash','runtime']})!=record['stages']:
            raise ValueError('stage dependency hash mismatch')
    except (KeyError,TypeError,AttributeError) as exc:
        raise ValueError('malformed scientific record') from exc
    return dict(integrity_passed=True,computational_replay_performed=False,
        record_sha256=record['record_sha256'],scope='integrity only; no authenticity, physical or clinical certification')


def replay_scientific_record(record):
    verify_scientific_record(record)
    if _checked_sources()!=record['sources'] or checked_source_hash()!=record['api_source_hash']:
        raise ValueError('replay source/dependency manifest differs; use the recorded source anchor')
    if runtime_manifest()!=record['runtime']: raise ValueError('replay runtime differs; use the recorded environment')
    replay=create_scientific_record(_loads(record['request_json']))
    if replay['record_sha256']!=record['record_sha256']:
        raise ValueError('full scientific computational replay differs')
    return dict(integrity_passed=True,computational_replay_performed=True,
        record_sha256=record['record_sha256'],payload_sha256=record['payload_sha256'],
        stages=replay['stages'],summary=replay['summary'],scope=SCOPE)


def default_store_path():
    configured=os.getenv('MRQLAB_RECORDS_PATH')
    return Path(configured) if configured else Path(__file__).resolve().parents[3]/'.mrqlab/scientific-records.sqlite3'


class ScientificStore:
    """One SQLite transaction per immutable record; no delete/update interface."""
    def __init__(self,path=None): self.path=Path(path) if path is not None else default_store_path()

    def _connect(self):
        self.path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if self.path.is_symlink(): raise ValueError('record database must not be a symbolic link')
        conn=sqlite3.connect(self.path,timeout=15)
        conn.execute('CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, study_id TEXT NOT NULL, created_ns INTEGER NOT NULL, record_json TEXT NOT NULL, summary_json TEXT NOT NULL, bytes INTEGER NOT NULL)')
        return conn

    def save(self,record):
        verify_scientific_record(record);raw=_dump(record);size=len(raw.encode())
        if size>MAX_BYTES: raise ValueError('scientific record exceeds 128 MiB storage limit')
        identity=record['record_sha256']
        if record['summary']['mode'] in {'edited_tse','edited_operations'}:
            parent,_=_edit_parent(_loads(record['request_json'])['execution'])
            self.save(parent)
        if record['summary']['mode']=='calibrated_radial_tse':
            parent,_=_parent_measurement(_loads(record['request_json'])['execution'])
            self.save(parent)
        if record['summary']['mode']=='agentic_inference':
            parent,_=_edit_parent(_loads(record['request_json'])['execution'])
            self.save(parent)
        with closing(self._connect()) as conn,conn:
            conn.execute('INSERT OR IGNORE INTO records VALUES (?,?,?,?,?,?)',
                (identity,record['summary']['study_id'],time.time_ns(),raw,_dump({k:v for k,v in record['summary'].items() if k!='candidates'}),size))
            stored=conn.execute('SELECT record_json FROM records WHERE id=?',(identity,)).fetchone()[0]
            existing=_loads(stored);verify_scientific_record(existing)
            if fingerprint(existing)!=fingerprint(record):
                raise ValueError('stored identity conflict or corruption; record was not overwritten')
        return identity

    def get(self,identity):
        if not HASH.fullmatch(identity): raise ValueError('64 lowercase hex record id required')
        with closing(self._connect()) as conn:
            row=conn.execute('SELECT record_json FROM records WHERE id=?',(identity,)).fetchone()
        if row is None: raise FileNotFoundError(identity)
        record=_loads(row[0]);verify_scientific_record(record)
        if record['record_sha256']!=identity: raise ValueError('stored record identity differs')
        return record

    def list(self,study_id=None,limit=50,offset=0):
        if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or offset<0:
            raise ValueError('bounded record listing required')
        with closing(self._connect()) as conn:
            where=' WHERE study_id=?' if study_id is not None else ''
            args=[study_id] if study_id is not None else []
            total=conn.execute('SELECT count(*) FROM records'+where,args).fetchone()[0]
            rows=conn.execute('SELECT id,created_ns,summary_json,bytes FROM records'+where+' ORDER BY created_ns DESC,id LIMIT ? OFFSET ?',args+[limit,offset]).fetchall()
        return dict(total=total,offset=offset,limit=limit,records=[dict(record_sha256=i,created_ns=t,
            summary=_loads(s),bytes=n,integrity_checked=False,computational_replay_performed=False) for i,t,s,n in rows])


def _response(record):
    payload=_loads(record['payload_json']);mode=record['summary']['mode']
    if mode in {'measured_tse','measured_flow','calibrated_radial_tse','agentic_inference','operation_sequence','waveform_bloch'}: view=payload['view']
    elif mode in {'edited_tse','edited_operations'}: view=payload['run']['view']
    elif mode=='run': view=payload['view']
    else:
        selected=payload['best'] or next((p for p in payload['candidates'] if p['feasible']),None)
        view=selected['run']['view'] if selected else None
    return dict(record=record,verification=verify_scientific_record(record),view=view)


def _api(action,conflict=False):
    try: return action()
    except FileNotFoundError as exc: raise HTTPException(404,'scientific record not found') from exc
    except (ValueError,sqlite3.DatabaseError,OSError) as exc: raise HTTPException(409 if conflict else 422,str(exc)) from exc


@router.post('')
def create_record(plan: ScientificPlan):
    def action():
        record=create_scientific_record(plan);ScientificStore().save(record);return _response(record)
    return _api(action)


@router.get('')
def list_records(study_id: str | None=Query(default=None,max_length=128),limit: int=Query(default=50,ge=1,le=100),offset: int=Query(default=0,ge=0)):
    return _api(lambda:ScientificStore().list(study_id,limit,offset))


@router.post('/import')
def import_record(record: dict):
    def action():
        ScientificStore().save(record);return _response(record)
    return _api(action)


@router.get('/{identity}')
def get_record(identity: str): return _api(lambda:_response(ScientificStore().get(identity)),True)


@router.post('/{identity}/replay')
def replay_record(identity: str): return _api(lambda:replay_scientific_record(ScientificStore().get(identity)),True)


@router.get('/{identity}/export')
def export_record(identity: str):
    def action():
        record=ScientificStore().get(identity)
        return Response(_dump(record),media_type='application/json',headers={'Content-Disposition':f'attachment; filename="mrqlab-record-{identity[:12]}.json"'})
    return _api(action,True)


def read_portable(path):
    with Path(path).open('rb') as stream: raw=stream.read(MAX_BYTES+1)
    if len(raw)>MAX_BYTES: raise ValueError('scientific record/input exceeds 128 MiB')
    return _loads(raw)


def write_portable(record,path):
    verify_scientific_record(record);path=Path(path);temporary=None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.mrqlab-record-',delete=False) as stream:
            temporary=Path(stream.name);stream.write(_dump(record).encode()+b'\n');stream.flush();os.fsync(stream.fileno())
        os.link(temporary,path)
    finally:
        if temporary is not None: temporary.unlink(missing_ok=True)


def main(argv=None):
    parser=argparse.ArgumentParser(description='Local scientific execution records; teaching/research only')
    parser.add_argument('--store',type=Path)
    commands=parser.add_subparsers(dest='action',required=True)
    for name in ['run','verify','replay','export']:
        command=commands.add_parser(name);command.add_argument('input')
        if name!='verify': command.add_argument('--output',type=Path,required=True)
    importer=commands.add_parser('import');importer.add_argument('input')
    commands.add_parser('list')
    args=parser.parse_args(argv)
    try:
        store=ScientificStore(args.store)
        if args.action=='list': print(_dump(store.list()));return 0
        if args.action=='verify': print(_dump(verify_scientific_record(read_portable(args.input))));return 0
        if args.action=='import':
            record=read_portable(args.input);store.save(record);print(_dump(verify_scientific_record(record)));return 0
        if args.output.exists(): raise ValueError('output already exists; no overwrite')
        if args.action=='export': record=store.get(args.input)
        elif args.action=='run': record=create_scientific_record(read_portable(args.input),store=store)
        else:
            record=read_portable(args.input);replay_scientific_record(record)
        store.save(record);write_portable(record,args.output)
        print(_dump(dict(record_sha256=record['record_sha256'],summary=record['summary'],computational_replay_performed=args.action=='replay')))
        return 0
    except (ValueError,OSError,sqlite3.DatabaseError,HTTPException) as exc:
        parser.exit(1,str(exc)+'\n')


if __name__=='__main__': raise SystemExit(main())
