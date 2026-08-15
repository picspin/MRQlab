import pytest

from mrqlab_experiment.objectives import ObjectiveFunction, ObjectiveTerm, evaluate_objective


def test_contrast_target_scores_forward_observations_only():
    objective = ObjectiveFunction(
        kind="contrast_target",
        terms=(
            ObjectiveTerm(
                observation="signal",
                metric="peak_magnitude",
                target=0.8,
                weight=2.0,
            ),
        ),
    )
    score = evaluate_objective(objective, {"signal": [0.5 + 0j, 0.9 + 0j]})
    assert score == pytest.approx(0.02)
    assert not hasattr(objective, "optimize")


def test_null_objective_scores_zero():
    assert evaluate_objective(ObjectiveFunction(), {"signal": []}) == 0.0
