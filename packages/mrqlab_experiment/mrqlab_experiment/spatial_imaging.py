"""Replayable spatial teaching chains on top of existing family physics.

The extra Fourier readout is an explicit ideal encoding model, not a claim
that sparse authored family ADC events already acquire a complete image.
"""
from hashlib import sha256
import json
import numpy as np
from mrqlab_recon.spatial import (cartesian_acquire, cartesian_reconstruct,
    radial_acquire, radial_reconstruct, image_quality)
from mrqlab_recon.noncartesian import radial_cgls
from .family_recipes import build_family_recipe
from .family_execution import adc_map
from .kernel import run_experiment
from .observations import build_result_graph

SCOPE = ('research/teaching ideal independent voxels and Fourier encoding; no scanner '
         'validation, clinical quality certification, parallel imaging, compressed sensing, '
         'flow, slice selection, gating, noise or EPI distortion; TSE mean-echo weighting')


def _hash(value):
    return sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def run_spatial_imaging(chain, labels, *, encoding='cartesian', order='sequential_ky',
                        spokes=96, points=64, acceleration=1, max_samples=1000000,
                        max_work=100000000, quality_threshold=None, reconstruction='gridding',
                        inverse_max_iterations=1500, inverse_tolerance=1e-12,
                        max_memory_bytes=134217728):
    """Design -> family simulation -> acquisition -> reconstruction -> validation.

    labels assigns each voxel to one of two known tissue classes. Provenance
    stores all replay inputs plus hashes of measured Fourier samples. Budgets
    count complex samples and direct-DFT multiply terms, not scanner time/SAR.
    CEST reports Z(-3.5)-Z(+3.5); ADC units are mm²/s.
    """
    recipes = dict(cartesian_2d='brain_t1_3d_tse', partition_3d='brain_t1_3d_tse',
                   noncartesian='brain_t1_3d_tse', cest='cest_multi_pool_z_spectrum', adc='brain_epse_dwi')
    if chain not in recipes or encoding not in {'cartesian', 'radial', 'stack_of_stars'}:
        raise ValueError('unsupported chain or encoding')
    if reconstruction not in {'gridding', 'cgls'} or (encoding == 'cartesian' and reconstruction != 'gridding'):
        raise ValueError('unsupported reconstruction for encoding')
    labels = np.asarray(labels)
    if labels.ndim not in (2, 3) or min(labels.shape) < 2 or not np.isin(labels, [0, 1]).all():
        raise ValueError('two-class 2D/3D label grid required')
    if (chain == 'cartesian_2d' and labels.ndim != 2) or (chain == 'partition_3d' and labels.ndim != 3):
        raise ValueError('inconsistent chain grid dimensions')
    if chain != 'noncartesian' and encoding != 'cartesian':
        raise ValueError('chain requires Cartesian encoding')
    if chain == 'noncartesian' and (encoding == 'cartesian' or (encoding == 'radial') != (labels.ndim == 2)):
        raise ValueError('radial is 2D; stack_of_stars is 3D')
    for budget in (max_samples, max_work):
        if type(budget) is not int or budget <= 0:
            raise ValueError('positive integer budgets required')
    for count in (spokes, points, acceleration):
        if type(count) is not int or count <= 0:
            raise ValueError('invalid encoding count')
    if order not in {'sequential_ky', 'centric_ky', 'epi'} or (encoding != 'cartesian' and acceleration != 1):
        raise ValueError('invalid encoding order/acceleration')
    frames = 7 if chain == 'cest' else 2 if chain == 'adc' else 1
    count = (labels.size if encoding == 'cartesian' else spokes*points*(labels.shape[0] if labels.ndim == 3 else 1))*frames
    work = count*(labels.shape[-1]*labels.shape[-2] if encoding != 'cartesian' else 1)
    if count > max_samples or work > max_work:
        raise ValueError('infeasible acquisition budget')
    threshold = quality_threshold if quality_threshold is not None else (1e-6 if reconstruction == 'cgls' else 0.4 if encoding != 'cartesian' else 1e-10)
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError('invalid quality threshold')
    graph = build_family_recipe(recipes[chain]); physical = []; sources = []
    if chain == 'partition_3d':
        graph.sequence.params['partitions'] = labels.shape[0]

    def run(g):
        result = run_experiment(g)
        physical.append(build_result_graph(result).observations[0].provenance.model_dump(mode='json'))
        return result

    if chain == 'cest':
        spectra = []; offsets = None
        for scale in (1., .5):
            g = graph.model_copy(deep=True)
            # Scale both directions to retain detailed balance and pool fractions.
            g.sequence.metadata['cest']['exchange_matrix_hz'] = (np.array(g.sequence.metadata['cest']['exchange_matrix_hz'])*scale).tolist()
            r = run(g); offsets = np.asarray(r.sim_result.z_spectrum['offset_ppm'])
            spectra.append(r.sim_result.z_spectrum['Z'])
        sources = [np.take(np.array(spectra)[:, i], labels.astype(int)) for i in range(len(offsets))]
        target = sources[np.flatnonzero(np.isclose(offsets, -3.5))[0]]-sources[np.flatnonzero(np.isclose(offsets, 3.5))[0]]
        units = 'Z(-3.5 ppm)-Z(+3.5 ppm)'
    else:
        tissue_signals = []; b = None; truth = []
        for tissue in graph.tissue:
            g = graph.model_copy(deep=True); g.tissue = tissue
            r = run(g); weighted = float(np.mean(abs(r.sim_result.signal)))
            if chain == 'adc':
                b = r.sim_result.meta['b_value_s_mm2']
                g.sequence.params['diffusion_gradient_mt_m'] = 0.
                baseline = float(np.mean(abs(run(g).sim_result.signal)))
                tissue_signals.append([baseline, weighted]); truth.append(tissue.diffusion_adc_mm2_s)
            else:
                tissue_signals.append([weighted])
        sources = [np.take(np.array(tissue_signals)[:, i], labels.astype(int)) for i in range(frames)]
        target = np.take(truth, labels.astype(int)) if chain == 'adc' else sources[0]
        units = 'mm2/s' if chain == 'adc' else 'relative signal'
    reconstructions = []; acquisitions = []; solvers = []; total_work = work
    for source in sources:
        if encoding == 'cartesian':
            coords, samples = cartesian_acquire(source, order, acceleration)
            recon = cartesian_reconstruct(coords, samples, source.shape)
        else:
            coords, samples = radial_acquire(source, spokes, points)
            if reconstruction == 'cgls':
                recon, solver = radial_cgls(coords, samples, source.shape,
                    max_iterations=inverse_max_iterations, tolerance=inverse_tolerance,
                    max_work=max_work-total_work, max_memory_bytes=max_memory_bytes)
                total_work += solver['estimated_work']; solvers.append(solver)
            else:
                recon = radial_reconstruct(coords, samples, source.shape)
        reconstructions.append(recon.real)
        acquisitions.append(dict(coordinates=coords.tolist(), sample_shape=list(samples.shape),
                                 samples_hash=_hash([samples.real.tolist(), samples.imag.tolist()])))
    if chain == 'adc':
        image = adc_map([0, b], np.array(reconstructions))
    elif chain == 'cest':
        image = reconstructions[np.flatnonzero(np.isclose(offsets, -3.5))[0]]-reconstructions[np.flatnonzero(np.isclose(offsets, 3.5))[0]]
    else:
        image = reconstructions[0]
    quality = image_quality(target, image, threshold)
    inputs = dict(chain=chain, labels=labels.tolist(), encoding=encoding, order=order,
                  spokes=spokes, points=points, acceleration=acceleration,
                  max_samples=max_samples, max_work=max_work, quality_threshold=threshold,
                  reconstruction=reconstruction, inverse_max_iterations=inverse_max_iterations,
                  inverse_tolerance=inverse_tolerance, max_memory_bytes=max_memory_bytes)
    return dict(clinical_question=graph.clinical_recipe.question.research_question,
                design=graph.model_dump(mode='json'), image=image, reference=target,
                source_images=np.array(sources), reconstructed_frames=np.array(reconstructions),
                quality=quality, units=units, scope=SCOPE, solvers=solvers,
                provenance=dict(version='spatial-cgls-v1' if reconstruction == 'cgls' else 'spatial-v1', replay=inputs, input_hash=_hash(inputs),
                                physical=physical, acquisitions=acquisitions,
                                estimated_samples=count, estimated_work=total_work,
                                reconstruction=reconstruction, solvers=solvers,
                                approximation='exact discrete Fourier model; bounded CGLS, no gain fit; small-grid reference, not NUFFT' if reconstruction == 'cgls' else 'linear splat with radial density weights and local weight normalization; no deapodization' if encoding != 'cartesian' else 'ideal Cartesian FFT'))
