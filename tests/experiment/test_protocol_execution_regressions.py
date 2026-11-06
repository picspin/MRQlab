import numpy as np
import pytest
from mrqlab_experiment import build_protocol_experiment
from mrqlab_experiment.compiler import compile_sequence
from mrqlab_experiment.objectives import evaluate_multi_tissue_contrast
from mrqlab_physics import Phantom, Isochromat
from mrqlab_physics.backends.epg import EPGBackend
from mrqlab_physics.ops.types import Relax, RfOp

IDS = ('brain_lesion_t2_tse', 'knee_cartilage_meniscus_pd_t2_tse')

@pytest.mark.parametrize('recipe', IDS)
def test_declared_echo_count_is_compiled(recipe):
    graph = build_protocol_experiment(recipe)
    assert compile_sequence(graph).metadata['echoes'] == graph.sequence.params['echo_count']

@pytest.mark.parametrize('recipe', IDS)
def test_default_clinical_vector_is_executable(recipe):
    graph = build_protocol_experiment(recipe)
    assert graph.objective is not None
    assert graph.objective.clinical_vector == graph.clinical_recipe.objective
    assert {'objective_score', 'tissue_contrast'} <= set(graph.readout.products)

def test_named_knee_pairs_ignore_tissue_order():
    graph = build_protocol_experiment(IDS[1])
    data = evaluate_multi_tissue_contrast(graph)
    means = {t['id']: np.mean(np.abs(s)) for t,s in zip(data['tissues'], data['tissue_signals'])}
    assert data['contrast_difference'] == pytest.approx(abs(means['meniscal_tear'] - means['meniscus']))
    assert len(data['pairs']) == len(graph.clinical_recipe.objective.terms)

def test_epg_ensemble_matches_independent_weighted_complex_states():
    spins = (Isochromat(t2=.02, weight=1), Isochromat(t2=.2, weight=3, off_resonance_hz=12))
    combined = EPGBackend(Phantom(isochromats=spins), 8)
    separate = [EPGBackend(Phantom(t1=s.t1,t2=s.t2,proton_density=s.proton_density,off_resonance_hz=s.off_resonance_hz),8) for s in spins]
    for op in (RfOp(t=0, alpha_rad=np.pi/2, phase_rad=0), Relax(t=0, dt=.03)):
        combined.apply(op)
        for b in separate: b.apply(op)
    expected = sum(s.weight*b.observe() for s,b in zip(spins,separate))/4
    assert combined.observe() == pytest.approx(expected)
    np.testing.assert_allclose(combined.snapshot(), sum(s.weight*b.snapshot() for s,b in zip(spins,separate))/4)

@pytest.mark.parametrize('recipe', IDS)
def test_api_emits_named_vector_score_and_aggregate(recipe):
    from fastapi.testclient import TestClient
    from mrqlab_api.main import app
    graph = build_protocol_experiment(recipe)
    response = TestClient(app).post('/experiments/run', json=graph.model_dump(mode='json'))
    assert response.status_code == 200, response.text
    obs = {o['kind']: o['data'] for o in response.json()['observations']}
    expected = -sum(t.weight*p['value'] for t,p in zip(graph.clinical_recipe.objective.terms, obs['tissue_contrast']['pairs']))
    assert obs['objective_score'] == pytest.approx(expected)
    aggregate = np.mean(np.array(obs['tissue_contrast']['tissue_signals'], dtype=complex), axis=0)
    actual = np.array([complex(v['real'],v['imag']) for v in obs['signal']])
    np.testing.assert_allclose(actual, aggregate, atol=1e-12)


def test_api_rejects_clinical_objective_tissues_missing_from_sample_only_graph():
    from fastapi.testclient import TestClient
    from mrqlab_api.main import app
    from mrqlab_experiment.clinical import ObjectiveVector
    from mrqlab_experiment.objectives import ObjectiveFunction, evaluate_multi_tissue_contrast, evaluate_objective

    graph = build_protocol_experiment(IDS[0])
    term = graph.clinical_recipe.objective.terms[0]
    missing_term = term.model_copy(update={"target_tissue_id": "wall", "reference_tissue_id": "blood"})
    recipe_objective = graph.clinical_recipe.objective.model_copy(update={"terms": (missing_term,)})
    graph.clinical_recipe = graph.clinical_recipe.model_copy(update={"objective": recipe_objective})
    graph.objective = ObjectiveFunction(kind="clinical_vector", clinical_vector=ObjectiveVector(terms=(missing_term,)))
    graph.tissue = None

    with pytest.raises(ValueError, match="wall, blood"):
        evaluate_multi_tissue_contrast(graph)
    with pytest.raises(ValueError, match="wall, blood"):
        evaluate_objective(graph.objective, {"multi_tissue_contrast": {
            "tissues": [{"id": "sample"}], "tissue_signals": [[1 + 0j]]
        }})

    response = TestClient(app).post("/experiments/run", json=graph.model_dump(mode="json"))

    assert response.status_code == 422


def test_echo_alias_conflicts_rejected():
    from mrqlab_sequence.templates import build_sequence
    with pytest.raises(ValueError, match='must agree'):
        build_sequence('TSE', {'echo_count': 16, 'echoes': 4})
