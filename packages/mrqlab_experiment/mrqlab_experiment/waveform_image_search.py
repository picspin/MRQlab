"""Finite RF grid search against sequential Cartesian image targets."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .waveform_bloch import estimate_waveform_work
from .waveform_cartesian import CartesianWaveformPlan, preflight_cartesian_trajectory, run_waveform_cartesian
from .waveform_search import FieldScenario


class _Strict(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)


class WaveformImageSearch(_Strict):
    base: CartesianWaveformPlan
    rf_block_id: str=Field(min_length=1,max_length=128)
    scales: list[float]=Field(min_length=1,max_length=8)
    scenarios: list[FieldScenario]=Field(min_length=1,max_length=4)
    signal_refinement_tolerance: float=Field(ge=0,le=2)
    image_refinement_tolerance: float=Field(ge=0,le=2)
    refinement_unit: Literal['a.u.']='a.u.'
    max_total_work: int=Field(default=2_000_000,ge=1,le=2_000_000,strict=True)

    @model_validator(mode='after')
    def valid_grid(self):
        if self.base.image_target is None: raise ValueError('an explicit image target is required')
        if self.base.waveform.substeps_per_interval>4: raise ValueError('base substeps must allow doubled refinement')
        if any(not 0<=x<=2 for x in self.scales) or len(set(self.scales))!=len(self.scales):
            raise ValueError('distinct RF scales in [0, 2] required')
        if len({s.id for s in self.scenarios})!=len(self.scenarios): raise ValueError('unique scenario IDs required')
        if not any(s.b0_delta_hz==0 and s.b1_scale_factor==1 for s in self.scenarios):
            raise ValueError('scenarios must include the nominal B0/B1 case')
        rf=[b for b in self.base.waveform.sequence.blocks if b.rf is not None]
        if len(rf)!=1 or rf[0].id!=self.rf_block_id:
            raise ValueError('rf_block_id must identify the only RF block')
        return self


def candidate_parameters(search,scale,scenario,refined):
    parameters=search.base.model_dump(mode='json');waveform=parameters['waveform']
    block=next(b for b in waveform['sequence']['blocks'] if b['id']==search.rf_block_id)
    block['rf']['samples_ut']=[float(v*scale) for v in block['rf']['samples_ut']]
    for tissue in waveform['tissues']:
        tissue['b0_hz']+=scenario.b0_delta_hz;tissue['b1_scale']*=scenario.b1_scale_factor
    if refined: waveform['substeps_per_interval']*=2
    return parameters


def search_waveform_image(request):
    search=WaveformImageSearch.model_validate(request)
    # Trajectory and sequence timing are invariant across the allowed edits.
    preflight_cartesian_trajectory(search.base)
    prepared=[];total=0
    for index,scale in enumerate(search.scales):
        entry=dict(index=index,scale=scale,scenarios=[])
        try:
            for scenario in search.scenarios:
                coarse=candidate_parameters(search,scale,scenario,False)
                fine=candidate_parameters(search,scale,scenario,True)
                rf=next(b['rf'] for b in coarse['waveform']['sequence']['blocks'] if b['id']==search.rf_block_id)
                if not any(rf['samples_ut']): raise ValueError('Cartesian adapter requires exactly one nonzero RF block')
                estimates=[estimate_waveform_work(coarse['waveform']),estimate_waveform_work(fine['waveform'])]
                entry['scenarios'].append((scenario.id,coarse,fine,estimates))
            entry['estimated_work']=sum(e['voxel_steps'] for s in entry['scenarios'] for e in s[3])
            total+=entry['estimated_work']
        except ValueError as exc:
            entry.update(error=str(exc),scenarios=[],estimated_work=0)
        prepared.append(entry)
    if total>search.max_total_work:
        raise ValueError(f'complete image search work {total} exceeds max_total_work {search.max_total_work}; no candidates were integrated')
    results=[]
    for entry in prepared:
        item=dict(index=entry['index'],scale=entry['scale'],executable='error' not in entry,
                  estimated_work=entry['estimated_work'],eligible=False,scenarios=[])
        if 'error' in entry:
            item['reasons']=[entry['error']];results.append(item);continue
        block=next(b for b in search.base.waveform.sequence.blocks if b.id==search.rf_block_id)
        item['rf_energy_proxy_ut2_s']=float(sum((v*entry['scale'])**2 for v in block.rf.samples_ut)*block.rf.raster_s)
        item['reasons']=[]
        for scenario_id,coarse,fine,estimates in entry['scenarios']:
            a=run_waveform_cartesian(coarse);b=run_waveform_cartesian(fine)
            works=[a['waveform']['work']['voxel_steps'],b['waveform']['work']['voxel_steps']]
            if works!=[e['voxel_steps'] for e in estimates] or works[1]!=2*works[0]:
                raise ValueError('image search work or doubled substeps differ from preflight')
            samples_a=a['waveform']['samples'];samples_b=b['waveform']['samples']
            signal_error=max(abs(complex(x['real']-y['real'],x['imag']-y['imag'])) for x,y in zip(samples_a,samples_b))
            image_error=max(abs(complex(ar-br,ai-bi)) for ar,ai,br,bi in zip(a['image']['real'],a['image']['imag'],b['image']['real'],b['image']['imag']))
            refined=signal_error<=search.signal_refinement_tolerance and image_error<=search.image_refinement_tolerance
            target=a['validation']['passed'] and b['validation']['passed']
            if not refined: item['reasons'].append(f'{scenario_id}: signal or image refinement tolerance failed')
            if not target: item['reasons'].append(f'{scenario_id}: declared image or signal target failed')
            item['scenarios'].append(dict(id=scenario_id,coarse=a,refined=b,max_signal_difference=float(signal_error),
                                           max_image_difference=float(image_error),refinement_passed=bool(refined),target_passed=bool(target)))
        item['eligible']=not item['reasons'];results.append(item)
    eligible=[x for x in results if x['eligible']]
    best=min(eligible,key=lambda x:(x['rf_energy_proxy_ut2_s'],x['index'])) if eligible else None
    return dict(model='waveform_image_rf_grid_v1',candidates=results,selected_index=best['index'] if best else None,
                validation=dict(passed=best is not None,scope='finite authored scenarios and reconstructed image target; not a clinical optimum'),
                objective='minimum edited RF block energy proxy among image-, signal- and refinement-passing candidates; not SAR',
                work=dict(total_voxel_steps=total,max_total_work=search.max_total_work,
                          policy='complete trajectory and grid preflight before spin integration; no silent coarsening'),
                provenance=dict(replay=search.model_dump(mode='json'),scope='synthetic static plane and sequential point ADC; teaching/research only'))
