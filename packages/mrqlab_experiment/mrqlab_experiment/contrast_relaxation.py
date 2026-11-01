"""Explicit static dilute-agent R1/R2 binding, conditional on supplied relaxivity.

No agent catalog, dose conversion, pharmacokinetics, susceptibility/T2*, changes
to diffusion/exchange, or inference/authentication of measured coefficients.
"""
import math
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator


class ContrastExposure(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True,allow_inf_nan=False,frozen=True)
    model: Literal['static_linear_R1_R2']='static_linear_R1_R2'
    concentration_mmol_l: float=Field(ge=0,le=100.)
    concentration_unit: Literal['mmol/L']='mmol/L'
    r1_l_mmol_s: float=Field(ge=0,le=1000.)
    r2_l_mmol_s: float=Field(ge=0,le=1000.)
    relaxivity_unit: Literal['L/(mmol*s)']='L/(mmol*s)'
    reference_b0_t: float=Field(gt=0,le=14.)
    reference_temperature_k: float=Field(ge=260.,le=330.)
    medium: str=Field(min_length=1,max_length=512)
    valid_concentration_max_mmol_l: float=Field(gt=0,le=100.)
    source_ref: str=Field(min_length=1,max_length=1024)
    origin: Literal['authored','synthetic','measured']

    @model_validator(mode='after')
    def declared_domain(self):
        if self.r1_l_mmol_s+self.r2_l_mmol_s<=0: raise ValueError('at least one nonzero declared relaxivity required')
        if self.concentration_mmol_l>self.valid_concentration_max_mmol_l: raise ValueError('concentration exceeds supplied relaxivity validity range; no extrapolation')
        if not self.source_ref.strip() or not self.medium.strip(): raise ValueError('nonblank relaxivity source and medium required')
        return self


def tissue_relaxation(tissue,field_t):
    """Return effective times and binding without modifying authored tissue."""
    exposure=tissue.contrast_exposure
    if exposure is None: return tissue.t1,tissue.t2,None
    # Revalidate model_copy/update or mutable parent inputs at execution time.
    e=ContrastExposure.model_validate(exposure.model_dump(mode='json'))
    if not math.isfinite(field_t) or abs(e.reference_b0_t-field_t)>1e-9:
        raise ValueError('relaxivity reference B0 differs from effective scanner field; no field interpolation')
    if tissue.bound_pool or abs(tissue.chemical_shift_ppm)>1e-12:
        raise ValueError('contrast relaxivity binding supports liquid water tissues, not semisolid/shifted solute pools')
    if tissue.t2_star is not None: raise ValueError('contrast T2* / susceptibility binding is unsupported')
    if not all(math.isfinite(v) and v>0 for v in [tissue.t1,tissue.t2]): raise ValueError('finite positive baseline T1/T2 required')
    base_r1=1./tissue.t1;base_r2=1./tissue.t2
    r1=base_r1+e.r1_l_mmol_s*e.concentration_mmol_l
    r2=base_r2+e.r2_l_mmol_s*e.concentration_mmol_l
    if base_r2<base_r1/2-1e-12 or r2<r1/2-1e-12:
        raise ValueError('declared baseline/effective relaxation violates R2 >= R1/2 for this spin-1/2 model')
    binding=dict(tissue_id=tissue.id,exposure=e.model_dump(mode='json'),
        baseline_t1_s=tissue.t1,baseline_t2_s=tissue.t2,baseline_r1_s_inv=base_r1,baseline_r2_s_inv=base_r2,
        effective_r1_s_inv=r1,effective_r2_s_inv=r2,effective_t1_s=1./r1,effective_t2_s=1./r2,
        unchanged='PD, geometry, diffusion ADC, exchange rates and chemical shifts remain authored; no concentration-time or susceptibility model',
        assumptions='uniform static per-tissue concentration; supplied dilute linear relaxivity at the declared field/temperature/medium; origin is user-declared')
    return 1./r1,1./r2,binding


def contrast_bindings(graph):
    if graph.physiology is not None and graph.physiology.contrast_agent_concentration!=0:
        raise ValueError('legacy physiology.contrast_agent_concentration has no units/relaxivity binding; use explicit tissue.contrast_exposure')
    tissues=graph.tissue if isinstance(graph.tissue,tuple) else (() if graph.tissue is None else (graph.tissue,))
    if any(t.contrast_exposure is not None for t in tissues) and len({t.id for t in tissues})!=len(tissues):
        raise ValueError('contrast binding requires unique tissue ids')
    return [b for t in tissues if (b:=tissue_relaxation(t,graph.effective_scanner.b0_t)[2]) is not None]


def effective_tissue(tissue,field_t):
    t1,t2,_=tissue_relaxation(tissue,field_t)
    return tissue.model_copy(update=dict(t1=t1,t2=t2))
