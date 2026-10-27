"""Research-model acceptance, never scanner-connected clinical validation.

The legacy named recipes exercise only their actual SE/GRE/TSE relaxation
models, not the clinical mechanisms suggested by their display names.
"""
import json
import hashlib
from time import perf_counter

import numpy as np
import pytest

from mrqlab_experiment import (
    build_protocol_experiment, build_clinical_recipe, build_preset,
    build_result_graph, run_experiment, compile_sequence, plan_experiment,
)
from mrqlab_experiment.clinical import ContrastMetric, ObjectiveVector
from mrqlab_experiment.clinical_search import search_clinical_parameters
from mrqlab_experiment.objectives import ObjectiveFunction, evaluate_objective
from mrqlab_physics.kernel.units import GAMMA_BAR_HZ_T


PROTOCOLS = ("brain_lesion_t2_tse", "knee_cartilage_meniscus_pd_t2_tse")
LEGACY = ("dark_blood_vessel_wall_tse", "cardiac_cine_gre", "abdomen_dixon_gre", "angio_tof_gre", "spin-echo")


def research_graph(name):
    if name in PROTOCOLS:
        return build_protocol_experiment(name)
    graph = build_preset(name) if name == "spin-echo" else build_clinical_recipe(name)
    if name == "spin-echo":
        graph.tissue = build_protocol_experiment(PROTOCOLS[0]).tissue[:2]
    # Legacy tissues have duplicate default ids. Name the relaxation comparison
    # explicitly, without promoting these recipes into the Milestone A catalog.
    graph.tissue = tuple(t.model_copy(update={"id": f"tissue_{i}"}) for i, t in enumerate(graph.tissue))
    graph.objective = ObjectiveFunction(kind="clinical_vector", clinical_vector=ObjectiveVector(terms=(
        ContrastMetric(id="research-relaxation-contrast", target_tissue_id="tissue_0", reference_tissue_id="tissue_1",
                       metric="normalized_cnr_proxy", direction="maximize", weight=1),
    )))
    return graph


@pytest.mark.parametrize("name", (*PROTOCOLS, *LEGACY))
def test_design_lab_search_and_named_clinical_target_replay(name, tmp_path):
    graph = research_graph(name)
    before = graph.model_dump(mode="json")
    tse = graph.sequence.template == "TSE"
    angle = "refocusing_flip_angle" if tse else "flip_angle"
    points = [{"te": te, angle: fa} for te in ((.01, .02, .04) if tse or name == "spin-echo" else (.003, .006, .009)) for fa in ((100., 140., 180.) if tse else (30., 60., 90.))]
    search = search_clinical_parameters(graph, points, max_rf_energy_relative=20, max_repetition_duration_s=3.1)
    assert graph.model_dump(mode="json") == before
    assert len(search.candidates) == 9
    assert search.elapsed_s >= sum(p.elapsed_s for p in search.candidates) > 0
    assert search.best is not None
    assert search.best.objective_loss < search.baseline.objective_loss - 1e-6
    assert search.best.objective_loss == min(p.objective_loss for p in (search.baseline, *search.candidates) if p.feasible)
    assert search.best.rf_energy_relative <= 20
    assert search.best.repetition_duration_s <= 3.1
    assert search.parameter_units == {"te": "s", angle: "deg"}
    replay = graph.model_copy(deep=True)
    replay.sequence.params.update(search.best.parameters)
    replay.readout = replay.readout.model_copy(update={"products": ("signal", "tissue_contrast", "objective_score")})
    assert plan_experiment(replay).fingerprint == search.best.plan_fingerprint
    digest = hashlib.sha256(json.dumps(replay.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    assert digest == search.best.experiment_hash
    replay.readout = replay.readout.model_copy(update={"products": ("signal", "tissue_contrast", "objective_score", "echo_train")})
    run = run_experiment(replay)
    obs = {o.id: o for o in build_result_graph(run).observations}
    assert obs["objective_score"].data == pytest.approx(search.best.objective_loss, abs=1e-12)
    # Independently reconstruct every term, including both Knee named pairs.
    data = obs["tissue_contrast"].data
    means = {t["id"]: np.mean(np.abs(s)) for t, s in zip(data["tissues"], data["tissue_signals"])}
    expected = 0
    for term in graph.objective.clinical_vector.terms:
        a, b = means[term.target_tissue_id], means[term.reference_tissue_id]
        difference = abs(a-b)
        value = {"normalized_cnr_proxy": difference/.05, "absolute_signal_difference": difference, "signal_ratio": a/max(1e-6,b)}[term.metric]
        expected -= term.weight * value
    assert expected == pytest.approx(search.best.objective_loss)
    assert np.isfinite(run.sim_result.signal).all()
    sequence = compile_sequence(replay)
    adc_times = [e.time for ch in sequence.channels if ch.name == "adc_gate" for e in ch.events if e.value == 1]
    count = sequence.metadata["echoes"] if tse else 1
    assert len(adc_times) == count
    assert adc_times == pytest.approx(np.arange(1, count+1) * replay.sequence.params["te"])
    assert len(obs["echo_train"].data) == count
    assert obs["echo_train"].axes["time_s"] == pytest.approx(adc_times)
    assert obs["echo_train"].data == pytest.approx(np.abs(run.sim_result.signal[::2]))
    assert adc_times[-1] + .002 <= sequence.duration
    rf_energy = sum((e.value/180)**2 for ch in sequence.channels if ch.name == "rf_amp" for e in ch.events)
    assert search.best.rf_energy_relative == pytest.approx(rf_energy)
    assert "unavailable" in search.best.gradient_check
    assert "not hardware safety certification" in search.best.safety_scope
    for o in obs.values():
        assert len(o.provenance.plan_fingerprint) == 64
        assert o.provenance.plan_fingerprint == run.plan.fingerprint
        assert len(o.provenance.experiment_hash) == 64
        assert o.provenance.n_ops > 0
    states = {s.name: s for s in run.plan.parameters}
    assert states["te"].unit == "s"
    assert states["te"].value == replay.sequence.params["te"]
    assert run.plan.engine == ("epg" if tse else "bloch")
    if name in PROTOCOLS:
        assert run.plan.clinical_recipe_id == name
        assert run.plan.scanner_profile == "research-3t@1.0.0"
        assert search.objective == graph.clinical_recipe.objective.model_dump(mode="json")
    path = tmp_path / f"{name}-search.json"
    path.write_text(search.model_dump_json(indent=2))
    assert json.loads(path.read_text())["best"]["objective_loss"] == search.best.objective_loss


@pytest.mark.parametrize("name,shift", (("cest_amide_z_spectrum", 3.5), ("cest_amide_pulsed_z_spectrum", 3.5), ("cest_amine_z_spectrum", 2.0)))
def test_cest_coupled_pool_lab_search_exchange_contrast(name, shift, tmp_path):
    # Research question: distinguish an exchanging solute from a no-exchange
    # control via normalized water Z at its chemical shift, not isolated pools.
    graph = build_clinical_recipe(name)
    original = graph.model_dump(mode="json")
    objective = ObjectiveFunction(kind="clinical_vector", clinical_vector=ObjectiveVector(terms=(
        ContrastMetric(id="exchange-sensitive-water", target_tissue_id="exchange", reference_tissue_id="control",
                       metric="absolute_signal_difference", direction="maximize", weight=1),
    )))
    records = []
    for power in (2., .5, 1., 3.):  # first is the actual recipe baseline
        tick = perf_counter()
        pair = []
        hashes = []
        for exchange in (True, False):
            candidate = graph.model_copy(deep=True)
            candidate.sequence.metadata["cest"]["saturation_power_uT"] = power
            if not exchange:
                candidate.tissue = (candidate.tissue[0].model_copy(update={"exchange_rate_hz": 0}), candidate.tissue[1])
            run = run_experiment(candidate)
            obs = {o.id: o for o in build_result_graph(run).observations}
            z = obs["z_spectrum"].data
            offsets = np.asarray(z["offset_ppm"])
            values = np.asarray(z["Z"])
            assert values.shape == offsets.shape
            assert np.isfinite(values).all() and np.all((values >= 0) & (values <= 1.001))
            assert z["offset_hz"] == pytest.approx(offsets * GAMMA_BAR_HZ_T * 3 * 1e-6)
            pair.append([float(values[np.flatnonzero(np.isclose(offsets, shift))[0]])])
            assert run.plan.engine == "epg-x"
            assert obs["z_spectrum"].provenance.plan_fingerprint == run.plan.fingerprint
            assert len(obs["z_spectrum"].provenance.experiment_hash) == 64
            hashes.append(run.plan.fingerprint)
        loss = evaluate_objective(objective, {"multi_tissue_contrast": {
            "tissues": [{"id": "exchange"}, {"id": "control"}], "tissue_signals": pair}})
        assert loss == pytest.approx(-abs(pair[0][0]-pair[1][0]))
        cest = graph.sequence.metadata["cest"]
        on_time = cest["n_pulses"]*cest["pulse_duration_s"] if cest["mode"] == "pulsed" else cest["saturation_duration_s"]
        records.append(dict(power_uT=power, loss=loss, rf_energy_uT2_s=power**2*on_time,
                            saturation_duration_s=cest["saturation_duration_s"], elapsed_s=perf_counter()-tick,
                            fingerprints=hashes, safety_scope="B1 squared times RF on-time proxy; not hardware SAR"))
    # B1 squared times on-time budget has uT² s units, not W/kg SAR.
    feasible = [r for r in records if r["rf_energy_uT2_s"] <= 18 and r["saturation_duration_s"] <= 2]
    best = min(feasible, key=lambda r: r["loss"])
    assert best["loss"] < records[0]["loss"] - 1e-6
    assert best["rf_energy_uT2_s"] <= 18
    assert best["saturation_duration_s"] <= 2
    assert all(r["elapsed_s"] > 0 and len(set(r["fingerprints"])) == 2 for r in records)
    if graph.sequence.metadata["cest"]["mode"] == "pulsed":
        spec = graph.sequence.metadata["cest"]
        assert spec["saturation_duration_s"] == pytest.approx(spec["n_pulses"] * spec["pulse_duration_s"] + (spec["n_pulses"]-1) * spec["gap_duration_s"])
        assert spec["duty_cycle"] == pytest.approx(spec["n_pulses"] * spec["pulse_duration_s"] / spec["saturation_duration_s"])
    assert graph.model_dump(mode="json") == original
    (tmp_path / f"{name}-search.json").write_text(json.dumps({"objective": objective.model_dump(mode="json"), "records": records, "best": best}, indent=2))


def test_search_fails_closed_for_infeasible_budget():
    result = search_clinical_parameters(research_graph(PROTOCOLS[0]), [{"te": .02}], max_rf_energy_relative=.01, max_repetition_duration_s=.01)
    assert result.best is None
    assert all(not p.feasible for p in (result.baseline, *result.candidates))


@pytest.mark.parametrize("patch", ({"te": float("nan")}, {"te": True}, {"te_ms": 20}, {"te": 100}))
def test_search_rejects_invalid_units_or_parameters(patch):
    with pytest.raises(ValueError):
        search_clinical_parameters(research_graph(PROTOCOLS[0]), [patch], max_rf_energy_relative=20, max_repetition_duration_s=3.1)


@pytest.mark.parametrize("dwell", (.0005, .001, .002))
def test_echo_identity_is_independent_of_adc_dwell(dwell):
    graph = build_preset("dark-blood-tse", {"echoes": 4, "te": .02, "tr": .2})
    graph.engine.options = {"dwell_time": dwell}
    graph.readout.products = ("signal", "echo_train")
    run = run_experiment(graph)
    obs = {o.id: o for o in build_result_graph(run).observations}
    samples_per_echo = round(.002 / dwell)
    assert len(run.sim_result.signal) == 4 * samples_per_echo
    assert obs["echo_train"].axes["time_s"] == pytest.approx([.02, .04, .06, .08])
    assert obs["echo_train"].data == pytest.approx(np.abs(run.sim_result.signal[::samples_per_echo]))


def test_search_respects_rf_budget_even_when_unconstrained_contrast_is_better():
    graph = research_graph(PROTOCOLS[0])
    points = [{"refocusing_flip_angle": angle} for angle in (100., 140., 180.)]
    result = search_clinical_parameters(graph, points, max_rf_energy_relative=6, max_repetition_duration_s=3.1)
    assert result.best is not None
    assert result.best.parameters == {"refocusing_flip_angle": 100.}
    assert result.best.rf_energy_relative == pytest.approx(.25 + 16*(100/180)**2)
    assert result.candidates[-1].objective_loss < result.best.objective_loss
    assert not result.candidates[-1].feasible
