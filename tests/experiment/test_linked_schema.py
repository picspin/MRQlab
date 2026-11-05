"""Common schema checks use complex synthetic data without TSE physics."""
from copy import deepcopy
import numpy as np
import pytest
from mrqlab_experiment.linked_readout import (
    SCHEMA, complex_values, create_linked_readout, verify_linked_readout, validate_linked_edits,
)
from mrqlab_experiment.lab_study import fingerprint


@pytest.fixture
def pair():
    shape=[3,5]; indices=np.array(list(np.ndindex(*shape)))[::-1]
    image=np.arange(15).reshape(shape)/15 + 1j*np.linspace(-.3,.7,15).reshape(shape)
    # A direct, centered forward sum independent of the production FFT.
    positions=np.array(list(np.ndindex(*shape)))-np.array(shape)//2
    coords=(indices-np.array(shape)//2)/shape
    samples=np.exp(-2j*np.pi*(coords@positions.T))@image.ravel()
    return create_linked_readout(
        image=dict(id='complex_map',shape=shape,axes=['row','column'],index_unit='voxel',flatten_order='C',value_unit='synthetic',values=complex_values(image)),
        signal_vector=dict(id='acquisition',axis='acquisition_sample',value_unit='synthetic',complex_convention='real + i*imag',values=complex_values(samples),
            grid_indices=indices.tolist(),grid_index_axes=['row','column'],normalized_coordinates=coords.tolist(),coordinate_unit='cycles/voxel',sample_times_s=(np.arange(15)*.01).tolist(),time_unit='s'),
        structure=dict(shape=shape,label_grid=(np.indices(shape).sum(axis=0)%3).tolist(),label_to_tissue_id=['a','b','c'],origin='synthetic'),
        controls=[dict(field='model.fraction',tissue_id='c',kind='number',value=.4,unit='fraction',min=0.,max=1.),
                  dict(field='model.choice',kind='category',value='one',unit='category',choices=['one','two'])],
        links=[dict(source='acquisition',target='complex_map',transform='centered_inverse_dft',normalization='1/product(shape); no fitted gain')],
        provenance=dict(adapter='synthetic-direct-sum-fixture',source_sha256='a'*64,inputs_sha256='b'*64,runtime={'fixture':'direct sum'},origin='synthetic',
            source_refs=[dict(tissue_id=t,source_ref='synthetic:'+t,origin='synthetic',state={'fraction':.4}) for t in ['a','b','c']]),scope='teaching fixture')


def rehash(pair):
    pair['pair_sha256']=fingerprint({k:v for k,v in pair.items() if k!='pair_sha256'})
    return pair


def test_schema_is_not_tse_specific_and_retains_complex_data(pair):
    assert pair['schema_version']==SCHEMA
    assert 'echo_numbers' not in pair['signal_vector']
    assert len(pair['structure']['label_to_tissue_id'])==3
    assert any(v!=0 for v in pair['image']['values']['imag'])
    checked=verify_linked_readout(pair)
    assert checked['complex_sample_count']==15 and checked['max_absolute_transform_error']<2e-15


@pytest.mark.parametrize('damage',[
    'axes','shape','layout','units','labels','unbound_label','duplicate_tissue','missing_state',
    'empty_origin','source','runtime','transform','ambiguous_transform','duplicate_control','unbound_control','unbounded_control','bool_values','bool_times','bool_indices','bool_labels','category_current','numeric_origin','blank_unit',
])
def test_self_consistent_hash_never_authorizes_invalid_schema(pair,damage):
    if damage=='axes': pair['signal_vector']['grid_index_axes'].reverse()
    elif damage=='shape': pair['structure']['shape']=[5,3]
    elif damage=='layout': pair['image']['flatten_order']='F'
    elif damage=='units': pair['signal_vector']['time_unit']='ms'
    elif damage=='labels': pair['structure']['label_grid'][0]=[0]
    elif damage=='unbound_label': pair['structure']['label_grid'][0][0]=3
    elif damage=='duplicate_tissue': pair['structure']['label_to_tissue_id'][1]='a'
    elif damage=='missing_state': pair['provenance']['source_refs'][0]['state']={}
    elif damage=='empty_origin': pair['provenance']['origin']=''
    elif damage=='source': pair['provenance']['source_sha256']='missing'
    elif damage=='runtime': pair['provenance']['runtime']={}
    elif damage=='transform': pair['links'][0]['transform']='invented'
    elif damage=='ambiguous_transform': pair['links'].append(dict(pair['links'][0]))
    elif damage=='duplicate_control': pair['controls'].append(dict(pair['controls'][0]))
    elif damage=='unbound_control': pair['controls'][0]['tissue_id']='unknown'
    elif damage=='unbounded_control': del pair['controls'][0]['max']
    elif damage=='bool_values': pair['image']['values']['real'][0]=True
    elif damage=='bool_times': pair['signal_vector']['sample_times_s'][0]=False
    elif damage=='bool_indices': pair['signal_vector']['grid_indices'][0][0]=True
    elif damage=='bool_labels': pair['structure']['label_grid'][0][0]=False
    elif damage=='category_current': pair['controls'][1]['value']='invented'
    elif damage=='numeric_origin': pair['provenance']['origin']=1
    else: pair['controls'][0]['unit']=' '
    with pytest.raises(ValueError): verify_linked_readout(rehash(pair))


@pytest.mark.parametrize('view',['image','signal_vector'])
def test_common_typed_edits_accept_both_views_without_mutating_parent(pair,view):
    before=deepcopy(pair)
    checked=validate_linked_edits(pair,[dict(field='model.fraction',tissue_id='c',value=.7,view=view),dict(field='model.choice',value='two',view=view)])
    assert checked[0].view==view and checked[0].value==.7
    assert pair==before


@pytest.mark.parametrize('edit',[
    dict(field='model.fraction',tissue_id='c',value=1.01),
    dict(field='model.fraction',tissue_id='c',value=-.01),
    dict(field='model.fraction',tissue_id='c',value='0.5'),
    dict(field='model.fraction',tissue_id='c',value=True),
    dict(field='model.fraction',tissue_id='c',value=float('inf')),
    dict(field='model.fraction',value=.5),
    dict(field='model.fraction',tissue_id='unknown',value=.5),
    dict(field='model.choice',value='invented'),
    dict(field='model.choice',value='one',tissue_id='a'),
    dict(field='gradient.waveform',value=1.),
    dict(field='image.values.real',value=1.),
    dict(field='model.fraction',tissue_id='c',value=.5,view='other'),
    dict(field='model.fraction',tissue_id='c',value=.5,path='arbitrary'),
])
def test_rejected_edit_preserves_explicit_failure_and_parent(pair,edit):
    before=deepcopy(pair)
    with pytest.raises(ValueError) as error: validate_linked_edits(pair,[edit])
    assert str(error.value) and pair==before


def test_duplicate_cross_view_edits_are_ambiguous(pair):
    with pytest.raises(ValueError,match='ambiguous'):
        validate_linked_edits(pair,[dict(field='model.choice',value='one',view='image'),dict(field='model.choice',value='two',view='signal_vector')])
