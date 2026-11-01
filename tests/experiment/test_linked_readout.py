import copy
from hashlib import sha256
import json
import numpy as np
import pytest
from mrqlab_experiment.tse_imaging import run_tse_imaging
from mrqlab_experiment.linked_readout import verify_linked_readout
from mrqlab_experiment.lab_study import fingerprint


@pytest.mark.parametrize('shape',[(8,5),(2,8,5)])
@pytest.mark.parametrize('order',['linear','centric'])
def test_complete_acquisition_vector_matches_independent_voxel_sum_and_image(shape,order):
    labels=(np.indices(shape).sum(axis=0)%3==0).astype(int)
    r=run_tse_imaging(labels,order=order);p=r['linked_readout'];s=p['signal_vector']
    actual=np.array(s['values']['real'])+1j*np.array(s['values']['imag'])
    xyz=(np.indices(shape)-np.array(shape).reshape((-1,)+(1,)*len(shape))//2).reshape(len(shape),-1).T
    expected=[]
    for echo,coordinate in zip(s['echo_numbers'],s['normalized_coordinates']):
        source=np.take(r['tissue_echo_weights'][:,echo-1],labels).ravel()
        expected.append(np.sum(source*np.exp(-2j*np.pi*(xyz@np.asarray(coordinate)))))
    assert actual==pytest.approx(expected,abs=2e-12)
    assert len(actual)==labels.size and len(s['grid_indices'])==labels.size
    image=np.array(p['image']['values']['real'])+1j*np.array(p['image']['values']['imag'])
    assert image.reshape(shape)==pytest.approx(r['image'],abs=1e-14)
    assert p['structure']['label_grid']==labels.tolist()
    assert np.all(np.diff(s['sample_times_s'])>0)
    assert verify_linked_readout(p)['transform_passed']


@pytest.mark.parametrize('damage',['values','duplicates','times','coordinates','image'])
def test_consistent_pair_checksum_does_not_hide_invalid_transform_or_geometry(damage):
    p=run_tse_imaging(np.indices((8,8))[0]%2)['linked_readout']
    if damage=='values': p['signal_vector']['values']['imag'][0]+=.01
    elif damage=='duplicates': p['signal_vector']['grid_indices'][0]=p['signal_vector']['grid_indices'][1]
    elif damage=='times': p['signal_vector']['sample_times_s'][1]=-1.
    elif damage=='coordinates': p['signal_vector']['normalized_coordinates'][0][0]+=.1
    else: p['image']['values']['real'][0]+=.01
    p['pair_sha256']=fingerprint({k:v for k,v in p.items() if k!='pair_sha256'})
    with pytest.raises(ValueError): verify_linked_readout(p)


def test_signal_image_pair_survives_real_javascript_numeric_roundtrip():
    import subprocess
    p=run_tse_imaging(np.indices((8,8))[0]%2)['linked_readout']
    raw=subprocess.run(['node','-e','let s="";process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>process.stdout.write(JSON.stringify(JSON.parse(s))))'],input=json.dumps(p),text=True,capture_output=True,check=True).stdout
    restored=json.loads(raw)
    assert restored['pair_sha256']==p['pair_sha256'] and verify_linked_readout(restored)['transform_passed']
