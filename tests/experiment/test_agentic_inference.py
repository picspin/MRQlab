"""Agent-readable inference from the common linked image/vector schema."""
from copy import deepcopy
import json
import math
import numpy as np
import pytest
from mrqlab_experiment.agentic_inference import (
    SCHEMA, infer_tissue_modalities, verify_agentic_inference,
)
from mrqlab_experiment.linked_readout import complex_values, create_linked_readout
from mrqlab_experiment.lab_study import fingerprint
from mrqlab_experiment.tse_imaging import run_tse_imaging
from mrqlab_recon.spatial import cartesian_indices, cartesian_reconstruct, fft_image


def _labels():
    y,x=np.indices((16,16))
    return ((((x-8)**2+(y-8)**2<20)|((x==3)&(y>3))).astype(int))


@pytest.fixture(scope='module')
def tse_run():
    return run_tse_imaging(_labels().tolist(),echoes=4,order='centric',echo_spacing_s=.008,
                           tr_s=.4,t2_s=(.04,.12),refocusing_angle=180.,refocusing_end_angle=180.)


@pytest.fixture(scope='module')
def tse_pair(tse_run): return tse_run['linked_readout']


def _provenance(tissues):
    return dict(adapter='synthetic-direct-sum',source_sha256='a'*64,inputs_sha256='b'*64,
                runtime={'fixture':'direct sum'},origin='synthetic',
                source_refs=[dict(tissue_id=t,source_ref='synthetic:'+t,origin='synthetic',state={'x':1})
                             for t in tissues])


def _direct_pair(*, shape, labels, tissues, echo_numbers=None, times=None):
    indices=np.array(list(np.ndindex(*shape)))[::-1]
    rng=np.random.default_rng(17)
    image=(rng.normal(size=math.prod(shape))+1j*rng.normal(size=math.prod(shape))).reshape(shape)
    positions=np.array(list(np.ndindex(*shape)))-np.array(shape)//2
    coords=(indices-np.array(shape)//2)/np.array(shape)
    samples=np.exp(-2j*np.pi*(coords@positions.T))@image.ravel()
    signal=dict(id='acquisition',axis='acquisition_sample',value_unit='synthetic',
                complex_convention='real + i*imag',values=complex_values(samples),
                grid_indices=indices.tolist(),grid_index_axes=['row','column'],
                normalized_coordinates=coords.tolist(),coordinate_unit='cycles/voxel',
                sample_times_s=(np.arange(len(samples))*.01).tolist(),time_unit='s')
    if echo_numbers is not None:
        signal['extensions']=dict(echo_numbers=echo_numbers)
        signal['sample_times_s']=times
    return create_linked_readout(
        image=dict(id='complex_map',shape=list(shape),axes=['row','column'],index_unit='voxel',
                   flatten_order='C',value_unit='synthetic',values=complex_values(image)),
        signal_vector=signal,
        structure=dict(shape=list(shape),label_grid=np.asarray(labels).tolist(),
                       label_to_tissue_id=list(tissues),origin='synthetic'),
        controls=[dict(field='model.fraction',tissue_id=tissues[-1],kind='number',value=.5,
                       unit='fraction',min=0.,max=1.)],
        links=[dict(source='acquisition',target='complex_map',transform='centered_inverse_dft',
                    normalization='1/product(shape); no fitted gain')],
        provenance=_provenance(tissues),scope='agentic inference fixture')


@pytest.fixture(scope='module')
def generic_pair():
    return _direct_pair(shape=[3,5],labels=np.indices([3,5]).sum(axis=0)%3,tissues=['a','b','c'])


@pytest.fixture(scope='module')
def nonstatic_echo_pair():
    count=16
    labels=np.random.default_rng(17).integers(0,3,size=(4,4))
    return _direct_pair(shape=[4,4],labels=labels,tissues=['a','b','c'],
                        echo_numbers=[0]*8+[1]*8,times=(np.arange(count)*.01).tolist())


@pytest.fixture(scope='module')
def same_t2_pair():
    shape=[16,16]; echoes=4; lines_per=shape[0]//echoes; t2=.05
    labels=_labels(); indices=cartesian_indices(shape)
    echo_numbers=np.array([y//lines_per+1 for y,x in indices])
    weights={0:.2*np.exp(-np.arange(1,echoes+1)*.008/t2),
             1:.12*np.exp(-np.arange(1,echoes+1)*.008/t2)}
    grid=np.zeros(shape,complex)
    for echo in range(1,echoes+1):
        selected=echo_numbers==echo
        full=sum(fft_image((labels==index).astype(float))*weights[index][echo-1] for index in (0,1))
        grid[tuple(indices[selected].T)]=full[tuple(indices[selected].T)]
    image=cartesian_reconstruct(indices,grid[tuple(indices.T)],shape)
    times=np.array([echo*.008 for echo in echo_numbers])
    return create_linked_readout(
        image=dict(id='image',shape=shape,axes=['y','x'],index_unit='voxel',flatten_order='C',
                   value_unit='a.u.',values=complex_values(image)),
        signal_vector=dict(id='signal',axis='acquisition_sample',value_unit='a.u.',
                           complex_convention='real + i*imag',values=complex_values(grid[tuple(indices.T)]),
                           grid_indices=indices.tolist(),grid_index_axes=['y','x'],
                           normalized_coordinates=((indices-np.array(shape)//2)/np.array(shape)).tolist(),
                           coordinate_unit='cycles/voxel',sample_times_s=times.tolist(),time_unit='s',
                           extensions=dict(echo_numbers=echo_numbers.tolist())),
        structure=dict(shape=shape,label_grid=labels.tolist(),label_to_tissue_id=['a','b'],origin='synthetic'),
        controls=[dict(field='model.fraction',tissue_id='b',kind='number',value=.5,
                       unit='fraction',min=0.,max=1.)],
        links=[dict(source='signal',target='image',transform='centered_inverse_dft',
                    normalization='1/product(shape); no fitted gain')],
        provenance=_provenance(['a','b']),scope='same-T2 synthetic fixture')


def test_reads_complete_signal_and_reports_exact_structure_and_image_proportions(tse_pair):
    before=deepcopy(tse_pair)
    inference=infer_tissue_modalities(tse_pair)
    assert inference['schema_version']==SCHEMA
    assert inference['source']['pair_sha256']==tse_pair['pair_sha256']
    assert inference['ingestion']['sample_count']==inference['ingestion']['voxel_count']==256
    assert inference['ingestion']['parseval_relative_error']<=1e-12
    labels=np.asarray(tse_pair['structure']['label_grid']);tissues=tse_pair['structure']['label_to_tissue_id']
    image=(np.asarray(tse_pair['image']['values']['real'])
           +1j*np.asarray(tse_pair['image']['values']['imag'])).reshape(labels.shape)
    total_energy=float(np.sum(np.abs(image)**2));total_magnitude=float(np.sum(np.abs(image)))
    for index,tissue in enumerate(tissues):
        mask=labels==index
        expected_count=int(np.count_nonzero(mask))
        item=inference['proportions']['structure'][tissue]
        assert item['voxel_count']==expected_count
        assert item['voxel_fraction']==pytest.approx(expected_count/256,rel=0,abs=1e-15)
        signal=inference['proportions']['image_signal'][tissue]
        assert signal['energy']==pytest.approx(float(np.sum(np.abs(image[mask])**2)),rel=1e-14)
        assert signal['magnitude']==pytest.approx(float(np.sum(np.abs(image[mask]))),rel=1e-14)
        assert signal['energy_fraction']==pytest.approx(float(np.sum(np.abs(image[mask])**2))/total_energy,rel=1e-14)
    assert verify_agentic_inference(inference)['integrity_passed']
    assert tse_pair==before
    assert infer_tissue_modalities(tse_pair)['inference_sha256']==inference['inference_sha256']
    json.dumps(inference,allow_nan=False)


def test_absolute_amplitudes_are_identified_only_at_the_dc_echo(tse_pair,tse_run):
    inference=infer_tissue_modalities(tse_pair)
    acquisition=inference['proportions']['acquisition']
    assert acquisition['available'] and inference['validation']['passed']
    bins=inference['ingestion']['echo_bins']
    absolute=[entry for entry in bins if entry['absolute_amplitude_identified']]
    assert len(absolute)==1 and absolute[0]['rank']==2 and absolute[0]['nullity']==0
    assert all(entry['rank']==1 and entry['nullity']==1 for entry in bins if not entry['absolute_amplitude_identified'])
    echo=str(absolute[0]['echo'])
    assert set(acquisition['absolute_dc_echo'])=={echo}
    weights=tse_run['tissue_echo_weights'];tissues=tse_pair['structure']['label_to_tissue_id']
    for index,tissue in enumerate(tissues):
        assert acquisition['absolute_dc_echo'][echo][tissue]==pytest.approx(
            float(weights[index,absolute[0]['echo']-1]),rel=1e-12,abs=1e-15)
    assert acquisition['contrast_vs_reference'][tissues[0]]==[0.,0.,0.,0.]
    assert all(value is None for value in acquisition['apparent_relative_contrast_decay_s'].values())
    assert any(item['item']=='per_tissue_t2_map' for item in inference['unavailable'])
    assert any(item['item']=='t1_weighted_modality' for item in inference['unavailable'])


def test_same_t2_pair_recovers_relative_contrast_decay_not_a_tissue_t2_map(same_t2_pair):
    inference=infer_tissue_modalities(same_t2_pair)
    acquisition=inference['proportions']['acquisition']
    assert acquisition['available']
    contrast=acquisition['contrast_vs_reference']['b']
    assert all(value<0 for value in contrast)
    assert acquisition['apparent_relative_contrast_decay_s']['b']==pytest.approx(.05,rel=1e-9)
    assert acquisition['decay_fit_residual']['b']==pytest.approx(0.,abs=1e-12)
    assert acquisition['apparent_relative_contrast_decay_s']['a'] is None
    assert acquisition['relative_contrast_strength']['b']>0
    bins=inference['ingestion']['echo_bins']
    absolute=next(entry for entry in bins if entry['absolute_amplitude_identified'])
    assert sum(entry['absolute_amplitude_identified'] for entry in bins)==1
    assert set(acquisition['absolute_dc_echo'])=={str(absolute['echo'])}
    assert any(item['item']=='per_tissue_t2_map' for item in inference['unavailable'])


def test_link_without_echo_membership_keeps_structure_proportions_and_reports_gap(generic_pair):
    inference=infer_tissue_modalities(generic_pair,reference_tissue_id='b')
    assert inference['reference']==dict(tissue_id='b',definition='explicit request')
    assert inference['ingestion']['echo_ids']==[]
    assert inference['proportions']['acquisition']['available'] is False
    assert 'echo_numbers' in inference['proportions']['acquisition']['reason']
    assert inference['validation']['passed'] is False
    assert inference['validation']['checks']['echo_membership_declared'] is False
    assert abs(sum(item['voxel_fraction'] for item in inference['proportions']['structure'].values())-1)<1e-12
    assert abs(sum(item['energy_fraction'] for item in inference['proportions']['image_signal'].values())-1)<1e-12
    assert {item['id'] for item in inference['modalities']}=={'structure_voxel_share','image_signal_share'}
    assert any(item['item']=='per_echo_coefficients' for item in inference['unavailable'])
    assert verify_agentic_inference(inference)['integrity_passed']


def test_non_static_partition_signal_is_not_forced_into_the_amplitude_model(nonstatic_echo_pair):
    inference=infer_tissue_modalities(nonstatic_echo_pair)
    acquisition=inference['proportions']['acquisition']
    assert acquisition['available'] is False
    assert 'static per-tissue Fourier model' in acquisition['reason']
    assert acquisition['coefficients']=={}
    assert inference['validation']['passed'] is False
    assert len(inference['ingestion']['echo_bins'])==2
    assert all(entry['relative_residual']>1e-8 for entry in inference['ingestion']['echo_bins'])


def test_reference_and_bounds_are_rejected_explicitly(generic_pair,tse_pair):
    with pytest.raises(ValueError,match='reference tissue'): infer_tissue_modalities(generic_pair,reference_tissue_id='unknown')
    with pytest.raises(ValueError,match='bounded agentic inference sample limit'): infer_tissue_modalities(tse_pair,max_samples=10)
    with pytest.raises(ValueError,match='bounded integer inference sample limit'): infer_tissue_modalities(tse_pair,max_samples=True)


def test_integrity_hash_detects_tampering_but_replay_is_the_computational_proof(tse_pair):
    inference=infer_tissue_modalities(tse_pair)
    tampered=deepcopy(inference)
    tampered['proportions']['acquisition']['relative_contrast_strength']['gray_matter']+=1e-3
    with pytest.raises(ValueError,match='hash mismatch'): verify_agentic_inference(tampered)
    # A self-consistent rehash passes the structural verifier; only the scientific
    # record replay recomputes the signal and rejects it.
    tampered['inference_sha256']=fingerprint({k:v for k,v in tampered.items() if k!='inference_sha256'})
    assert verify_agentic_inference(tampered)['integrity_passed']
    broken=deepcopy(inference);broken['modalities']=[]
    broken['inference_sha256']=fingerprint({k:v for k,v in broken.items() if k!='inference_sha256'})
    with pytest.raises(ValueError,match='bounded modality proxies'): verify_agentic_inference(broken)
