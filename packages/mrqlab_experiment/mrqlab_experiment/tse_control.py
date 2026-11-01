"""Bounded semantic edits shared by human and agent TSE controls."""
from copy import deepcopy
import math
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class TSEEdit(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False)
    field: Literal['rf.refocusing_start_deg','rf.refocusing_end_deg','timing.tr_s','timing.echo_spacing_s','encoding.order','tissue.concentration_mmol_l']
    value: float | str
    tissue_id: str | None=Field(default=None,min_length=1,max_length=128)

    @model_validator(mode='after')
    def typed_value(self):
        if self.field=='encoding.order':
            if self.value not in ['linear','centric']: raise ValueError('TSE order must be linear or centric')
        elif type(self.value) not in [int,float] or not math.isfinite(self.value): raise ValueError('finite numeric control value required')
        if (self.field=='tissue.concentration_mmol_l')!=(self.tissue_id is not None): raise ValueError('tissue_id applies only to concentration edits')
        return self


def apply_tse_edits(parameters,updates):
    result=deepcopy(parameters);seen=set()
    mapped={'rf.refocusing_start_deg':'refocusing_angle','rf.refocusing_end_deg':'refocusing_end_angle','timing.tr_s':'tr_s','timing.echo_spacing_s':'echo_spacing_s','encoding.order':'order'}
    for raw in updates:
        edit=TSEEdit.model_validate(raw.model_dump(mode='json') if isinstance(raw,TSEEdit) else raw)
        key=(edit.field,edit.tissue_id)
        if key in seen: raise ValueError('duplicate semantic edit')
        seen.add(key)
        if edit.field=='rf.refocusing_end_deg' and result.get('echoes',4)==1: raise ValueError('terminal-angle control is unavailable for a single-echo train')
        if edit.field in mapped: result[mapped[edit.field]]=edit.value
        else:
            tissues=result.get('experiment',{}).get('tissue',[])
            if not isinstance(tissues,list): raise ValueError('controlled TSE requires two explicitly named tissues')
            matches=[t for t in tissues if t['id']==edit.tissue_id]
            if len(matches)!=1 or not matches[0].get('contrast_exposure'): raise ValueError('concentration edit requires an existing explicit tissue exposure and relaxivity reference')
            matches[0]['contrast_exposure']['concentration_mmol_l']=edit.value
    return result


def contrast_tse_example():
    from .family_recipes import build_family_recipe
    from .contrast_relaxation import ContrastExposure
    from .clinical import TissuePrior
    graph=build_family_recipe('brain_t1_3d_tse')
    question='How do prescribed static contrast-agent concentration and refocusing design alter this synthetic TSE image and its complete complex acquisition?'
    for tissue,c in zip(graph.tissue,[0.,.2]):
        tissue.contrast_exposure=ContrastExposure(concentration_mmol_l=c,r1_l_mmol_s=4.,r2_l_mmol_s=5.,reference_b0_t=3.,reference_temperature_k=310.,
            medium='synthetic uniform water tissue surrogate',valid_concentration_max_mmol_l=1.,source_ref='synthetic:constant-relaxivity-teaching-example',origin='synthetic')
    recipe=graph.clinical_recipe
    graph.clinical_recipe=recipe.model_copy(update={'question':recipe.question.model_copy(update={'research_question':question}),
        'tissue_priors':recipe.tissue_priors.model_copy(update={'tissues':tuple(TissuePrior.model_validate(t.model_dump()) for t in graph.tissue)})})
    return dict(context=dict(study_id='synthetic-contrast-tse-1',research_question=question,
        target_rationale='Compare complete linked signal/image outputs and retain existing reference-image/PSF target reports; no clinical enhancement criterion is inferred.',
        assumptions='Authored structure, baseline T1/T2 and synthetic static relaxivity at 3 T; no dose, pharmacokinetics, within-ADC Bloch evolution or patient/scanner certification.'),
        execution=dict(type='run',kind='tse',parameters=dict(experiment=graph.model_dump(mode='json'),t2_s=[t.t2 for t in graph.tissue],refocusing_angle=140.,refocusing_end_angle=110.)))
