"""Common linked complex image/vector core, with explicitly registered transforms.

The first verified transform is complete Cartesian centered inverse DFT. Modality
physics and control-to-input mappings belong to adapters, never this schema.
"""
from copy import deepcopy
import math
from typing import Literal
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
from mrqlab_recon.spatial import cartesian_reconstruct

SCHEMA = 'mrqlab-linked-image-vector-1'


def _hash(value):
    from .lab_study import fingerprint
    return fingerprint(value)


def complex_values(data):
    a = np.asarray(data, complex).ravel()
    return dict(real=a.real.tolist(), imag=a.imag.tolist())


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class LinkedEdit(Strict):
    """A semantic edit from either view; its bound descriptor supplies the type."""
    field: str = Field(min_length=1, max_length=128, pattern=r'^[a-zA-Z][a-zA-Z0-9_.]*$')
    value: float | str
    tissue_id: str | None = Field(default=None, min_length=1, max_length=128)
    view: Literal['image', 'signal_vector'] | None = None


class Control(Strict):
    field: str = Field(min_length=1, max_length=128, pattern=r'^[a-zA-Z][a-zA-Z0-9_.]*$')
    tissue_id: str | None = None
    value: float | str
    unit: str = Field(min_length=1)
    kind: Literal['number', 'category']
    min: float | None = None
    max: float | None = None
    choices: list[str] | None = None

    @model_validator(mode='after')
    def bounded(self):
        if not self.unit.strip():
            raise ValueError('explicit control unit required')
        if self.kind == 'number':
            if self.min is None or self.max is None or self.min > self.max or self.choices is not None:
                raise ValueError('explicit finite numeric control bounds required')
            if not isinstance(self.value, float):
                raise ValueError('numeric control value required')
        elif self.min is not None or self.max is not None or not self.choices or len(set(self.choices)) != len(self.choices):
            raise ValueError('explicit unique category choices required')
        elif any(not choice.strip() for choice in self.choices) or self.value not in self.choices:
            raise ValueError('declared current category required')
        return self

    def check_value(self, value):
        if self.kind == 'number':
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError('finite numeric control value required')
            if not self.min <= value <= self.max:
                raise ValueError('out-of-range or extrapolated control value: ' + self.field)
        elif type(value) is not str or value not in self.choices:
            raise ValueError('unsupported category value: ' + self.field)


def validate_linked_edits(pair, updates):
    """Return validated edits, never mutate a parent or directly write samples."""
    verify_linked_readout(pair)
    if not isinstance(updates, list) or not 1 <= len(updates) <= 8:
        raise ValueError('one to eight typed edits required')
    controls = {(c['field'], c.get('tissue_id')): Control.model_validate(c) for c in pair['controls']}
    seen = set(); checked = []
    for raw in updates:
        edit = LinkedEdit.model_validate(raw.model_dump(mode='json') if isinstance(raw, BaseModel) else raw)
        key = (edit.field, edit.tissue_id)
        if key in seen:
            raise ValueError('duplicate or ambiguous semantic edit')
        seen.add(key)
        if key not in controls:
            raise ValueError('unsupported or unbound control (physical gradient waveform edits unsupported): ' + edit.field)
        controls[key].check_value(edit.value)
        checked.append(edit)
    return checked


def create_linked_readout(*, image, signal_vector, structure, controls, links, provenance, scope):
    body = deepcopy(dict(schema_version=SCHEMA, canonicalization='typed-json-f64-v1', image=image,
        signal_vector=signal_vector, structure=structure, controls=controls, links=links, provenance=provenance, scope=scope))
    body['pair_sha256'] = _hash(body)
    verify_linked_readout(body)
    return body


def _numeric(value, name):
    def no_bools(v):
        if isinstance(v,list): return all(no_bools(x) for x in v)
        return type(v) in (int,float)
    if not no_bools(value):
        raise ValueError('finite numeric ' + name + ' required')
    a = np.asarray(value)
    if a.dtype.kind not in 'fiu' or not np.isfinite(a).all():
        raise ValueError('finite numeric ' + name + ' required')
    return a


def _integers(value, name):
    def valid(v):
        return all(valid(x) for x in v) if isinstance(v,list) else type(v) is int
    if not isinstance(value,list) or not valid(value):
        raise ValueError('integer ' + name + ' required; booleans are unsupported')
    return np.asarray(value)


def _text(value):
    return isinstance(value,str) and bool(value.strip())


def verify_linked_readout(pair):
    """Integrity/geometry/transform checks; computational replay proves physics."""
    try:
        return _verify(pair)
    except (KeyError, TypeError, IndexError, OverflowError) as exc:
        raise ValueError('malformed common linked image/vector schema') from exc


def _verify(pair):
    expected = {'schema_version','canonicalization','image','signal_vector','structure','controls','links','provenance','scope','pair_sha256'}
    if not isinstance(pair, dict) or set(pair) != expected or pair['schema_version'] != SCHEMA or pair['canonicalization'] != 'typed-json-f64-v1':
        raise ValueError('unsupported common linked image/vector schema')
    if _hash({k:v for k,v in pair.items() if k != 'pair_sha256'}) != pair['pair_sha256']:
        raise ValueError('image/signal pair hash mismatch')
    image = pair['image']; signal = pair['signal_vector']; shape = image['shape']
    if not isinstance(shape, list) or len(shape) not in (2,3) or any(type(n) is not int or n < 2 for n in shape) or math.prod(shape) > 1000000:
        raise ValueError('bounded image grid required')
    axes = image['axes']
    if len(axes) != len(shape) or len(set(axes)) != len(axes) or any(not isinstance(a,str) or not a for a in axes) or signal['grid_index_axes'] != axes:
        raise ValueError('shared unique spatial axes required')
    if not all(_text(v) for v in [image['id'],signal['id'],image['value_unit'],signal['value_unit']]):
        raise ValueError('explicit view identifiers and value units required')
    if image['flatten_order'] != 'C' or image['index_unit'] != 'voxel' or signal['coordinate_unit'] != 'cycles/voxel' or signal['time_unit'] != 's' or image['value_unit'] != signal['value_unit']:
        raise ValueError('unsupported image/vector layout or units')
    if signal['complex_convention'] != 'real + i*imag' or signal['axis'] != 'acquisition_sample':
        raise ValueError('explicit complex acquisition convention required')
    def values(payload):
        if set(payload) != {'real','imag'}:
            raise ValueError('complete real/imag vectors required')
        re = _numeric(payload['real'], 'real values'); im = _numeric(payload['imag'], 'imag values')
        if re.ndim != 1 or re.shape != im.shape:
            raise ValueError('finite matched complex vectors required')
        return re + 1j*im
    samples = values(signal['values']); actual = values(image['values'])
    if samples.size != math.prod(shape) or actual.size != samples.size:
        raise ValueError('complete paired image/acquisition required')
    indices = _integers(signal['grid_indices'], 'grid indices'); coords = _numeric(signal['normalized_coordinates'], 'coordinates'); times = _numeric(signal['sample_times_s'], 'times')
    if indices.shape != (samples.size,len(shape)) or indices.dtype.kind not in 'iu' or np.any(indices < 0) or np.any(indices >= shape) or len(np.unique(indices,axis=0)) != samples.size:
        raise ValueError('complete unique bounded integer grid indices required')
    if times.shape != (samples.size,) or np.any(times < 0) or np.any(np.diff(times) < 0):
        raise ValueError('bounded acquisition-order sample times required')
    expected_coords = (indices - np.asarray(shape)//2)/np.asarray(shape)
    if coords.shape != expected_coords.shape or not np.array_equal(coords, expected_coords):
        raise ValueError('normalized coordinates differ from encoding grid')
    structure = pair['structure']; labels = _integers(structure['label_grid'], 'tissue labels'); tissues = structure['label_to_tissue_id']
    if structure['shape'] != shape or labels.shape != tuple(shape) or labels.dtype.kind not in 'iu' or not tissues or len(set(tissues)) != len(tissues) or any(not isinstance(t,str) or not t.strip() for t in tissues) or np.any(labels < 0) or np.any(labels >= len(tissues)):
        raise ValueError('complete bound spatial tissue labels required')
    controls = pair['controls']; seen = set()
    if not isinstance(controls,list) or len(controls) > 128:
        raise ValueError('bounded control descriptors required')
    for raw in controls:
        c = Control.model_validate(raw); key = (c.field,c.tissue_id)
        if key in seen or (c.tissue_id is not None and c.tissue_id not in tissues):
            raise ValueError('ambiguous or unbound control descriptor')
        seen.add(key)
        # Low-level adapter runs can use a larger physical domain than the safe
        # record-edit API. Such current values are readable, never edit bounds.
    provenance = pair['provenance']
    for key in ['source_sha256','inputs_sha256']:
        value = provenance[key]
        if not isinstance(value,str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('source/input pin required')
    if not all(_text(v) for v in [provenance['adapter'],provenance['origin'],structure['origin'],pair['scope']]) or not isinstance(provenance['runtime'],dict) or not provenance['runtime'] or not provenance['source_refs']:
        raise ValueError('runtime, adapter, provenance and origin required')
    refs = provenance['source_refs']
    if not isinstance(refs,list) or len(refs) != len(tissues) or {r['tissue_id'] for r in refs} != set(tissues) or any(not _text(r['source_ref']) or not _text(r['origin']) or not isinstance(r['state'],dict) or not r['state'] for r in refs):
        raise ValueError('per-tissue state, source and origin bindings required')
    if image['id'] == signal['id'] or not image['id'] or not signal['id']:
        raise ValueError('distinct linked view identifiers required')
    transform = dict(source=signal['id'],target=image['id'],transform='centered_inverse_dft',normalization='1/product(shape); no fitted gain')
    if pair['links'].count(transform) != 1:
        raise ValueError('unsupported or ambiguous image/vector transform')
    if any(l['target'] == image['id'] and l != transform for l in pair['links']):
        raise ValueError('unsupported image/vector transform')
    reconstructed = cartesian_reconstruct(indices,samples,tuple(shape)).ravel()
    error = float(np.max(abs(reconstructed-actual)))
    if error > 1e-12*max(1.,float(np.max(abs(actual)))):
        raise ValueError('image is not the inverse transform of the retained signal vector')
    return dict(integrity_passed=True,transform_passed=True,max_absolute_transform_error=error,complex_sample_count=int(samples.size),
        scope='pair integrity and Fourier relationship only; no independent physical/model/clinical revalidation')
