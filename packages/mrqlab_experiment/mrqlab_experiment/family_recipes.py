"""Research clinical questions linked to executable extensions, not replacements."""
import numpy as np
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T
from .models import (ExperimentGraph, ExperimentNode, TemplateRef, TissueModel, EngineRef,
                     ReadoutSpec, ScannerModel, SampleSpec)
from .clinical import ClinicalProtocolRecipe, ClinicalQuestion, TissuePriorSet, TissuePrior, ObjectiveVector
from .clinical_catalog import RESEARCH_3T

OBJECTIVES={
 'TSE3D':'maximize absolute target/reference mean echo contrast at matched PD and T2',
 'SSFP':'maximize wall mean magnitude minus blood mean magnitude in the transient readout',
 'EPSE':'maximize restricted minus normal diffusion signal at matched TE; ADC from b=0 and candidate b',
 'CEST':'maximize water Z difference versus the same pools with all exchange disabled at 3.5 ppm',
 'PRESS':'minimize summed relative water-referenced peak-area bias against declared teaching metabolite amounts',
}

FAMILY_RECIPES=('brain_t1_3d_tse','vessel_wall_ssfp_darkblood','brain_epse_dwi','cest_multi_pool_z_spectrum','brain_press_mrs')


def build_family_recipe(name):
    if name not in FAMILY_RECIPES:
        raise ValueError(f'unknown family recipe {name!r}')
    params={}; sample=SampleSpec(); products=('signal',); metadata={}
    if name=='brain_t1_3d_tse':
        template='TSE3D'; engine='epg'
        params=dict(te=.008,tr=.4,echoes=4,partitions=4,refocusing_flip_angle=140.,refocusing_end_angle=110.)
        tissues=(TissueModel(id='white_matter',t1=.85,t2=.08,proton_density=.8),TissueModel(id='gray_matter',role='reference',t1=1.4,t2=.08,proton_density=.8))
        question='Separate equal-PD, equal-T2 white and gray matter through short-TR T1 recovery in a partition-encoded TSE train'
        mechanism='spoiled repeated short-TR TSE with explicit kz encoding and linear refocusing ramp'
    elif name=='vessel_wall_ssfp_darkblood':
        template='SSFP'; engine='bloch'
        params=dict(tr=.005,te=.0025,flip_angle=40.,repetitions=8,double_inversion=1,inversion_time_s=.9,inflow_fraction=1.)
        tissues=(TissueModel(id='wall',t1=1.,t2=.08),TissueModel(id='blood',role='reference',t1=1.6,t2=.18))
        question='Retain static vessel wall while minimizing incoming blood during a short balanced-SSFP readout after double inversion'
        mechanism='nonselective inversion plus local reinversion; known incoming fraction at readout; finite transient train'
    elif name=='brain_epse_dwi':
        template='EPSE'; engine='epg'
        params=dict(te=.09,tr=1.,diffusion_gradient_mt_m=30.,delta_s=.02,separation_s=.045,epi_lines=16)
        tissues=(TissueModel(id='restricted',t1=1.,t2=.1,diffusion_adc_mm2_s=.0006),TissueModel(id='normal',role='reference',t1=1.,t2=.1,diffusion_adc_mm2_s=.001))
        question='Separate restricted from normal Gaussian diffusion at matched TE and recover ADC from a b series'
        mechanism='rectangular PGSE spin echo followed by alternating EPI traversal'
    elif name=='cest_multi_pool_z_spectrum':
        from .presets import build_clinical_recipe
        graph=build_clinical_recipe('cest_amide_z_spectrum')
        tissues=(TissueModel(id='water',t1=1.,t2=.08,proton_density=.96,pool_fraction=.96),
                 TissueModel(id='amide',t1=1.,t2=.015,proton_density=.025,pool_fraction=.025,chemical_shift_ppm=3.5),
                 TissueModel(id='amine',t1=1.,t2=.012,proton_density=.015,pool_fraction=.015,chemical_shift_ppm=2.))
        rates=np.zeros((3,3))
        for j,k in ((1,30.),(2,100.)):
            rates[j,0]=k; rates[0,j]=k*tissues[j].proton_density/tissues[0].proton_density
        graph.sequence.metadata['cest'].update(exchange_matrix_hz=rates.tolist(),offsets_ppm=[-5,-3.5,-2,0,2,3.5,5])
        graph.tissue=tissues
        question='Resolve exchange-sensitive water saturation from simultaneous amide and amine pools'
        mechanism='N-liquid-pool Bloch-McConnell with explicit detailed-balance exchange matrix'
        template=None; engine='epg-x'
    else:
        template='PRESS'; engine='spectral'
        params=dict(te=.03,tr=1.,readout_s=.512,voxel_size_m=.02)
        tissues=()
        # Relative frequencies use water as 0 ppm (metabolites upfield).
        pools=[dict(name=n,fraction=f,chemical_shift_ppm=ppm,t1=1.,t2=.15) for n,f,ppm in
               (('NAA',.02,-2.69),('Cr',.015,-1.67),('Cho',.01,-1.49))]
        sample=SampleSpec(pools=tuple(pools),isochromats=(dict(position_m=(0.,0.,0.),weight=1.),dict(position_m=(.03,0.,0.),weight=1.)))
        question='Measure relative NAA, Cr and Cho singlet areas in an ideal PRESS voxel against a matched unsuppressed water reference'
        mechanism='orthogonal ideal slab PRESS localization; independent Lorentzian singlets; peak integration'
    if template:
        graph=ExperimentGraph(id=f'recipe:{name}',name=name,intent='clinical_contrast',
            nodes=(ExperimentNode(id='design',kind='RF',label=mechanism),),edges=(),
            sequence=TemplateRef(template=template,params=params),sample=sample,tissue=tissues or None,
            engine=EngineRef(preferred=engine,options={'dwell_time':.0001 if template=='SSFP' else .001,'epg_kmax':8}),
            readout=ReadoutSpec(products=products),scanner_model=ScannerModel(b0_t=3.))
    graph.id=f'recipe:{name}'; graph.name=name
    graph.clinical_recipe=ClinicalProtocolRecipe(id=name,version='1.0.0',vertical=name,
        question=ClinicalQuestion(anatomy='brain' if name!='vessel_wall_ssfp_darkblood' else 'vessel wall',
            research_question=question,target_finding='research contrast or relative peak area',contrast_mechanism=mechanism),
        tissue_priors=TissuePriorSet(id=name+'-priors',version='1.0.0',tissues=tuple(TissuePrior.model_validate(t.model_dump()) for t in tissues)),
        objective=ObjectiveVector(terms=()),measurement_objective=OBJECTIVES[template or "CEST"],robustness=(),constraints=(),scanner_profile=RESEARCH_3T,experiment_recipe_id=name)
    return graph
