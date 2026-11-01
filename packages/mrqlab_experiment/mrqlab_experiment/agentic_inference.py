"""Deterministic agent-readable inference from a common linked image/vector pair.

This is the agentic projection layer: it ingests the complete complex acquisition
vector, the declared structure grid and the pair's declared inverse transform,
then reports structural/image signal proportions and identifiable per-echo
relative coefficients. It renders bounded per-structure modality proxies for
human preview. No language model is called, no tissue is classified and no
clinical interpretation is added.

Identifiability is explicit. For a complete labelling of the image, masks sum to
one, so their Fourier columns differ only by the DC component. At every sampled
non-DC frequency the per-tissue amplitudes are therefore fixed only up to one
common-mode offset. The common mode is identified only at the single DC sample,
which belongs to at most one echo. Per-tissue absolute echo amplitudes and
per-tissue T2 are consequently not inferred. This module reports the
identifiable relative coefficients in a declared zero-common-mode gauge and
absolute amplitudes only for the DC-bearing echo.
"""
from copy import deepcopy
import math
import numpy as np
from mrqlab_recon.spatial import fft_image
from .linked_readout import _hash, verify_linked_readout

SCHEMA = 'mrqlab-agentic-tissue-inference-1'
CANONICALIZATION = 'typed-json-f64-v1'
MAX_SAMPLES = 65536
MAX_TISSUES = 16
MAX_ECHOES = 64
PARSEVAL_RELATIVE_TOLERANCE = 1e-9
STATIC_MODEL_RELATIVE_TOLERANCE = 1e-8
IMAGINARY_RELATIVE_TOLERANCE = 1e-9
FRACTION_SUM_TOLERANCE = 1e-9
SCOPE = ('deterministic agent-readable projection of one linked image/vector pair; '
         'teaching/research simulation only; no language-model call, tissue classification, '
         'patient anatomy, diagnosis or clinical validation')


def _finite(value, name):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError('finite numeric ' + name + ' required')
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError('finite numeric ' + name + ' required') from exc
    if not math.isfinite(result):
        raise ValueError('finite numeric ' + name + ' required')
    return result


def _all_finite(values, name):
    for value in values:
        _finite(value, name)
    return True


def _complex_values(payload):
    real = np.asarray(payload['real'], float)
    imag = np.asarray(payload['imag'], float)
    if real.ndim != 1 or real.shape != imag.shape or not np.isfinite(real).all() or not np.isfinite(imag).all():
        raise ValueError('complete finite complex acquisition required')
    return real + 1j * imag


def _echo_numbers(signal, count):
    """Return validated acquisition echo membership, or (None, reason)."""
    extensions = signal.get('extensions')
    if not isinstance(extensions, dict) or 'echo_numbers' not in extensions:
        return None, 'signal_vector.extensions.echo_numbers is not declared'
    raw = extensions['echo_numbers']
    if not isinstance(raw, list) or len(raw) != count:
        return None, 'declared echo membership must match every acquisition sample'
    if any(type(value) is not int or value < 0 for value in raw):
        return None, 'declared echo numbers must be nonnegative integers'
    unique = sorted(set(raw))
    if not 1 <= len(unique) <= MAX_ECHOES:
        return None, 'declared echo count exceeds the bounded inference limit'
    return np.asarray(raw, int), None


def _counts(labels, tissues):
    counts = [int(np.count_nonzero(labels == index)) for index in range(len(tissues))]
    return counts


def _structure_proportions(labels, tissues, counts):
    total = int(labels.size)
    return {tissue: dict(voxel_count=count, voxel_fraction=float(count / total))
            for tissue, count in zip(tissues, counts)}


def _image_proportions(image, labels, tissues):
    image = np.asarray(image).reshape(labels.shape)
    total_energy = float(np.sum(np.abs(image) ** 2))
    total_magnitude = float(np.sum(np.abs(image)))
    if not math.isfinite(total_energy) or total_energy <= 0 or not math.isfinite(total_magnitude) or total_magnitude <= 0:
        raise ValueError('nonzero finite image signal is required for proportional inference')
    result = {}
    for index, tissue in enumerate(tissues):
        mask = labels == index
        energy = float(np.sum(np.abs(image[mask]) ** 2))
        magnitude = float(np.sum(np.abs(image[mask])))
        result[tissue] = dict(energy=energy, energy_fraction=energy / total_energy,
                              magnitude=magnitude, magnitude_fraction=magnitude / total_magnitude)
    return result


def _echo_times(sample_times, echo_numbers, echo_ids):
    return [float(np.mean(sample_times[echo_numbers == echo])) for echo in echo_ids]


def _identifiable_coefficients(*, labels, tissues, indices, samples, echo_numbers, echo_ids, counts):
    """Solve the static partition model per echo; never invent a common mode."""
    if any(count == 0 for count in counts):
        return dict(available=False,
                    reason='every declared tissue must occupy at least one voxel for coefficient identification',
                    echo_bins=[]), None
    tissue_count = len(tissues)
    masks = [(labels == index).astype(float) for index in range(tissue_count)]
    basis = np.column_stack([fft_image(mask)[tuple(indices.T)] for mask in masks])
    ones = np.ones(tissue_count)
    coefficient_scale = max(1.0, float(np.max(np.abs(basis))))
    coefficients = np.zeros((tissue_count, len(echo_ids)))
    bins = []
    failure = None
    for column, echo in enumerate(echo_ids):
        selected = echo_numbers == echo
        design = basis[selected]
        observed = samples[selected]
        solution, _, rank, _ = np.linalg.lstsq(design, observed, rcond=None)
        projection = float(np.linalg.norm(design @ ones))
        common_mode_identified = projection > 1e-9 * max(1.0, coefficient_scale)
        expected_rank = tissue_count if common_mode_identified else tissue_count - 1
        residual = float(np.linalg.norm(design @ solution - observed) / max(float(np.linalg.norm(observed)), 1e-300))
        bins.append(dict(echo=int(echo), sample_count=int(np.count_nonzero(selected)),
                         rank=int(rank), nullity=int(tissue_count - rank),
                         absolute_amplitude_identified=bool(common_mode_identified and rank == tissue_count),
                         relative_residual=residual))
        if failure is not None:
            continue
        if rank != expected_rank:
            failure = 'sampled Fourier columns are rank-deficient beyond the declared common-mode limitation'
            continue
        if residual > STATIC_MODEL_RELATIVE_TOLERANCE:
            failure = 'acquired samples do not follow the declared static per-tissue Fourier model'
            continue
        imaginary = float(np.max(np.abs(solution.imag))) if solution.size else 0.0
        scale = max(1.0, float(np.max(np.abs(solution.real)))) if solution.size else 1.0
        if imaginary > IMAGINARY_RELATIVE_TOLERANCE * scale:
            failure = 'identified coefficients are not real in the declared partition gauge'
            continue
        if common_mode_identified:
            if float(np.min(solution.real)) < -IMAGINARY_RELATIVE_TOLERANCE * scale:
                failure = 'identified absolute amplitudes are negative'
                continue
        # Zero-common-mode projection makes every echo comparable. For a
        # rank-(T-1) echo this is the least-squares solution itself.
        coefficients[:, column] = solution.real - float(np.mean(solution.real))
    if failure is not None:
        return dict(available=False, reason=failure, echo_bins=bins), None
    absolute = {}
    for entry, echo in zip(bins, echo_ids):
        if entry['absolute_amplitude_identified']:
            selected = echo_numbers == echo
            design = basis[selected]
            solution, _, _, _ = np.linalg.lstsq(design, samples[selected], rcond=None)
            absolute[int(echo)] = {tissue: max(0.0, float(value)) for tissue, value in zip(tissues, solution.real)}
    return dict(available=True, reason=None, echo_bins=bins, coefficients=coefficients,
                absolute=absolute), basis


def _contrast_and_decay(*, coefficients, tissues, echo_ids, echo_times, reference):
    reference_index = tissues.index(reference)
    contrast = {}
    for index, tissue in enumerate(tissues):
        contrast[tissue] = [float(coefficients[index, column] - coefficients[reference_index, column])
                            for column in range(len(echo_ids))]
    decay = {}
    for tissue in tissues:
        if tissue == reference:
            decay[tissue] = dict(value_s=None, fit_residual=None, reason='reference tissue contrast is identically zero')
            continue
        values = contrast[tissue]
        if len(values) < 2:
            decay[tissue] = dict(value_s=None, fit_residual=None, reason='at least two echoes are required for a relative contrast decay fit')
            continue
        if not all(value > 0 for value in values) and not all(value < 0 for value in values):
            decay[tissue] = dict(value_s=None, fit_residual=None, reason='relative contrast changes sign or is zero; a single exponential decay is not identified')
            continue
        times = np.asarray(echo_times, float)
        if np.any(np.diff(times) <= 0):
            decay[tissue] = dict(value_s=None, fit_residual=None, reason='echo mean times are not strictly increasing')
            continue
        log_values = np.log(np.abs(np.asarray(values, float)))
        fit = np.polyfit(times, log_values, 1)
        residual = float(np.max(np.abs(log_values - np.polyval(fit, times))))
        slope = float(fit[0])
        if not math.isfinite(slope) or slope >= 0:
            decay[tissue] = dict(value_s=None, fit_residual=residual, reason='relative contrast does not decay with echo time')
            continue
        value = float(-1.0 / slope)
        if not math.isfinite(value) or value <= 0:
            decay[tissue] = dict(value_s=None, fit_residual=residual, reason='fitted relative contrast time is not finite and positive')
            continue
        decay[tissue] = dict(value_s=value, fit_residual=residual, reason=None)
    strength = {tissue: float(np.sqrt(np.mean(np.square(values)))) for tissue, values in contrast.items()}
    return contrast, decay, strength


def _modality(*, identifier, label, kind, values, shape, axes, basis, note, signed=False):
    flat = np.asarray(values, float).ravel()
    if flat.size != math.prod(shape) or not np.isfinite(flat).all():
        raise ValueError('complete finite modality grid required')
    low = float(np.min(flat)); high = float(np.max(flat))
    if not signed and low < -1e-15:
        raise ValueError('nonnegative modality grid required')
    if high <= 0 and not signed:
        raise ValueError('nonzero modality grid required')
    return dict(id=identifier, label=label, kind=kind, shape=list(shape), axes=list(axes),
                values=flat.tolist(), value_unit='relative a.u.; per-structure constant',
                min=low, max=high, basis=basis, note=note)


def _normalized_per_structure(value_by_tissue, tissues, labels, *, signed=False):
    values = np.asarray([value_by_tissue[tissue] for tissue in tissues], float)
    if signed:
        scale = float(np.max(np.abs(values)))
    else:
        scale = float(np.max(values))
    if not math.isfinite(scale) or scale <= 0:
        raise ValueError('nonzero per-structure values required for modality proxy')
    per_voxel = values / scale
    return per_voxel[np.asarray(labels, int)]


def _modalities(*, labels, tissues, shape, axes, structure, image_signal, acquisition, reference):
    modalities = []
    modalities.append(_modality(
        identifier='structure_voxel_share', label='Structure voxel share (declared grid)',
        kind='structure_proportion',
        values=_normalized_per_structure({tissue: structure[tissue]['voxel_fraction'] for tissue in tissues}, tissues, labels),
        shape=shape, axes=axes,
        basis='declared label grid; voxel fraction normalized to the largest tissue',
        note='declared structural proportion, not measured anatomy'))
    modalities.append(_modality(
        identifier='image_signal_share', label='Reconstructed image signal share',
        kind='signal_proportion',
        values=_normalized_per_structure({tissue: image_signal[tissue]['energy_fraction'] for tissue in tissues}, tissues, labels),
        shape=shape, axes=axes,
        basis='complete complex image energy inside each declared label, normalized to the largest tissue',
        note='relative signal proportion from the declared inverse transform; no anatomy or diagnosis'))
    if not acquisition['available']:
        return modalities
    if acquisition['absolute']:
        echo = sorted(acquisition['absolute'])[0]
        amplitudes = acquisition['absolute'][echo]
        modalities.append(_modality(
            identifier='dc_echo_absolute_amplitude',
            label=f'DC-echo (echo {echo + 1}) absolute amplitude share',
            kind='absolute_amplitude',
            values=_normalized_per_structure(amplitudes, tissues, labels),
            shape=shape, axes=axes,
            basis=f'absolute per-tissue amplitude identified at the DC sample of echo {echo + 1}',
            note='absolute amplitude at one echo only; other echoes keep the unidentified common mode'))
    per_echo = acquisition['contrast_vs_reference']
    for name, column, description in [('early', 0, 'first echo'), ('late', len(acquisition['echo_ids']) - 1, 'last echo')]:
        if name == 'late' and len(acquisition['echo_ids']) < 2:
            continue
        values = {tissue: per_echo[tissue][column] for tissue in tissues}
        if max(abs(value) for value in values.values()) <= 0:
            continue
        modalities.append(_modality(
            identifier=f'{name}_relative_contrast',
            label=f'Relative contrast vs {reference} ({description})',
            kind='relative_contrast',
            values=_normalized_per_structure(values, tissues, labels, signed=True),
            shape=shape, axes=axes,
            basis=f'identifiable zero-common-mode coefficient difference at the {description}',
            note='signed relative contrast proxy; absolute per-tissue amplitude and T2 remain unidentified',
            signed=True))
    return modalities


def infer_tissue_modalities(pair, *, reference_tissue_id=None, max_samples=MAX_SAMPLES):
    """Infer bounded, identifiable structure proportions and modality proxies."""
    if type(max_samples) is not int or not 1 <= max_samples <= 1000000:
        raise ValueError('bounded integer inference sample limit required')
    verify_linked_readout(pair)
    image_payload = pair['image']; signal = pair['signal_vector']; structure_payload = pair['structure']
    shape = list(image_payload['shape']); axes = list(image_payload['axes'])
    tissues = list(structure_payload['label_to_tissue_id'])
    labels = np.asarray(structure_payload['label_grid'], int)
    image = _complex_values(image_payload['values'])
    samples = _complex_values(signal['values'])
    indices = np.asarray(signal['grid_indices'], int)
    sample_times = np.asarray(signal['sample_times_s'], float)
    sample_count = int(samples.size)
    if sample_count > max_samples:
        raise ValueError('linked pair exceeds the bounded agentic inference sample limit')
    if len(tissues) < 2:
        raise ValueError('at least two declared structure tissues are required for proportional inference')
    if len(tissues) > MAX_TISSUES:
        raise ValueError('declared structure tissue count exceeds the bounded inference limit')
    reference = tissues[0] if reference_tissue_id is None else reference_tissue_id
    if reference not in tissues:
        raise ValueError('reference tissue is not declared by the linked structure grid')
    counts = _counts(labels, tissues)
    structure = _structure_proportions(labels, tissues, counts)
    image_signal = _image_proportions(image, labels, tissues)

    image_energy = float(np.sum(np.abs(image) ** 2))
    signal_energy = float(np.sum(np.abs(samples) ** 2))
    expected_image_energy = signal_energy / math.prod(shape)
    parseval_error = float(abs(image_energy - expected_image_energy) / max(image_energy, 1e-300))

    echo_numbers, echo_reason = _echo_numbers(signal, sample_count)
    echo_ids = sorted(set(int(value) for value in echo_numbers)) if echo_numbers is not None else []
    echo_times = _echo_times(sample_times, echo_numbers, echo_ids) if echo_ids else []
    echo_bins = []
    acquisition = dict(available=False, reason=echo_reason, echo_ids=echo_ids,
                       coefficients={}, contrast_vs_reference={}, decay={}, strength={},
                       absolute={}, echo_bins=echo_bins)
    if echo_numbers is not None:
        echo_bins.extend([dict(echo=int(echo), sample_count=int(np.count_nonzero(echo_numbers == echo)),
                               mean_time_s=float(echo_times[column]),
                               kspace_energy=float(np.sum(np.abs(samples[echo_numbers == echo]) ** 2)))
                          for column, echo in enumerate(echo_ids)])
        solved, _ = _identifiable_coefficients(labels=labels, tissues=tissues, indices=indices,
                                               samples=samples, echo_numbers=echo_numbers,
                                               echo_ids=echo_ids, counts=counts)
        acquisition['reason'] = solved['reason']
        for entry in solved['echo_bins']:
            match = next(item for item in echo_bins if item['echo'] == entry['echo'])
            match.update({key: entry[key] for key in ('rank', 'nullity', 'absolute_amplitude_identified', 'relative_residual')})
        if solved['available']:
            coefficients = solved['coefficients']
            contrast, decay, strength = _contrast_and_decay(
                coefficients=coefficients, tissues=tissues, echo_ids=echo_ids,
                echo_times=echo_times, reference=reference)
            acquisition.update(available=True, reason=None,
                               coefficients={tissue: [float(value) for value in coefficients[index]]
                                             for index, tissue in enumerate(tissues)},
                               contrast_vs_reference=contrast, decay=decay, strength=strength,
                               absolute=solved['absolute'])

    modalities = _modalities(labels=labels, tissues=tissues, shape=shape, axes=axes, structure=structure,
                             image_signal=image_signal, acquisition=acquisition, reference=reference)

    unavailable = [
        dict(item='per_tissue_t2_map',
             reason='per-tissue absolute echo amplitudes are not identifiable from one complete Cartesian partition; only relative coefficients are reported'),
        dict(item='t1_weighted_modality',
             reason='one declared TR does not identify T1; no T1 map or T1-weighted proxy is inferred'),
        dict(item='tissue_classification',
             reason='structure labels are declared inputs; no histological or clinical tissue classification is performed'),
        dict(item='measured_anatomy',
             reason='declared/synthetic structure grid only; no patient anatomy, registration or partial-volume model'),
    ]
    if not acquisition['available']:
        unavailable.append(dict(item='per_echo_coefficients', reason=acquisition['reason']))
    if not acquisition['absolute']:
        unavailable.append(dict(item='absolute_echo_amplitudes',
                                reason='the DC sample is absent or not identifiable; the common-mode amplitude is unidentified'))
    for tissue, fit in acquisition['decay'].items():
        if fit['reason'] is not None:
            unavailable.append(dict(item='relative_contrast_decay:' + tissue, reason=fit['reason']))

    checks = dict(
        pair_integrity=True,
        complete_signal_read=sample_count == math.prod(shape) and indices.shape == (sample_count, len(shape)),
        parseval_energy_consistency=parseval_error <= PARSEVAL_RELATIVE_TOLERANCE,
        echo_membership_declared=echo_numbers is not None,
        static_partition_linear_model=acquisition['available'],
        identifiable_coefficient_basis=acquisition['available'] and all(
            entry['rank'] in (len(tissues), len(tissues) - 1) for entry in echo_bins if 'rank' in entry),
        structure_proportions_normalized=abs(sum(item['voxel_fraction'] for item in structure.values()) - 1.0) <= FRACTION_SUM_TOLERANCE,
        image_proportions_normalized=abs(sum(item['energy_fraction'] for item in image_signal.values()) - 1.0) <= FRACTION_SUM_TOLERANCE,
        modalities_complete=all(len(item['values']) == math.prod(shape) and math.isfinite(item['min'])
                                and math.isfinite(item['max']) for item in modalities),
    )
    body = dict(
        schema_version=SCHEMA,
        canonicalization=CANONICALIZATION,
        source=dict(pair_sha256=pair['pair_sha256'], linked_schema_version=pair['schema_version'],
                    adapter=pair['provenance']['adapter'], origin=pair['provenance']['origin'],
                    source_sha256=pair['provenance']['source_sha256'],
                    inputs_sha256=pair['provenance']['inputs_sha256'],
                    runtime=deepcopy(pair['provenance']['runtime']),
                    image_id=image_payload['id'], signal_id=signal['id'],
                    shape=shape, axes=axes, tissue_ids=tissues,
                    structure_origin=structure_payload['origin'], linked_scope=pair['scope']),
        ingestion=dict(sample_count=sample_count, voxel_count=math.prod(shape),
                       complete_unique_grid_indices=True,
                       signal_energy=signal_energy, image_energy=image_energy,
                       parseval_signal_energy=expected_image_energy,
                       parseval_image_energy=image_energy,
                       parseval_relative_error=parseval_error,
                       transform_max_absolute_error=0.0,
                       echo_ids=echo_ids, echo_times_s=echo_times, echo_bins=echo_bins),
        proportions=dict(structure=structure, image_signal=image_signal,
                         acquisition=dict(
                             available=acquisition['available'], reason=acquisition['reason'],
                             echo_ids=echo_ids, echo_bins=echo_bins,
                             coefficients=acquisition['coefficients'],
                             contrast_vs_reference=acquisition['contrast_vs_reference'],
                             relative_contrast_strength=acquisition['strength'],
                             apparent_relative_contrast_decay_s={tissue: fit['value_s'] for tissue, fit in acquisition['decay'].items()},
                             decay_fit_residual={tissue: fit['fit_residual'] for tissue, fit in acquisition['decay'].items()},
                             absolute_dc_echo={str(echo): values for echo, values in acquisition['absolute'].items()},
                             identifiability=dict(
                                 gauge='zero-common-mode relative coefficients',
                                 common_mode='identified only by a sampled DC point; at most one echo',
                                 per_tissue_absolute_amplitudes='not identifiable for echoes without the DC sample',
                                 per_tissue_t2='not inferred from relative differences'))),
        reference=dict(tissue_id=reference,
                       definition='explicit request' if reference_tissue_id is not None else 'first declared tissue'),
        modalities=modalities,
        unavailable=unavailable,
        validation=dict(passed=all(checks.values()), checks=checks,
                        tolerances=dict(parseval_relative_error=PARSEVAL_RELATIVE_TOLERANCE,
                                        static_model_relative_residual=STATIC_MODEL_RELATIVE_TOLERANCE,
                                        imaginary_relative=IMAGINARY_RELATIVE_TOLERANCE,
                                        fraction_sum=FRACTION_SUM_TOLERANCE),
                        scope='numerical identifiability checks only; not physics, anatomy or clinical validation'),
        limits=dict(max_samples=max_samples, max_tissues=MAX_TISSUES, max_echoes=MAX_ECHOES),
        scope=SCOPE)
    body['inference_sha256'] = _hash(body)
    verify_agentic_inference(body)
    return body


_EXPECTED = {'schema_version', 'canonicalization', 'source', 'ingestion', 'proportions', 'reference',
             'modalities', 'unavailable', 'validation', 'limits', 'scope', 'inference_sha256'}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _hash64(value):
    return isinstance(value, str) and len(value) == 64 and all(character in '0123456789abcdef' for character in value)


def _bounded_fraction(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and 0 <= value <= 1


def verify_agentic_inference(inference):
    """Integrity and structural checks; full replay proves the computation."""
    try:
        return _verify(inference)
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError('malformed agentic tissue inference') from exc


def _verify(inference):
    if not isinstance(inference, dict) or set(inference) != _EXPECTED:
        raise ValueError('unsupported agentic tissue inference schema')
    if inference['schema_version'] != SCHEMA or inference['canonicalization'] != CANONICALIZATION:
        raise ValueError('unsupported agentic tissue inference schema')
    if _hash({key: value for key, value in inference.items() if key != 'inference_sha256'}) != inference['inference_sha256']:
        raise ValueError('agentic inference hash mismatch')
    source = inference['source']
    shape = source['shape']; tissues = source['tissue_ids']
    if (not isinstance(shape, list) or len(shape) not in (2, 3)
            or any(type(value) is not int or value < 2 for value in shape)):
        raise ValueError('bounded 2D/3D inference grid required')
    if (not isinstance(tissues, list) or not 2 <= len(tissues) <= MAX_TISSUES
            or len(set(tissues)) != len(tissues) or any(not _text(tissue) for tissue in tissues)):
        raise ValueError('unique declared tissue identifiers required')
    if not all(_hash64(source[key]) for key in ('pair_sha256', 'source_sha256', 'inputs_sha256')):
        raise ValueError('linked pair and source pins required')
    if (not isinstance(source['runtime'], dict) or not source['runtime']
            or not all(_text(source[key]) for key in ('adapter', 'origin', 'image_id', 'signal_id', 'structure_origin', 'linked_scope'))):
        raise ValueError('linked provenance and view identifiers required')
    if (not isinstance(source['axes'], list) or len(source['axes']) != len(shape)
            or len(set(source['axes'])) != len(source['axes']) or any(not _text(axis) for axis in source['axes'])):
        raise ValueError('shared unique spatial axes required')

    ingestion = inference['ingestion']
    count = math.prod(shape)
    if (type(ingestion['sample_count']) is not int or ingestion['sample_count'] != count
            or type(ingestion['voxel_count']) is not int or ingestion['voxel_count'] != count
            or ingestion['complete_unique_grid_indices'] is not True):
        raise ValueError('complete acquisition read required')
    for key in ('signal_energy', 'image_energy', 'parseval_signal_energy', 'parseval_image_energy',
                'parseval_relative_error', 'transform_max_absolute_error'):
        if _finite(ingestion[key], key) < 0:
            raise ValueError('finite nonnegative ingestion quantities required')
    echo_ids = ingestion['echo_ids']; echo_times = ingestion['echo_times_s']; echo_bins = ingestion['echo_bins']
    if (not isinstance(echo_ids, list) or len(echo_ids) != len(set(echo_ids))
            or any(type(echo) is not int or echo < 0 for echo in echo_ids)
            or len(echo_ids) > MAX_ECHOES or len(echo_times) != len(echo_ids)
            or not isinstance(echo_bins, list) or len(echo_bins) != len(echo_ids)):
        raise ValueError('bounded echo membership required')
    for time in echo_times:
        if _finite(time, 'echo time') < 0:
            raise ValueError('nonnegative echo times required')
    for entry in echo_bins:
        if (type(entry['echo']) is not int or entry['echo'] not in echo_ids
                or type(entry['sample_count']) is not int or entry['sample_count'] < 1
                or _finite(entry['mean_time_s'], 'mean echo time') < 0
                or _finite(entry['kspace_energy'], 'kspace energy') < 0):
            raise ValueError('malformed echo bin')
        if 'rank' in entry and (type(entry['rank']) is not int or type(entry['nullity']) is not int
                                or not isinstance(entry['absolute_amplitude_identified'], bool)
                                or _finite(entry['relative_residual'], 'relative residual') < 0):
            raise ValueError('malformed echo identifiability diagnostics')

    proportions = inference['proportions']
    structure = proportions['structure']; image_signal = proportions['image_signal']; acquisition = proportions['acquisition']
    if set(structure) != set(tissues) or set(image_signal) != set(tissues):
        raise ValueError('proportions must cover every declared tissue')
    for tissue in tissues:
        item = structure[tissue]
        if (type(item['voxel_count']) is not int or item['voxel_count'] < 0
                or not _bounded_fraction(item['voxel_fraction'])):
            raise ValueError('bounded structure proportions required')
        item = image_signal[tissue]
        if (_finite(item['energy'], 'image energy') < 0 or _finite(item['magnitude'], 'image magnitude') < 0
                or not _bounded_fraction(item['energy_fraction']) or not _bounded_fraction(item['magnitude_fraction'])):
            raise ValueError('bounded image signal proportions required')
    if (abs(sum(item['voxel_fraction'] for item in structure.values()) - 1) > FRACTION_SUM_TOLERANCE
            or abs(sum(item['energy_fraction'] for item in image_signal.values()) - 1) > FRACTION_SUM_TOLERANCE):
        raise ValueError('normalized structure/image proportions required')
    if not isinstance(acquisition['available'], bool):
        raise ValueError('explicit acquisition inference availability required')
    if acquisition['available']:
        if acquisition['reason'] is not None:
            raise ValueError('available inference cannot carry an unavailable reason')
        if set(acquisition['coefficients']) != set(tissues) or set(acquisition['contrast_vs_reference']) != set(tissues):
            raise ValueError('coefficient proportions must cover every declared tissue')
        for tissue in tissues:
            values = acquisition['coefficients'][tissue]
            contrast = acquisition['contrast_vs_reference'][tissue]
            if (not isinstance(values, list) or len(values) != len(echo_ids)
                    or not isinstance(contrast, list) or len(contrast) != len(echo_ids)):
                raise ValueError('complete per-echo coefficient vectors required')
            for value in values + contrast:
                _finite(value, 'relative coefficient')
        reference = inference['reference']['tissue_id']
        if reference not in tissues or any(abs(value) > 1e-12 for value in acquisition['contrast_vs_reference'][reference]):
            raise ValueError('zero reference-tissue contrast required')
        for echo in acquisition['absolute_dc_echo']:
            if not echo.isdigit() or int(echo) not in echo_ids or set(acquisition['absolute_dc_echo'][echo]) != set(tissues):
                raise ValueError('malformed absolute DC-echo amplitudes')
            if any(_finite(value, 'absolute amplitude') < 0 for value in acquisition['absolute_dc_echo'][echo].values()):
                raise ValueError('nonnegative absolute amplitudes required')
    else:
        if not _text(acquisition['reason']) or acquisition['coefficients'] or acquisition['contrast_vs_reference']:
            raise ValueError('explicit unavailable acquisition reason required')
    if inference['reference']['tissue_id'] not in tissues or not _text(inference['reference']['definition']):
        raise ValueError('declared reference tissue required')

    modalities = inference['modalities']
    if not isinstance(modalities, list) or not 1 <= len(modalities) <= 8:
        raise ValueError('bounded modality proxies required')
    seen = set()
    for item in modalities:
        if item['id'] in seen:
            raise ValueError('duplicate modality proxy identifier')
        seen.add(item['id'])
        if (item['kind'] not in {'structure_proportion', 'signal_proportion', 'absolute_amplitude', 'relative_contrast'}
                or item['shape'] != shape or item['axes'] != source['axes']
                or not isinstance(item['values'], list) or len(item['values']) != count
                or not _all_finite(item['values'], 'modality value')
                or _finite(item['min'], 'modality minimum') > _finite(item['max'], 'modality maximum')
                or not all(_text(item[key]) for key in ('label', 'value_unit', 'basis', 'note'))):
            raise ValueError('malformed modality proxy')
        if item['kind'] != 'relative_contrast' and item['min'] < -1e-15:
            raise ValueError('nonnegative proportion modality required')
    unavailable = inference['unavailable']
    if (not isinstance(unavailable, list) or len(unavailable) > 64
            or any(not isinstance(item, dict) or set(item) != {'item', 'reason'}
                   or not _text(item['item']) or not _text(item['reason']) for item in unavailable)):
        raise ValueError('explicit bounded unavailable-item reasons required')
    validation = inference['validation']; limits = inference['limits']
    if (not isinstance(validation['passed'], bool) or not isinstance(validation['checks'], dict)
            or not validation['checks'] or any(not isinstance(value, bool) for value in validation['checks'].values())
            or validation['passed'] != all(validation['checks'].values())
            or not isinstance(validation['tolerances'], dict)
            or any(not _finite(value, 'tolerance') or value <= 0 for value in validation['tolerances'].values())
            or not _text(validation['scope'])):
        raise ValueError('explicit numerical validation block required')
    if (type(limits['max_samples']) is not int or type(limits['max_tissues']) is not int
            or type(limits['max_echoes']) is not int or count > limits['max_samples']
            or len(tissues) > limits['max_tissues'] or len(echo_ids) > limits['max_echoes']):
        raise ValueError('declared inference limits exceeded')
    if not _text(inference['scope']):
        raise ValueError('explicit inference scope required')
    return dict(integrity_passed=True, inference_sha256=inference['inference_sha256'],
                passed=validation['passed'], sample_count=count, tissue_count=len(tissues),
                scope='integrity and identifiability structure only; full replay proves the computation')
