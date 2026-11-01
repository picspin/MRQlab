"""Declared ideal TSE adapter for the common linked image/vector core."""
import numpy as np
from .linked_readout import _hash, complex_values as _values, create_linked_readout


def pair_tse_readout(kspace,image,timeline,labels,tissues,design):
    shape=list(np.shape(image));axes=['z','y','x'][-len(shape):];indices=[];times=[];echoes=[]
    for train in timeline:
        for line in train['lines']:
            for x in range(shape[-1]):
                indices.append([line['kz'],line['ky'],x][-len(shape):]);times.append(line['adc_start_s']+x*line['dwell_s']);echoes.append(line['echo'])
    indices=np.asarray(indices,int);samples=kspace[tuple(indices.T)]
    signal=dict(id='acquired_kspace',axis='acquisition_sample',value_unit='a.u.',complex_convention='real + i*imag',values=_values(samples),
        grid_indices=indices.tolist(),grid_index_axes=axes,
        normalized_coordinates=((indices-np.asarray(shape)//2)/np.asarray(shape)).tolist(),coordinate_unit='cycles/voxel',
        sample_times_s=times,time_unit='s',extensions=dict(echo_numbers=echoes),
        timing_model='ideal authored ADC schedule; one periodic EPG echo-center amplitude is held across the entire line')
    mr_image=dict(id='reconstructed_image',shape=shape,axes=axes,index_unit='voxel',flatten_order='C',value_unit='a.u.',values=_values(image),
        display='magnitude for human preview; complex values retained without gain normalization')
    structure=dict(shape=shape,label_grid=np.asarray(labels,int).tolist(),label_to_tissue_id=[t.id for t in tissues],
        origin='authored two-class synthetic spatial structure; no patient/anatomical validation')
    controls=[dict(field=name,unit=unit,value=value) for name,unit,value in [
        ('rf.refocusing_start_deg','deg',timeline[0]['refocusing_degrees'][0]),
        ('rf.refocusing_end_deg','deg',timeline[0]['refocusing_degrees'][-1]),
        ('timing.tr_s','s',design['tr_s']),('timing.echo_spacing_s','s',design['echo_spacing_s']),('encoding.order','category',design['order'])]]
    if len(timeline[0]['refocusing_degrees'])==1: controls=[c for c in controls if c['field']!='rf.refocusing_end_deg']
    for tissue in tissues:
        e=tissue.contrast_exposure
        if e is not None: controls.append(dict(field='tissue.concentration_mmol_l',tissue_id=tissue.id,value=e.concentration_mmol_l,unit='mmol/L',min=0.,max=e.valid_concentration_max_mmol_l))
    result=dict(image=mr_image,signal_vector=signal,structure=structure,controls=controls,
        links=[dict(source='acquired_kspace',target='reconstructed_image',transform='centered_inverse_dft',normalization='1/product(shape); no fitted gain'),
               dict(source='structure',target='acquired_kspace',transform='tissue-specific periodic EPG and ideal Fourier line encoding')],
        scope='linked teaching/research ideal TSE images and signal vectors, not DICOM, diagnosis, scanner control or a universal multimodal representation')
    from .study_records import _checked_sources, runtime_manifest
    result['provenance']=dict(adapter='ideal-cartesian-tse-1',source_sha256=_checked_sources()['sha256'],runtime=runtime_manifest(),
        inputs_sha256=_hash(design),origin=structure['origin'],source_refs=[dict(tissue_id=t.id,source_ref=t.contrast_exposure.source_ref if t.contrast_exposure else 'authored:tissue:'+t.id,origin=t.contrast_exposure.origin if t.contrast_exposure else 'authored',state=t.model_dump(mode='json')) for t in tissues])
    for c in controls:
        if c['field']=='encoding.order': c.update(kind='category',choices=['linear','centric'])
        else:
            bounds={'rf.refocusing_start_deg':(1.,180.),'rf.refocusing_end_deg':(1.,180.),'timing.tr_s':(.05,2.),'timing.echo_spacing_s':(.006,.03)}
            low,high=bounds.get(c['field'],(c.get('min',0.),c.get('max',1.)))
            c.update(kind='number',min=low,max=high)
    return create_linked_readout(**result)

