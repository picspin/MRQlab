"""Echo-resolved Cartesian teaching readout; no scanner waveform execution."""
import numpy as np
from mrqlab_sequence import build_sequence
from mrqlab_recon.spatial import fft_image, ifft_image, cartesian_indices, cartesian_reconstruct, image_quality
from .spatial_imaging import _hash
from .family_recipes import build_family_recipe
from .kernel import run_experiment
from .observations import build_result_graph

SCOPE = ('Teaching/research spoiled periodic EPG, ideal hard CPMG RF and Cartesian '
         'encoding; no scanner validation or clinical quality certification; no B1 '
         'inhomogeneity, physical gradient timing, motion, parallel imaging or slice selection. '
         'One echo-center tissue amplitude is held constant across each ideal Fourier line.')


def psf_metrics(modulation):
    """Discrete amplitude PSF metrics, no gain normalization of image data.

    Width is the count of contiguous half-amplitude samples through the peak.
    Sidelobe is maximum amplitude outside that region / peak (not a first-null
    definition). RMS radius includes all periodic-grid energy and ringing.
    """
    psf = ifft_image(modulation)
    a = abs(psf); peak_index = np.unravel_index(np.argmax(a), a.shape)
    peak = float(a[peak_index])
    core = np.ones(a.shape, bool); widths = []
    for axis, n in enumerate(a.shape):
        cut = [*peak_index]; cut[axis] = slice(None)
        profile = a[tuple(cut)]; center = peak_index[axis]
        lo = hi = center
        while lo > 0 and profile[lo-1] >= peak/2: lo -= 1
        while hi+1 < n and profile[hi+1] >= peak/2: hi += 1
        widths.append(hi-lo+1)
        axis_mask = (np.arange(n) >= lo) & (np.arange(n) <= hi)
        dims = [1]*a.ndim; dims[axis] = n
        core &= axis_mask.reshape(dims)
    radius2 = np.zeros(a.shape)
    for axis, n in enumerate(a.shape):
        d = abs(np.arange(n)-peak_index[axis]); d = np.minimum(d, n-d)
        dims = [1]*a.ndim; dims[axis] = n
        radius2 += (d*d).reshape(dims)
    return dict(psf=psf, peak=peak, half_amplitude_width_voxels=widths,
                outside_half_mainlobe_peak_ratio=float(a[~core].max(initial=0)/peak),
                rms_radius_voxels=float(np.sqrt(np.sum(radius2*a*a)/np.sum(a*a))))


def prepare_tse_echo_train(*, echoes, echo_spacing_s, tr_s, t2_s,
                           refocusing_angle=180., refocusing_end_angle=180.,
                           max_work=100000000, experiment=None):
    """Shared periodic EPG echo centers; no spatial acquisition or mean weighting."""
    if type(echoes) is not int or not 1 <= echoes <= 64:
        raise ValueError('bounded integer echo count required')
    if len(t2_s) != 2 or not np.isfinite([echo_spacing_s,tr_s,*t2_s]).all() or min(echo_spacing_s,tr_s,*t2_s)<=0:
        raise ValueError('two finite positive T2 values and sequence timing required')
    if type(max_work) is not int or max_work <= 0:
        raise ValueError('positive integer EPG work budget required')
    experiment_input = None
    if experiment is None:
        graph = build_family_recipe('brain_t1_3d_tse')
    else:
        from .models import ExperimentGraph, TemplateRef
        validated = ExperimentGraph.model_validate(experiment)
        experiment_input = validated.model_dump(mode='json')
        graph = validated.model_copy(deep=True)
        if not isinstance(graph.sequence, TemplateRef) or graph.sequence.template != 'TSE3D' or graph.engine.preferred != 'epg':
            raise ValueError('TSE imaging requires a TSE3D EPG experiment chassis')
        if not isinstance(graph.tissue, tuple) or len(graph.tissue) != 2 or graph.physiology is not None or graph.disturbances.items:
            raise ValueError('two independent tissues without physiology/disturbances required')
        if graph.sample.pools or graph.sample.isochromats or graph.sample.off_resonance_hz:
            raise ValueError('TSE imaging chassis does not support pool/spatial/off-resonance sample overrides')
        if any(t.flow_velocity_mps or t.exchange_rate_hz or t.bound_pool or t.diffusion_adc_mm2_s for t in graph.tissue):
            raise ValueError('TSE imaging chassis requires independent relaxation tissues')
    graph.sequence.params.update(te=echo_spacing_s, tr=tr_s, echoes=echoes, partitions=1,
        refocusing_flip_angle=refocusing_angle, refocusing_end_angle=refocusing_end_angle)
    # One sample per existing 2ms ADC gate: exact echo center, not train mean.
    graph.engine.options.update(dwell_time=.002, epg_kmax=max(8, 2*echoes), max_work=max_work)
    sequence = build_sequence('TSE3D', graph.sequence.params)
    weights = []; physical = []; preparation_s = []; physical_work = 0
    for tissue, t2 in zip(graph.tissue, t2_s):
        tissue.t2 = t2
        g = graph.model_copy(deep=True); g.tissue = tissue
        result = run_experiment(g)
        signal = np.abs(result.sim_result.signal)
        if signal.shape != (echoes,) or not np.isfinite(signal).all() or signal.max() <= 0:
            raise ValueError('EPG echo/ADC count mismatch or invalid signal')
        weights.append(signal)
        physical.append(build_result_graph(result).observations[0].provenance.model_dump(mode='json'))
        physical_work += result.sim_result.meta['estimated_work']
        preparation_s.append(result.sim_result.meta['preparation_duration_s'])
    if physical_work > max_work:
        raise ValueError('combined EPG work exceeds budget')
    return graph,sequence,np.array(weights),physical,preparation_s,physical_work,experiment_input


def run_tse_imaging(labels, *, echoes=4, order='centric', echo_spacing_s=.008,
                    tr_s=.4, partitions=None, t2_s=(.04, .12),
                    refocusing_angle=180., refocusing_end_angle=180.,
                    weighting='echo', max_samples=1000000, max_work=100000000,
                    max_duration_s=10000., experiment=None):
    """Design -> periodic EPG -> timed full Cartesian readout -> image/PSF.

    Contiguous segments of linear/centric ky traversal form trains; kz is centric.
    Each TR has exactly `echoes` lines. Ny must be divisible by echoes. Periodic
    prepared train is reused at every TR; spatial encoding has no spin feedback.
    Magnitude EPG at exact echo centers defines a real tissue-specific transfer
    function (phase/off-resonance imaging is outside this model).
    """
    labels = np.asarray(labels)
    if labels.ndim not in (2, 3) or min(labels.shape) < 2 or not np.isin(labels, [0, 1]).all():
        raise ValueError('two-class 2D/3D labels required')
    nz, ny, nx = (1, *labels.shape) if labels.ndim == 2 else labels.shape
    if type(echoes) is not int or echoes < 1 or ny % echoes:
        raise ValueError('echo count must divide ky line count exactly')
    if partitions is not None and (type(partitions) is not int or partitions != nz):
        raise ValueError('partition count must match grid kz')
    if order not in {'linear', 'centric'} or weighting not in {'echo', 'mean'}:
        raise ValueError('unsupported ordering or weighting')
    for value in (echo_spacing_s, tr_s, max_duration_s, *t2_s):
        if not np.isfinite(value) or value <= 0: raise ValueError('positive finite timing required')
    if len(t2_s) != 2: raise ValueError('two tissue T2 values required')
    for value in (max_samples, max_work):
        if type(value) is not int or value <= 0: raise ValueError('positive integer budget required')
    trains = nz*ny//echoes
    # Work includes mask transforms, reconstruction, PSFs and the EPG budget.
    spatial_work = int(8*labels.size*max(1, np.ceil(np.log2(labels.size))))
    if labels.size > max_samples or spatial_work >= max_work or trains*tr_s > max_duration_s:
        raise ValueError('infeasible readout budget')
    graph,sequence,weights,physical,preparation_s,physical_work,experiment_input = prepare_tse_echo_train(
        echoes=echoes,echo_spacing_s=echo_spacing_s,tr_s=tr_s,t2_s=t2_s,
        refocusing_angle=refocusing_angle,refocusing_end_angle=refocusing_end_angle,
        max_work=max_work-spatial_work,experiment=experiment)
    if spatial_work+physical_work > max_work:
        raise ValueError('combined EPG and spatial work exceeds budget')
    if trains*tr_s+max(preparation_s) > max_duration_s:
        raise ValueError('prepared readout exceeds duration budget')
    weights = np.array(weights)
    ky = list(range(ny)); kz = sorted(range(nz), key=lambda z:(abs(z-nz//2), z))
    if order == 'centric': ky.sort(key=lambda y:(abs(y-ny//2), y))
    modulation = np.zeros((2, *labels.shape)); timeline = []; train = 0
    rf = sequence.channel('rf_amp')
    for z in kz:
        for start in range(0, ny, echoes):
            offset = train*tr_s
            entry = dict(train=train, excitation_s=offset,
                refocusing_s=[offset+e.time for e in rf if e.time > 0],
                refocusing_degrees=[e.value for e in rf if e.time > 0],
                tr_end_s=offset+tr_s, lines=[])
            for echo, y in enumerate(ky[start:start+echoes]):
                center = offset+(echo+1)*echo_spacing_s
                line = dict(ky=y, kz=z, echo=echo+1, echo_time_s=(echo+1)*echo_spacing_s,
                            adc_start_s=center, adc_end_s=center+.002, samples=nx,
                            dwell_s=.002/nx, kx_indices=list(range(nx)),
                            tissue_weights=(weights[:, echo] if weighting == 'echo' else weights.mean(axis=1)).tolist())
                entry['lines'].append(line)
                index = (slice(None), y, slice(None)) if labels.ndim == 2 else (slice(None), z, y, slice(None))
                modulation[index] = (weights[:, echo] if weighting == 'echo' else weights.mean(axis=1))[:, None]
            timeline.append(entry); train += 1
    masks = np.array([labels == i for i in range(2)])
    kspace = sum(fft_image(mask)*m for mask, m in zip(masks, modulation))
    indices = cartesian_indices(labels.shape)
    image = cartesian_reconstruct(indices, kspace[tuple(indices.T)], labels.shape)
    reference = np.take(weights.mean(axis=1), labels.astype(int))
    psfs = [psf_metrics(m) for m in modulation]
    # Convolution theorem verifies the tissue-wise PSF forward model independently.
    prediction = sum(ifft_image(fft_image(mask)*fft_image(p['psf'])) for mask, p in zip(masks, psfs))
    inputs = dict(labels=labels.tolist(), echoes=echoes, order=order, echo_spacing_s=echo_spacing_s,
        tr_s=tr_s, partitions=partitions, t2_s=list(t2_s), refocusing_angle=refocusing_angle,
        refocusing_end_angle=refocusing_end_angle, weighting=weighting,
        max_samples=max_samples, max_work=max_work, max_duration_s=max_duration_s)
    if experiment is not None: inputs['experiment'] = experiment_input
    question = graph.clinical_recipe.question.research_question if experiment is not None and graph.clinical_recipe else 'How do T2, echo ordering and train length alter tissue contrast and spatial resolution?'
    return dict(clinical_question=question,
        design=graph.model_dump(mode='json'), timeline=timeline, echo_times_s=np.arange(1, echoes+1)*echo_spacing_s,
        tissue_echo_weights=weights, modulation=modulation, psfs=psfs, image=image, reference=reference,
        quality=image_quality(reference, image, 1e-10),
        psf_prediction_quality=image_quality(prediction, image, 1e-10), scope=SCOPE,
        provenance=dict(version='tse-psf-v1', replay=inputs, input_hash=_hash(inputs), physical=physical,
            sequence=sequence.model_dump(mode='json'), timeline_hash=_hash(timeline),
            samples_hash=_hash([kspace.real.tolist(), kspace.imag.tolist()]),
            estimated_samples=int(labels.size), estimated_work=spatial_work+physical_work,
            acquisition_duration_s=trains*tr_s, preparation_duration_s=max(preparation_s),
            total_duration_s=trains*tr_s+max(preparation_s),
            weight_method='absolute periodic EPG at exact echo center; constant along kx; tissue-wise linear Fourier encoding'))
