"""Finite, budgeted RF-scale design search over sampled-waveform studies."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .waveform_bloch import WaveformBlochPlan, estimate_waveform_work, run_waveform_bloch


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class FieldScenario(Strict):
    id: str = Field(min_length=1, max_length=64, pattern=r'^[A-Za-z][A-Za-z0-9_]*$')
    b0_delta_hz: float = Field(ge=-1000, le=1000)
    b1_scale_factor: float = Field(ge=0, le=2)


class WaveformSearch(Strict):
    base: WaveformBlochPlan
    rf_block_id: str = Field(min_length=1, max_length=128)
    scales: list[float] = Field(min_length=1, max_length=8)
    scenarios: list[FieldScenario] = Field(min_length=1, max_length=4)
    refinement_tolerance: float = Field(ge=0, le=2)
    refinement_unit: Literal['a.u.'] = 'a.u.'
    max_total_work: int = Field(default=2_000_000, ge=1, le=2_000_000, strict=True)

    @model_validator(mode='after')
    def valid_grid(self):
        if self.base.target is None:
            raise ValueError('an explicit ADC point-signal target is required for waveform optimization')
        if self.base.substeps_per_interval > 4:
            raise ValueError('base substeps_per_interval must allow a doubled refinement')
        if any(not 0 <= v <= 2 for v in self.scales) or len(set(self.scales)) != len(self.scales):
            raise ValueError('distinct RF scales in [0, 2] required')
        if len({s.id for s in self.scenarios}) != len(self.scenarios):
            raise ValueError('unique scenario IDs required')
        if not any(s.b0_delta_hz == 0 and s.b1_scale_factor == 1 for s in self.scenarios):
            raise ValueError('scenarios must include the nominal B0/B1 case')
        if not any(b.id == self.rf_block_id and b.rf is not None for b in self.base.sequence.blocks):
            raise ValueError('rf_block_id must name one existing RF block')
        return self


def _candidate_parameters(search, scale, scenario, refined):
    parameters = search.base.model_dump(mode='json')
    block = next(b for b in parameters['sequence']['blocks'] if b['id'] == search.rf_block_id)
    block['rf']['samples_ut'] = [float(value * scale) for value in block['rf']['samples_ut']]
    for tissue in parameters['tissues']:
        tissue['b0_hz'] += scenario.b0_delta_hz
        tissue['b1_scale'] *= scenario.b1_scale_factor
    if refined:
        parameters['substeps_per_interval'] *= 2
    return parameters


def search_waveform_bloch(request):
    search = WaveformSearch.model_validate(request)
    replay = search.model_dump(mode='json')
    # Preflight the complete grid before any spin evolution. Invalid candidate
    # settings stay visible and consume no integration work.
    prepared = []
    total_work = 0
    for index, scale in enumerate(search.scales):
        entry = dict(index=index, scale=scale, scenarios=[])
        try:
            for scenario in search.scenarios:
                coarse = _candidate_parameters(search, scale, scenario, False)
                fine = _candidate_parameters(search, scale, scenario, True)
                estimates = [estimate_waveform_work(coarse), estimate_waveform_work(fine)]
                entry['scenarios'].append((scenario.id, coarse, fine, estimates))
            entry['estimated_work'] = sum(e['voxel_steps'] for s in entry['scenarios'] for e in s[3])
            total_work += entry['estimated_work']
        except ValueError as exc:
            entry['error'] = str(exc)
            entry['scenarios'] = []
            entry['estimated_work'] = 0
        prepared.append(entry)
    if total_work > search.max_total_work:
        raise ValueError(f'complete search work {total_work} exceeds max_total_work {search.max_total_work}; no candidates were integrated')

    results = []
    for entry in prepared:
        item = dict(index=entry['index'], scale=entry['scale'], executable='error' not in entry,
                    estimated_work=entry['estimated_work'], eligible=False, scenarios=[])
        if 'error' in entry:
            item['reasons'] = [entry['error']]
            results.append(item)
            continue
        block = next(b for b in search.base.sequence.blocks if b.id == search.rf_block_id)
        item['rf_energy_proxy_ut2_s'] = float(sum((v*entry['scale'])**2 for v in block.rf.samples_ut)*block.rf.raster_s)
        item['reasons'] = []
        for scenario_id, coarse, fine, estimates in entry['scenarios']:
            coarse_run = run_waveform_bloch(coarse); fine_run = run_waveform_bloch(fine)
            if [coarse_run['work']['voxel_steps'], fine_run['work']['voxel_steps']] != [e['voxel_steps'] for e in estimates]:
                raise ValueError('waveform work changed after search preflight')
            if fine_run['work']['voxel_steps'] != 2*coarse_run['work']['voxel_steps']:
                raise ValueError('refined run did not halve every integration substep')
            differences = [abs(complex(a['real']-b['real'], a['imag']-b['imag']))
                           for a,b in zip(coarse_run['samples'],fine_run['samples'])]
            max_error = max(differences)
            converged = max_error <= search.refinement_tolerance
            target_passed = coarse_run['validation']['passed'] and fine_run['validation']['passed']
            if not converged: item['reasons'].append(f'{scenario_id}: refinement tolerance failed')
            if not target_passed: item['reasons'].append(f'{scenario_id}: signal target failed')
            item['scenarios'].append(dict(id=scenario_id, coarse=coarse_run, refined=fine_run,
                max_sample_difference=float(max_error), refinement_passed=bool(converged), target_passed=bool(target_passed)))
        item['eligible'] = not item['reasons']
        results.append(item)
    eligible = [item for item in results if item['eligible']]
    best = min(eligible, key=lambda item: (item['rf_energy_proxy_ut2_s'], item['index'])) if eligible else None
    return dict(model='waveform_rf_scale_grid_v1', candidates=results,
        selected_index=best['index'] if best is not None else None,
        validation=dict(passed=best is not None, scope='finite authored B0/B1 scenarios and ADC point target; no clinical optimum'),
        work=dict(total_voxel_steps=total_work, max_total_work=search.max_total_work,
                  policy='complete grid preflight before any integration; no silent coarsening'),
        objective='minimum edited RF block energy proxy among target- and refinement-passing candidates; not SAR',
        provenance=dict(replay=replay, scope='finite grid, synthetic static plane, point ADC; teaching/research only'))
