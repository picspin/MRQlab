"""Lossless linked MR image / acquisition-order complex signal representation.

This adapter represents the existing ideal echo-held Cartesian TSE model. Sample
times are its authored ADC schedule, not additional within-window Bloch evolution.
"""
import numpy as np
from mrqlab_recon.spatial import cartesian_reconstruct


def _hash(value):
    # Runtime import avoids the existing lab-study -> TSE module dependency.
    from .lab_study import fingerprint
    return fingerprint(value)
def _values(data):
    a=np.asarray(data,complex).ravel()
    return dict(real=a.real.tolist(),imag=a.imag.tolist())


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
        sample_times_s=times,time_unit='s',echo_numbers=echoes,
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
    result=dict(schema_version='mrqlab-image-signal-pair-1',canonicalization='typed-json-f64-v1',image=mr_image,signal_vector=signal,structure=structure,controls=controls,
        links=[dict(source='acquired_kspace',target='reconstructed_image',transform='centered inverse DFT over declared grid axes',normalization='1/product(shape); no fitted gain'),
               dict(source='structure',target='acquired_kspace',transform='tissue-specific periodic EPG and ideal Fourier line encoding')],
        scope='linked teaching/research ideal TSE images and signal vectors, not DICOM, diagnosis, scanner control or a universal multimodal representation')
    result['pair_sha256']=_hash(result)
    return result


def verify_linked_readout(pair):
    if not isinstance(pair,dict) or pair.get('schema_version')!='mrqlab-image-signal-pair-1': raise ValueError('unsupported image/signal pair')
    if _hash({k:v for k,v in pair.items() if k!='pair_sha256'})!=pair.get('pair_sha256'): raise ValueError('image/signal pair hash mismatch')
    image=pair['image'];signal=pair['signal_vector'];shape=image['shape']
    if len(shape) not in [2,3] or any(type(n) is not int or n<2 for n in shape) or np.prod(shape)>1000000: raise ValueError('bounded image grid required')
    def values(payload):
        if set(payload)!= {'real','imag'}: raise ValueError('complete real/imag vectors required')
        re=np.asarray(payload['real']);im=np.asarray(payload['imag'])
        if re.ndim!=1 or re.shape!=im.shape or re.dtype.kind not in 'fiu' or im.dtype.kind not in 'fiu' or not np.isfinite(re).all() or not np.isfinite(im).all(): raise ValueError('finite matched complex vectors required')
        return re+1j*im
    samples=values(signal['values']);actual=values(image['values'])
    if samples.size!=np.prod(shape) or actual.size!=samples.size: raise ValueError('complete paired image/acquisition required')
    indices=np.asarray(signal['grid_indices']);coords=np.asarray(signal['normalized_coordinates']);times=np.asarray(signal['sample_times_s'])
    if times.shape!=(samples.size,) or not np.isfinite(times).all() or np.any(times<0) or np.any(np.diff(times)<0): raise ValueError('bounded acquisition-order sample times required')
    expected=(indices-np.asarray(shape)//2)/np.asarray(shape)
    if coords.shape!=expected.shape or not np.array_equal(coords,expected): raise ValueError('normalized coordinates differ from encoding grid')
    reconstructed=cartesian_reconstruct(indices,samples,tuple(shape)).ravel()
    error=float(np.max(abs(reconstructed-actual)))
    if error>1e-12*max(1.,float(np.max(abs(actual)))): raise ValueError('image is not the inverse transform of the retained signal vector')
    return dict(integrity_passed=True,transform_passed=True,max_absolute_transform_error=error,complex_sample_count=int(samples.size),
        scope='pair integrity and Fourier relationship only; no independent physical/model/clinical revalidation')
