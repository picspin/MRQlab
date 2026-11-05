import numpy as np
import pytest
from mrqlab_experiment.tse_imaging import run_tse_imaging, psf_metrics
from mrqlab_recon.spatial import cartesian_acquire, cartesian_reconstruct


def phantom(ndim=2):
    y, x = np.indices((16, 16))
    p = (((y-8)**2+(x-8)**2 < 20) | ((x == 3) & (y > 3))).astype(int)
    return p if ndim == 2 else np.stack([p, 1-p, np.roll(p, 2, 0), p])


@pytest.mark.parametrize('ndim', [2, 3])
@pytest.mark.parametrize('echoes', [2, 4, 8])
@pytest.mark.parametrize('order', ['linear', 'centric'])
def test_tse_echo_readout_psf_and_replay(ndim, echoes, order):
    labels = phantom(ndim)
    r = run_tse_imaging(labels, echoes=echoes, order=order)
    assert r['psf_prediction_quality']['passed']
    assert r['quality']['nrmse'] > 1e-3
    assert r['tissue_echo_weights'][0, -1] < r['tissue_echo_weights'][0, 0]
    assert r['psfs'][0]['rms_radius_voxels'] > r['psfs'][1]['rms_radius_voxels']
    lines = [line for t in r['timeline'] for line in t['lines']]
    assert len(lines)*labels.shape[-1] == labels.size
    assert len({(line['kz'], line['ky']) for line in lines}) == len(lines)
    for train in r['timeline']:
        assert len(train['refocusing_s']) == echoes
        assert all(train['excitation_s'] < rf < line['adc_start_s'] < line['adc_end_s'] < train['excitation_s']+.4
                   for rf, line in zip(train['refocusing_s'], train['lines']))
    if ndim == 2 and echoes == 4:
        replay = run_tse_imaging(**r['provenance']['replay'])
        assert replay['image'] == pytest.approx(r['image'])
        assert replay['provenance'] == r['provenance']


@pytest.mark.parametrize('ndim', [2, 3])
def test_constant_echo_weight_ideal_recovery_regression(ndim):
    r = run_tse_imaging(phantom(ndim), weighting='mean')
    coords, samples = cartesian_acquire(r['reference'])
    ideal = cartesian_reconstruct(coords, samples, r['reference'].shape)
    assert r['image'] == pytest.approx(ideal, abs=1e-12)
    assert r['quality']['passed']
    assert max(p['rms_radius_voxels'] for p in r['psfs']) < 1e-12


def test_order_and_t2_change_modulation_and_resolution():
    linear = run_tse_imaging(phantom(), echoes=8, order='linear')
    centric = run_tse_imaging(phantom(), echoes=8)
    assert not np.allclose(linear['image'], centric['image'])
    assert not np.allclose(linear['modulation'], centric['modulation'])
    assert centric['psfs'][0]['rms_radius_voxels'] > centric['psfs'][1]['rms_radius_voxels']
    short = run_tse_imaging(phantom(), echoes=2)
    assert short['quality']['nrmse'] < centric['quality']['nrmse']


@pytest.mark.parametrize('patch', [dict(echoes=3), dict(partitions=2), dict(tr_s=.02),
    dict(echo_spacing_s=.003), dict(echoes=True), dict(order='bad'), dict(weighting='bad'),
    dict(max_samples=1), dict(max_work=1), dict(max_duration_s=.1), dict(t2_s=(0., .1)),
    dict(refocusing_angle=190.)])
def test_invalid_tse_design_and_budgets(patch):
    with pytest.raises(ValueError): run_tse_imaging(phantom(), **patch)


def test_failed_readout_reports_epg_work_actually_consumed():
    """A budget failure after both tissue EPG runs must expose the real work.

    The cap is shared across the per-tissue runs, so a failure can consume more
    than the cap; the raised error carries the spent EPG work for honest ledgers.
    """
    from mrqlab_experiment.tse_imaging import ReadoutWorkError
    with pytest.raises(ReadoutWorkError) as caught:
        run_tse_imaging(phantom(), echoes=8, max_work=80000)
    assert caught.value.estimated_work > 80000
    assert str(caught.value)=='combined EPG and spatial work exceeds budget'
    # A design error rejected before any EPG run consumes no work and stays a
    # plain ValueError, so callers cannot charge budget for a rejected request.
    with pytest.raises(ValueError) as early:
        run_tse_imaging(phantom(), echoes=8, t2_s=(0., .1))
    assert not isinstance(early.value, ReadoutWorkError)


def test_failed_tse_preparation_reports_partial_tissue_work():
    """A family preparation failure exposes its already executed EPG work."""
    from mrqlab_experiment.family_recipes import build_family_recipe
    from mrqlab_experiment.tse_imaging import ReadoutWorkError
    graph=build_family_recipe('brain_t1_3d_tse').model_dump(mode='json')
    graph['tissue'][0]['t1']=.001
    with pytest.raises(ReadoutWorkError) as caught:
        run_tse_imaging(phantom(), echoes=8, max_work=50000, experiment=graph)
    assert str(caught.value)=='TSE steady preparation exceeds max_work'
    assert caught.value.estimated_work==59796


def test_discrete_psf_metrics_known_delta_and_lowpass():
    delta = psf_metrics(np.ones((16, 16)))
    assert delta['half_amplitude_width_voxels'] == [1, 1]
    assert delta['outside_half_mainlobe_peak_ratio'] == 0
    lowpass = np.zeros((16, 16)); lowpass[6:11, :] = 1
    p = psf_metrics(lowpass)
    assert p['half_amplitude_width_voxels'][0] > 1
    assert p['rms_radius_voxels'] > 0


def test_180_degree_train_t2_decay_and_explicit_line_weights():
    r = run_tse_imaging(phantom(3), echoes=8, refocusing_angle=180., refocusing_end_angle=180.)
    w = r['tissue_echo_weights']
    # Periodic T1 preparation sets amplitude; exact 180 CPMG gives exp(-TE/T2).
    assert w[:, 1:]/w[:, :-1] == pytest.approx(
        np.repeat(np.exp(-.008/np.array([.04, .12]))[:, None], 7, axis=1), abs=1e-9)
    for train in r['timeline']:
        for line in train['lines']:
            assert r['modulation'][:, line['kz'], line['ky'], 0] == pytest.approx(line['tissue_weights'])
            assert line['adc_start_s'] == pytest.approx(train['excitation_s']+line['echo_time_s'])
            assert line['dwell_s']*line['samples'] == pytest.approx(.002)


def test_psf_predicts_known_phantom_by_direct_circular_convolution():
    r = run_tse_imaging(phantom(), echoes=8)
    prediction = np.zeros((16, 16), complex)
    for tissue, p in enumerate(r['psfs']):
        for y, x in np.argwhere(phantom() == tissue):
            prediction += np.roll(p['psf'], (y-8, x-8), axis=(0, 1))
    assert prediction == pytest.approx(r['image'], abs=1e-12)


def test_variable_refocusing_epg_changes_echo_weights():
    fixed = run_tse_imaging(phantom())
    ramp = run_tse_imaging(phantom(), refocusing_angle=140., refocusing_end_angle=110.)
    assert not np.allclose(fixed['tissue_echo_weights'], ramp['tissue_echo_weights'])
    assert ramp['psf_prediction_quality']['passed']
