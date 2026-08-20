from fastapi.testclient import TestClient

from mrqlab_api.main import app
from mrqlab_experiment.optimizer import OptimizeGoal, compute_pareto, evaluate_tse_point

client = TestClient(app)


def test_higher_fa_increases_relative_sar():
    _, _, sar_lo = evaluate_tse_point(120, 100, target_t2_ms=120, reference_t2_ms=80, echo_train_length=16)
    _, _, sar_hi = evaluate_tse_point(180, 100, target_t2_ms=120, reference_t2_ms=80, echo_train_length=16)
    assert sar_hi > sar_lo


def test_pareto_frontier_is_non_dominated_and_feasible_when_possible():
    analysis = compute_pareto(OptimizeGoal(mode="balanced_sar", max_sar_budget=50.0, min_cnr_proxy=1.0))
    assert analysis.grid_size == 9 * 7
    assert analysis.optimal_candidate.is_feasible is True
    frontier = analysis.pareto_frontier
    assert len(frontier) >= 2
    for i, p in enumerate(frontier):
        assert p.is_dominated is False
        for q in frontier[i + 1 :]:
            # sorted by SAR; a later (higher-SAR) point must not be weakly worse on CNR
            weakly_worse = q.cnr_proxy <= p.cnr_proxy and q.relative_sar >= p.relative_sar
            identical = q.cnr_proxy == p.cnr_proxy and q.relative_sar == p.relative_sar
            assert not weakly_worse or identical

    tight = compute_pareto(OptimizeGoal(mode="balanced_sar", max_sar_budget=35.0, min_cnr_proxy=2.5))
    assert tight.optimal_candidate.is_feasible is True


def test_min_sar_picks_lower_sar_than_max_contrast():
    cool = compute_pareto(OptimizeGoal(mode="min_sar", max_sar_budget=50.0, min_cnr_proxy=1.0))
    hot = compute_pareto(OptimizeGoal(mode="max_contrast", max_sar_budget=50.0, min_cnr_proxy=1.0))
    assert cool.optimal_candidate.relative_sar <= hot.optimal_candidate.relative_sar


def test_tight_sar_budget_marks_high_fa_infeasible():
    analysis = compute_pareto(OptimizeGoal(mode="max_contrast", max_sar_budget=18.0, min_cnr_proxy=0.5))
    high_fa = [p for p in analysis.candidates if p.flip_angle >= 170]
    assert any(not p.is_feasible for p in high_fa)


def test_optimize_pareto_endpoint():
    res = client.post(
        "/optimize/pareto",
        json={"mode": "balanced_sar", "max_sar_budget": 35.0, "min_cnr_proxy": 2.5},
    )
    assert res.status_code == 200
    body = res.json()
    assert "pareto_frontier" in body
    assert "optimal_candidate" in body
    assert "sensitivities" in body
    opt = body["optimal_candidate"]
    assert opt["flip_angle"] >= 100
    assert opt["te_eff"] >= 60
    assert len(body["sensitivities"]) == 2
